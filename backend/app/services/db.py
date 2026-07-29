"""SQLite persistence layer.

Uses the stdlib ``sqlite3`` rather than SQLAlchemy deliberately: the platform's
whole premise is that it boots and tests with no external services and no extra
dependencies, and the three things that need to survive a restart — users,
conversations, documents — are small, relational, and single-writer. SQLite in
WAL mode covers that. The seam for swapping in Postgres is ``DATABASE_URL``
plus this module's narrow surface (``execute`` / ``query`` / ``query_one``); no
caller touches a connection directly.

Threading: FastAPI serves requests on a thread pool, so the connection is
opened with ``check_same_thread=False`` and every statement goes through one
re-entrant lock. That serialises writes, which is what SQLite wants anyway, and
keeps reads honest without a connection pool to reason about.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    summary    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL,
    chunk_count  INTEGER NOT NULL,
    uploaded_at  TEXT NOT NULL,
    uploaded_by  TEXT NOT NULL
);
"""


def resolve_path(database_url: str) -> str:
    """Turn a ``sqlite:///...`` URL into a path ``sqlite3.connect`` accepts.

    Anything that is not a sqlite URL falls back to in-memory with a warning
    rather than raising — a misconfigured DATABASE_URL should not stop the
    platform from booting, and the log line says exactly what happened.
    """
    if database_url in {":memory:", "sqlite:///:memory:", "sqlite://:memory:"}:
        return ":memory:"
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///") :]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://") :]
    logger.warning(
        "DATABASE_URL %r is not a sqlite:// URL; falling back to in-memory storage",
        database_url,
    )
    return ":memory:"


class Database:
    def __init__(self, database_url: str) -> None:
        self.path = resolve_path(database_url)
        self._lock = threading.RLock()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            if self.path != ":memory:":
                # WAL lets readers run while a write is in flight. It is a no-op
                # (and unsupported) for :memory:, hence the guard.
                self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def executemany(self, sql: str, seq: Iterable[Sequence[Any]]) -> None:
        with self._lock:
            self._conn.executemany(sql, seq)
            self._conn.commit()

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
