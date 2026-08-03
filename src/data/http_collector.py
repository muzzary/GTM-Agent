import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Protocol
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx2

from src.data.html_parser import ParsedHtml, parse_public_html, strip_contact_data
from src.data.research_cache import CacheEntry, ResearchCache
from src.data.source_policy import Resolver, SourcePolicy, validate_url


class ResearchCollectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def get(
        self, url: str, *, headers: Mapping[str, str], max_bytes: int
    ) -> HttpResponse: ...


@dataclass(frozen=True)
class CollectedDocument:
    requested_url: str
    canonical_url: str
    title: str
    text: str
    links: tuple[str, ...]
    content_type: str
    body_sha256: str
    fetched_at: datetime
    observed_at: datetime
    cache_hit: bool


@dataclass(frozen=True)
class _RobotsDecision:
    parser: RobotFileParser | None
    expires_at: datetime
    crawl_delay: float | None


class HttpxTransport:
    def __init__(self, user_agent: str) -> None:
        self._client = httpx2.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip"},
            timeout=httpx2.Timeout(10.0, connect=5.0),
            limits=httpx2.Limits(max_connections=1, max_keepalive_connections=1),
            follow_redirects=False,
            trust_env=False,
        )

    def get(
        self, url: str, *, headers: Mapping[str, str], max_bytes: int
    ) -> HttpResponse:
        try:
            with self._client.stream("GET", url, headers=headers) as response:
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ResearchCollectionError("response_too_large")
                    chunks.append(chunk)
                return HttpResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=b"".join(chunks),
                )
        except httpx2.HTTPError as error:
            raise ResearchCollectionError("source_unavailable") from error


class ControlledHttpCollector:
    def __init__(
        self,
        *,
        transport: HttpTransport,
        resolver: Resolver,
        research_contact: str,
        cache: ResearchCache | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if "\r" in research_contact or "\n" in research_contact:
            raise ValueError("research contact cannot contain line breaks")
        self._transport = transport
        self._resolver = resolver
        self._cache = cache
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or time.sleep
        self._user_agent = f"GTM-Agent/0.4 ({research_contact})"
        self._last_request: dict[str, float] = {}
        self._host_delay: dict[str, float] = {}
        self._robots: dict[str, _RobotsDecision] = {}

    def collect(self, raw_url: str, policy: SourcePolicy) -> CollectedDocument:
        observed_at = self._now()
        requested = validate_url(raw_url, policy, self._resolver)
        if policy.robots_required:
            self._require_robots_permission(requested.url, policy, observed_at)
        cache_key = f"{policy.policy_version}:{requested.url}"
        cached = self._cache_get(cache_key, policy, observed_at)
        if cached is not None:
            cached_canonical = validate_url(
                cached.canonical_url,
                policy,
                self._resolver,
            )
            if policy.robots_required and cached_canonical.url != requested.url:
                self._require_robots_permission(
                    cached_canonical.url,
                    policy,
                    observed_at,
                )
            return self._document_from_body(
                requested.url,
                cached_canonical.url,
                cached.content_type,
                cached.body,
                cached.fetched_at,
                observed_at,
                cache_hit=True,
            )

        current = requested
        for redirect_count in range(policy.max_redirects + 1):
            response = self._request(current.url, current.host, policy)
            if 300 <= response.status_code < 400:
                location = response.headers.get("location")
                if not location or redirect_count >= policy.max_redirects:
                    raise ResearchCollectionError("redirect_not_allowed")
                current = validate_url(
                    urljoin(current.url, location), policy, self._resolver
                )
                if policy.robots_required:
                    self._require_robots_permission(current.url, policy, self._now())
                continue
            if response.status_code < 200 or response.status_code >= 300:
                raise ResearchCollectionError("source_http_error")
            content_type = response.headers.get("content-type", "").split(";", 1)[0]
            if content_type not in policy.allowed_content_types:
                raise ResearchCollectionError("unsupported_content_type")
            fetched_at = self._now()
            self._cache_put(
                CacheEntry(
                    cache_key=cache_key,
                    policy_version=policy.policy_version,
                    canonical_url=current.url,
                    status_code=response.status_code,
                    content_type=content_type,
                    body=response.body,
                    body_sha256=sha256(response.body).hexdigest(),
                    fetched_at=fetched_at,
                    expires_at=fetched_at + timedelta(seconds=policy.cache_ttl_seconds),
                )
            )
            return self._document_from_body(
                requested.url,
                current.url,
                content_type,
                response.body,
                fetched_at,
                observed_at,
                cache_hit=False,
            )
        raise ResearchCollectionError("redirect_not_allowed")

    def _request(self, url: str, host: str, policy: SourcePolicy) -> HttpResponse:
        for attempt in range(2):
            interval = max(
                policy.minimum_request_interval_seconds,
                self._host_delay.get(host, 0.0),
            )
            self._rate_limit(host, interval)
            response = self._transport.get(
                url,
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/json, text/html, text/plain",
                },
                max_bytes=policy.max_response_bytes,
            )
            if response.status_code not in {429, 503} or attempt == 1:
                return response
            self._sleep(self._retry_delay(response.headers.get("retry-after")))
        raise ResearchCollectionError("source_unavailable")

    def _rate_limit(self, host: str, interval: float) -> None:
        current = self._monotonic()
        previous = self._last_request.get(host)
        if previous is not None:
            wait = interval - (current - previous)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._monotonic()

    def _require_robots_permission(
        self, url: str, policy: SourcePolicy, observed_at: datetime
    ) -> None:
        host = urlsplit(url).hostname or ""
        decision = self._robots.get(host)
        if decision is None or decision.expires_at <= observed_at:
            robots_url = f"https://{host}/robots.txt"
            validate_url(robots_url, policy, self._resolver)
            response = self._request(robots_url, host, policy)
            if response.status_code >= 500:
                raise ResearchCollectionError("robots_unavailable")
            parser: RobotFileParser | None = None
            delay: float | None = None
            if response.status_code < 400:
                parser = RobotFileParser()
                parser.set_url(robots_url)
                robots_text = response.body.decode("utf-8", errors="replace")
                parser.parse(robots_text.splitlines())
                delay = parser.crawl_delay(self._user_agent)
                request_rate = parser.request_rate(self._user_agent)
                if request_rate is not None and request_rate.requests > 0:
                    rate_delay = request_rate.seconds / request_rate.requests
                    delay = max(delay or 0.0, rate_delay)
            decision = _RobotsDecision(
                parser=parser,
                expires_at=observed_at + timedelta(hours=24),
                crawl_delay=delay,
            )
            self._robots[host] = decision
            if delay is not None:
                self._host_delay[host] = max(self._host_delay.get(host, 0), delay)
        if decision.parser is not None and not decision.parser.can_fetch(
            self._user_agent, url
        ):
            raise ResearchCollectionError("robots_denied")

    def _cache_get(
        self, cache_key: str, policy: SourcePolicy, observed_at: datetime
    ) -> CacheEntry | None:
        if self._cache is None:
            return None
        try:
            return self._cache.get(cache_key, policy.policy_version, observed_at)
        except (OSError, sqlite3.Error):
            return None

    def _cache_put(self, entry: CacheEntry) -> None:
        if self._cache is None:
            return
        try:
            self._cache.put(entry)
        except (OSError, sqlite3.Error):
            return

    def _retry_delay(self, value: str | None) -> float:
        if value is None:
            return 5.0
        try:
            delay = float(value)
        except ValueError:
            try:
                target = parsedate_to_datetime(value)
                delay = (target - self._now()).total_seconds()
            except (TypeError, ValueError):
                return 5.0
        if delay < 0 or delay > 30:
            raise ResearchCollectionError("retry_after_too_long")
        return delay

    @staticmethod
    def _document_from_body(
        requested_url: str,
        canonical_url: str,
        content_type: str,
        body: bytes,
        fetched_at: datetime,
        observed_at: datetime,
        *,
        cache_hit: bool,
    ) -> CollectedDocument:
        if content_type == "text/html":
            parsed: ParsedHtml = parse_public_html(body, canonical_url)
            title, text, links = parsed.title, parsed.text, parsed.links
        else:
            title = urlsplit(canonical_url).hostname or canonical_url
            text = body.decode("utf-8", errors="replace")[:100_000]
            if content_type == "text/plain":
                text = strip_contact_data(text)
            links = ()
        return CollectedDocument(
            requested_url=requested_url,
            canonical_url=canonical_url,
            title=title,
            text=text,
            links=links,
            content_type=content_type,
            body_sha256=sha256(body).hexdigest(),
            fetched_at=fetched_at,
            observed_at=observed_at,
            cache_hit=cache_hit,
        )
