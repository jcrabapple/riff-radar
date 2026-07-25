"""Plain-text digest of recent finds, for piping into email or chat."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import Config
from .store import Store, StoredRelease


def _line(rel: StoredRelease, is_seed: bool) -> list[str]:
    tag = "*" if is_seed else " "
    lines = [
        f" {tag} {rel.score:5.1f}  {rel.artist_name} - {rel.title} "
        f"({rel.record_type}, {rel.release_date})",
    ]
    if rel.link:
        lines.append(f"        {rel.link}")
    return lines


def render_digest(store: Store, cfg: Config, days: int = 7,
                  today: date | None = None) -> str:
    """Summarize releases first seen in the last `days` days as plain text."""
    today = today or date.today()
    cutoff = datetime.combine(today - timedelta(days=days),
                              datetime.min.time()).isoformat(timespec="seconds")
    releases = store.releases_since(cutoff)
    seeds = {s.lower() for s in cfg.seed_artists}

    header = (f"riff-radar digest, "
              f"{today - timedelta(days=days):%Y-%m-%d} to {today:%Y-%m-%d} "
              f"({days} days)")
    if not releases:
        return f"{header}\n\nno new releases. quiet week.\n"

    seed_rels = [r for r in releases if r.artist_name.lower() in seeds]
    other_rels = [r for r in releases if r.artist_name.lower() not in seeds]

    lines = [header, ""]
    lines.append(f"{len(releases)} new release(s), "
                 f"{len(seed_rels)} from seed artists")
    lines.append("")
    if seed_rels:
        lines.append("seed artists")
        for r in seed_rels:
            lines.extend(_line(r, True))
        lines.append("")
    if other_rels:
        lines.append("discoveries")
        for r in other_rels:
            lines.extend(_line(r, False))
        lines.append("")
    return "\n".join(lines) + "\n"
