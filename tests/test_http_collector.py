from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.data.http_collector import (
    ControlledHttpCollector,
    HttpResponse,
    ResearchCollectionError,
)
from src.data.research_cache import ResearchCache
from src.data.source_policy import SourcePolicy

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


class FakeTransport:
    def __init__(self, responses: Mapping[str, HttpResponse]) -> None:
        self.responses = dict(responses)
        self.requested: list[str] = []

    def get(self, url: str, *, headers: Mapping[str, str], max_bytes: int):
        self.requested.append(url)
        response = self.responses[url]
        if len(response.body) > max_bytes:
            raise ResearchCollectionError("response_too_large")
        return response


def policy() -> SourcePolicy:
    return SourcePolicy(
        policy_version="website-v1",
        allowed_hosts=frozenset({"example.com", "www.example.com"}),
        allowed_path_prefixes=("/",),
        allowed_content_types=frozenset({"text/html", "text/plain"}),
        robots_required=True,
        max_redirects=2,
        max_response_bytes=1_024,
    )


def response(status: int, body: bytes, content_type: str = "text/html"):
    return HttpResponse(
        status_code=status,
        headers={"content-type": content_type},
        body=body,
    )


def test_collector_obeys_robots_and_revalidates_redirects() -> None:
    transport = FakeTransport(
        {
            "https://example.com/robots.txt": response(404, b""),
            "https://example.com/about": HttpResponse(
                status_code=301,
                headers={"location": "https://www.example.com/about"},
                body=b"",
            ),
            "https://www.example.com/robots.txt": response(404, b""),
            "https://www.example.com/about": response(
                200, b"<title>About</title><p>Example logistics company.</p>"
            ),
        }
    )
    collector = ControlledHttpCollector(
        transport=transport,
        resolver=lambda _host: ("93.184.216.34",),
        research_contact="owner@example.com",
        now=lambda: NOW,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    document = collector.collect("https://example.com/about", policy())

    assert document.canonical_url == "https://www.example.com/about"
    assert document.title == "About"
    assert transport.requested[-1] == "https://www.example.com/about"


def test_collector_fails_closed_on_robots_server_failure() -> None:
    transport = FakeTransport(
        {"https://example.com/robots.txt": response(503, b"unavailable")}
    )
    collector = ControlledHttpCollector(
        transport=transport,
        resolver=lambda _host: ("93.184.216.34",),
        research_contact="owner@example.com",
        now=lambda: NOW,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(ResearchCollectionError, match="robots_unavailable"):
        collector.collect("https://example.com/about", policy())


def test_collector_rejects_unexpected_content_type() -> None:
    transport = FakeTransport(
        {
            "https://example.com/robots.txt": response(404, b""),
            "https://example.com/about": response(
                200, b"binary", "application/octet-stream"
            ),
        }
    )
    collector = ControlledHttpCollector(
        transport=transport,
        resolver=lambda _host: ("93.184.216.34",),
        research_contact="owner@example.com",
        now=lambda: NOW,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(ResearchCollectionError, match="unsupported_content_type"):
        collector.collect("https://example.com/about", policy())


def test_collector_obeys_robots_disallow() -> None:
    transport = FakeTransport(
        {
            "https://example.com/robots.txt": response(
                200, b"User-agent: *\nDisallow: /private"
            )
        }
    )
    collector = ControlledHttpCollector(
        transport=transport,
        resolver=lambda _host: ("93.184.216.34",),
        research_contact="owner@example.com",
        now=lambda: NOW,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(ResearchCollectionError, match="robots_denied"):
        collector.collect("https://example.com/private/project", policy())


def test_collector_reuses_valid_cached_content(tmp_path: Path) -> None:
    transport = FakeTransport(
        {
            "https://example.com/robots.txt": response(404, b""),
            "https://example.com/about": response(
                200, b"<title>About</title><p>Logistics company.</p>"
            ),
        }
    )
    collector = ControlledHttpCollector(
        transport=transport,
        resolver=lambda _host: ("93.184.216.34",),
        research_contact="owner@example.com",
        cache=ResearchCache(tmp_path / "cache.sqlite3"),
        now=lambda: NOW,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    first = collector.collect("https://example.com/about", policy())
    second = collector.collect("https://example.com/about", policy())

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert transport.requested.count("https://example.com/about") == 1
