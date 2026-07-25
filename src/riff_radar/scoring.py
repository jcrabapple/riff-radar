"""Release scoring.

Score components (0..100):
  recency   0..40   linear decay across the scan window
  proximity 0..35   seed artist > direct related > anything else
  keywords  0..25   genre/scene keywords found in title or artist name

The formula is deliberately simple and documented so every part of a
release's score is explainable in the report.
"""

from __future__ import annotations

from datetime import date

RECENCY_MAX = 40.0
PROXIMITY_SEED = 35.0
PROXIMITY_RELATED = 18.0
KEYWORD_MAX = 25.0


def parse_date(s: str) -> date | None:
    try:
        y, m, d = (int(p) for p in s.split("-"))
        if y == 0:
            return None
        return date(y, max(1, min(12, m)), max(1, min(28, d)))
    except (ValueError, AttributeError):
        return None


def recency_score(release: date, today: date, window_days: int) -> float:
    age = (today - release).days
    if age < 0:
        return RECENCY_MAX  # announced future release: full marks
    if age > window_days:
        return 0.0
    return RECENCY_MAX * (1 - age / max(1, window_days))


def keyword_hits(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    return [k for k in keywords if k.lower() in low]


def keyword_score(text: str, keywords: list[str]) -> float:
    hits = keyword_hits(text, keywords)
    if not hits:
        return 0.0
    # Diminishing returns: first hit is worth the most.
    return min(KEYWORD_MAX, 12.0 + 6.5 * (len(hits) - 1))


def proximity_score(is_seed: bool, is_related: bool) -> float:
    if is_seed:
        return PROXIMITY_SEED
    if is_related:
        return PROXIMITY_RELATED
    return 0.0


def score_release(
    release_date: date | None,
    title: str,
    artist_name: str,
    *,
    is_seed: bool,
    is_related: bool,
    keywords: list[str],
    today: date,
    window_days: int,
) -> tuple[float, dict]:
    """Return (score, breakdown) so reports can explain every point."""
    if release_date is None:
        rec = 0.0
    else:
        rec = recency_score(release_date, today, window_days)
    prox = proximity_score(is_seed, is_related)
    kw = keyword_score(f"{title} {artist_name}", keywords)
    total = round(rec + prox + kw, 1)
    return total, {
        "recency": round(rec, 1),
        "proximity": prox,
        "keywords": round(kw, 1),
        "keyword_hits": keyword_hits(f"{title} {artist_name}", keywords),
    }
