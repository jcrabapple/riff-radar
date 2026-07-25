"""The scan engine: seeds -> related artists -> recent releases -> scored, deduped."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime

from .config import Config
from .deezer import DeezerClient, Artist, Release, DeezerError
from .scoring import parse_date, score_release
from .store import Store


@dataclass
class ScoredRelease:
    release: Release
    score: float
    breakdown: dict
    is_seed_artist: bool


@dataclass
class ScanResult:
    new_releases: list[ScoredRelease] = field(default_factory=list)
    artists_scanned: int = 0
    seed_names_missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_artist_graph(client: DeezerClient, cfg: Config) -> tuple[dict[int, tuple[Artist, bool]], list[str], list[str]]:
    """Return ({artist_id: (artist, is_seed)}, missing_seed_names, errors)."""
    graph: dict[int, tuple[Artist, bool]] = {}
    missing: list[str] = []
    errors: list[str] = []
    for name in cfg.seed_artists:
        try:
            seed = client.search_artist(name)
        except DeezerError as e:
            errors.append(f"search '{name}': {e}")
            continue
        if seed is None:
            missing.append(name)
            continue
        graph[seed.id] = (seed, True)
        try:
            for rel in client.related_artists(seed.id, limit=cfg.related_per_seed):
                if len(graph) >= cfg.max_artists_per_scan:
                    break
                graph.setdefault(rel.id, (rel, False))
        except DeezerError as e:
            errors.append(f"related for '{seed.name}': {e}")
        if len(graph) >= cfg.max_artists_per_scan:
            break
    return graph, missing, errors


def skipped_record_types(cfg: Config, artist_name: str) -> set[str]:
    """Record types to ignore for an artist: global skips plus per-artist extras."""
    skip = {t.lower() for t in cfg.skip_record_types}
    for name, types in cfg.artist_skip_record_types.items():
        if name.lower() == artist_name.lower():
            skip |= {t.lower() for t in types}
    return skip


def scan(client: DeezerClient, store: Store, cfg: Config,
         today: date | None = None) -> ScanResult:
    today = today or date.today()
    result = ScanResult()
    graph, missing, errors = build_artist_graph(client, cfg)
    result.seed_names_missing = missing
    result.errors = errors
    result.artists_scanned = len(graph)

    seen = store.seen_ids()
    for artist_id, (artist, is_seed) in graph.items():
        skip_types = skipped_record_types(cfg, artist.name)
        try:
            releases = client.artist_releases(artist_id, artist_name=artist.name)
        except DeezerError as e:
            result.errors.append(f"albums for '{artist.name}': {e}")
            continue
        for rel in releases:
            if rel.id in seen:
                continue
            if rel.record_type.lower() in skip_types:
                continue
            rd = parse_date(rel.release_date)
            if rd is None:
                continue
            age = (today - rd).days
            if age > cfg.window_days:
                continue  # older than the window; not added, may resurface never
            score, breakdown = score_release(
                rd, rel.title, rel.artist_name,
                is_seed=is_seed, is_related=not is_seed,
                keywords=cfg.keywords, today=today,
                window_days=cfg.window_days,
            )
            scored = ScoredRelease(rel, score, breakdown, is_seed)
            result.new_releases.append(scored)
            store.add_release(rel, score, json.dumps(breakdown),
                              datetime.now().isoformat(timespec="seconds"))
            seen.add(rel.id)

    result.new_releases.sort(key=lambda s: s.score, reverse=True)
    store.record_scan(datetime.now().isoformat(timespec="seconds"),
                      result.artists_scanned, len(result.new_releases))
    store.commit()
    return result
