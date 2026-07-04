"""Persistent search history, stored in SQLite under the user's data directory."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

from dorker.engines.base import SearchResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    engines TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL REFERENCES queries(id),
    url TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    engine TEXT,
    score REAL
);
"""


def default_db_path() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    data_dir = Path(data_home) / "dorker"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "history.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def save_search(
    query: str,
    engines: list[str],
    results: list[SearchResult],
    db_path: Optional[Path] = None,
) -> int:
    """Persist a query and its results; returns the new query id."""
    db_path = db_path or default_db_path()
    with closing(_connect(db_path)) as conn:
        cur = conn.execute(
            "INSERT INTO queries (query, engines) VALUES (?, ?)",
            (query, ",".join(engines)),
        )
        query_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO results (query_id, url, title, snippet, engine, score) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(query_id, r.url, r.title, r.snippet, r.engine, r.score) for r in results],
        )
        conn.commit()
        return query_id


def list_history(limit: int = 20, db_path: Optional[Path] = None) -> list[dict]:
    """Return the most recent queries, newest first."""
    db_path = db_path or default_db_path()
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, query, engines, timestamp FROM queries ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def search_history(term: str, limit: int = 20, db_path: Optional[Path] = None) -> list[dict]:
    """Find past queries whose text contains the given term."""
    db_path = db_path or default_db_path()
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, query, engines, timestamp FROM queries "
            "WHERE query LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{term}%", limit),
        ).fetchall()
        return [dict(row) for row in rows]
