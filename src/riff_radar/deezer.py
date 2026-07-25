"""Thin Deezer public-API client.

Uses only the unauthenticated endpoints (api.deezer.com), so no API key,
no OAuth, no rate-limit drama beyond the soft ~50 req/5s guidance. We add
a small polite delay between calls and retry once on transient failure.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE = "https://api.deezer.com"
USER_AGENT = "riff-radar/0.1 (+https://github.com/jcrabapple/riff-radar)"


class DeezerError(RuntimeError):
    pass


@dataclass
class Artist:
    id: int
    name: str


@dataclass
class Release:
    id: int
    title: str
    artist_id: int
    artist_name: str
    release_date: str  # YYYY-MM-DD
    record_type: str   # "album" | "single" | "ep" | "compile"
    link: str
    cover: str


def _get(path: str, params: dict | None = None, retries: int = 2) -> dict:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode())
            if isinstance(payload, dict) and payload.get("error"):
                raise DeezerError(f"Deezer API error: {payload['error']}")
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise DeezerError(f"request failed: {url}: {last_err}")


def _polite(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)


class DeezerClient:
    def __init__(self, delay: float = 0.15):
        self.delay = delay

    def search_artist(self, name: str) -> Artist | None:
        data = _get("/search/artist", {"q": name, "limit": 5})
        _polite(self.delay)
        for item in data.get("data", []):
            # Prefer an exact (case-insensitive) name match.
            if item.get("name", "").lower() == name.lower():
                return Artist(id=item["id"], name=item["name"])
        items = data.get("data", [])
        return Artist(id=items[0]["id"], name=items[0]["name"]) if items else None

    def related_artists(self, artist_id: int, limit: int = 10) -> list[Artist]:
        data = _get(f"/artist/{artist_id}/related", {"limit": limit})
        _polite(self.delay)
        return [Artist(id=a["id"], name=a["name"]) for a in data.get("data", [])]

    def artist_releases(self, artist_id: int, limit: int = 25,
                        artist_name: str = "") -> list[Release]:
        data = _get(f"/artist/{artist_id}/albums", {"limit": limit})
        _polite(self.delay)
        out = []
        for a in data.get("data", []):
            artist = a.get("artist") or {}
            out.append(Release(
                id=a["id"],
                title=a.get("title", ""),
                artist_id=artist.get("id", artist_id),
                artist_name=artist.get("name") or artist_name,
                release_date=a.get("release_date", "0000-00-00"),
                record_type=a.get("record_type", "album"),
                link=a.get("link", ""),
                cover=a.get("cover_medium", ""),
            ))
        return out
