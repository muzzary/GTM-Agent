from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from src.data.http_collector import (
    ControlledHttpCollector,
    HttpResponse,
    HttpxTransport,
    ResearchCollectionError,
)
from src.data.research_cache import ResearchCache
from src.data.source_policy import SourcePolicy, SourcePolicyError

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


def test_httpx_transport_reports_timeouts_separately(monkeypatch) -> None:
    class TimedOutClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def stream(self, *_args, **_kwargs):
            raise httpx2.ReadTimeout("timed out")

    monkeypatch.setattr("src.data.http_collector.httpx2.Client", TimedOutClient)
    transport = HttpxTransport("GTM-Agent/test")

    with pytest.raises(ResearchCollectionError, match="^source_timeout$"):
        transport.get("https://example.com/", headers={}, max_bytes=1024)


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


def test_plain_text_collection_removes_contact_details() -> None:
    transport = FakeTransport(
        {
            "https://example.com/robots.txt": response(404, b""),
            "https://example.com/about": response(
                200,
                b"Contact sales@example.com or +1 (555) 123-4567",
                "text/plain",
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

    assert "sales@example.com" not in document.text
    assert "555" not in document.text
    assert document.text.count("[contact removed]") == 2


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


def test_cached_redirect_target_is_revalidated_before_use(tmp_path: Path) -> None:
    addresses = {
        "example.com": "93.184.216.34",
        "www.example.com": "93.184.216.34",
    }
    transport = FakeTransport(
        {
            "https://example.com/robots.txt": response(404, b""),
            "https://example.com/about": HttpResponse(
                status_code=301,
                headers={"location": "https://www.example.com/about"},
                body=b"",
            ),
            "https://www.example.com/robots.txt": response(404, b""),
            "https://www.example.com/about": response(200, b"<p>Company</p>"),
        }
    )
    collector = ControlledHttpCollector(
        transport=transport,
        resolver=lambda host: (addresses[host],),
        research_contact="owner@example.com",
        cache=ResearchCache(tmp_path / "cache.sqlite3"),
        now=lambda: NOW,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )
    collector.collect("https://example.com/about", policy())
    addresses["www.example.com"] = "127.0.0.1"

    with pytest.raises(SourcePolicyError, match="public address"):
        collector.collect("https://example.com/about", policy())
