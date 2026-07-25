"""SQLite store: seen releases, dedupe, scan history.

Dedupe key is the Deezer album id, which is stable across re-scans.
A release is "new" the first time we see it; afterwards it stays in the
DB so reports can show history but scans stay quiet about it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS releases (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    release_date TEXT NOT NULL,
    record_type TEXT NOT NULL,
    link TEXT,
    cover TEXT,
    score REAL NOT NULL,
    breakdown TEXT,
    first_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at TEXT NOT NULL,
    artists_scanned INTEGER NOT NULL,
    new_found INTEGER NOT NULL
);
"""


@dataclass
class StoredRelease:
    id: int
    title: str
    artist_name: str
    release_date: str
    record_type: str
    link: str
    cover: str
    score: float
    breakdown: str
    first_seen: str


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def seen_ids(self) -> set[int]:
        rows = self.conn.execute("SELECT id FROM releases").fetchall()
        return {r["id"] for r in rows}

    def add_release(self, rel, score: float, breakdown: str, first_seen: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO releases VALUES (?,?,?,?,?,?,?,?,?,?)",
            (rel.id, rel.title, rel.artist_name, rel.release_date,
             rel.record_type, rel.link, rel.cover, score, breakdown, first_seen),
        )

    def record_scan(self, ran_at: str, artists_scanned: int, new_found: int) -> None:
        self.conn.execute(
            "INSERT INTO scans (ran_at, artists_scanned, new_found) VALUES (?,?,?)",
            (ran_at, artists_scanned, new_found),
        )

    def recent_releases(self, limit: int = 100) -> list[StoredRelease]:
        rows = self.conn.execute(
            "SELECT * FROM releases ORDER BY release_date DESC, score DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [StoredRelease(**dict(r)) for r in rows]

    def stats(self) -> dict:
        rel = self.conn.execute("SELECT COUNT(*) c FROM releases").fetchone()["c"]
        scans = self.conn.execute("SELECT COUNT(*) c FROM scans").fetchone()["c"]
        artists = self.conn.execute(
            "SELECT COUNT(DISTINCT artist_name) c FROM releases").fetchone()["c"]
        return {"releases": rel, "scans": scans, "artists": artists}

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
