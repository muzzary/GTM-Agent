import sqlite3
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from src.data.research_cache import CacheEntry, ResearchCache

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def test_sqlite_cache_round_trip_expiry_and_hash_validation(tmp_path: Path) -> None:
    cache = ResearchCache(tmp_path / "research.sqlite3")
    body = b"public evidence"
    entry = CacheEntry(
        cache_key="website-v1:https://example.com/about",
        policy_version="website-v1",
        canonical_url="https://example.com/about",
        status_code=200,
        content_type="text/html",
        body=body,
        body_sha256=sha256(body).hexdigest(),
        fetched_at=NOW,
        expires_at=NOW + timedelta(hours=24),
    )

    cache.put(entry)
    assert cache.get(entry.cache_key, "website-v1", NOW) == entry
    assert cache.get(entry.cache_key, "website-v1", NOW + timedelta(days=2)) is None

    with sqlite3.connect(cache.path) as connection:
        connection.execute(
            "UPDATE research_cache SET body = ? WHERE cache_key = ?",
            (b"tampered", entry.cache_key),
        )
    assert cache.get(entry.cache_key, "website-v1", NOW) is None
