import sqlite3
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class CacheEntry:
    cache_key: str
    policy_version: str
    canonical_url: str
    status_code: int
    content_type: str
    body: bytes
    body_sha256: str
    fetched_at: datetime
    expires_at: datetime


class ResearchCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_cache (
                    cache_key TEXT PRIMARY KEY,
                    policy_version TEXT NOT NULL,
                    canonical_url TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    body BLOB NOT NULL,
                    body_sha256 TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )

    def get(
        self, cache_key: str, policy_version: str, observed_at: datetime
    ) -> CacheEntry | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT policy_version, canonical_url, status_code, content_type,
                       body, body_sha256, fetched_at, expires_at
                FROM research_cache WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
        if row is None or row[0] != policy_version:
            return None
        body = bytes(row[4])
        fetched_at = datetime.fromisoformat(row[6])
        expires_at = datetime.fromisoformat(row[7])
        if expires_at <= observed_at or sha256(body).hexdigest() != row[5]:
            return None
        return CacheEntry(
            cache_key=cache_key,
            policy_version=row[0],
            canonical_url=row[1],
            status_code=row[2],
            content_type=row[3],
            body=body,
            body_sha256=row[5],
            fetched_at=fetched_at,
            expires_at=expires_at,
        )

    def put(self, entry: CacheEntry) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO research_cache (
                    cache_key, policy_version, canonical_url, status_code,
                    content_type, body, body_sha256, fetched_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.cache_key,
                    entry.policy_version,
                    entry.canonical_url,
                    entry.status_code,
                    entry.content_type,
                    entry.body,
                    entry.body_sha256,
                    entry.fetched_at.isoformat(),
                    entry.expires_at.isoformat(),
                ),
            )
