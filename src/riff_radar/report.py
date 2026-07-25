"""Static HTML report: dark theme, cover grid, explainable scores."""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

from .store import Store

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin:0; background:#0d0d10; color:#e8e6e3;
       font-family: ui-sans-serif, system-ui, sans-serif; }
header { padding:2rem 2rem 1rem; border-bottom:1px solid #26262e; }
h1 { margin:0; font-size:1.6rem; letter-spacing:0.02em; }
h1 .accent { color:#ff4d2e; }
.sub { color:#8b8b96; margin-top:0.35rem; font-size:0.9rem; }
.grid { display:grid; gap:1.25rem; padding:2rem;
        grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); }
.card { background:#16161c; border:1px solid #26262e; border-radius:10px;
        overflow:hidden; display:flex; flex-direction:column; }
.card img { width:100%; aspect-ratio:1; object-fit:cover; display:block;
            background:#222; }
.body { padding:0.8rem 0.9rem 1rem; display:flex; flex-direction:column; gap:0.4rem; }
.title { font-weight:650; font-size:0.98rem; line-height:1.25; }
.artist { color:#a9a9b4; font-size:0.85rem; }
.meta { display:flex; justify-content:space-between; align-items:center;
        font-size:0.78rem; color:#8b8b96; }
.badge { padding:0.1rem 0.45rem; border-radius:999px; font-size:0.7rem;
         text-transform:uppercase; letter-spacing:0.05em;
         background:#26262e; color:#c9c9d4; }
.badge.seed { background:#3d1a12; color:#ff8a6b; }
.score { font-weight:700; color:#ff4d2e; font-variant-numeric:tabular-nums; }
.why { font-size:0.72rem; color:#6f6f7a; }
a.listen { margin-top:0.35rem; text-align:center; text-decoration:none;
           padding:0.45rem; border-radius:6px; background:#ff4d2e;
           color:#0d0d10; font-weight:650; font-size:0.85rem; }
a.listen:hover { background:#ff6a4f; }
.empty { padding:4rem 2rem; text-align:center; color:#8b8b96; }
footer { padding:1rem 2rem 2rem; color:#55555e; font-size:0.75rem; }
"""


def render(store: Store, out_path: Path, limit: int = 100) -> Path:
    releases = store.recent_releases(limit=limit)
    stats = store.stats()
    cards = []
    for r in releases:
        try:
            breakdown = json.loads(r.breakdown) if r.breakdown else {}
        except json.JSONDecodeError:
            breakdown = {}
        why = []
        if breakdown.get("recency"):
            why.append(f"recency +{breakdown['recency']:.0f}")
        if breakdown.get("proximity"):
            why.append(f"proximity +{breakdown['proximity']:.0f}")
        if breakdown.get("keywords"):
            hits = ", ".join(breakdown.get("keyword_hits", []))
            why.append(f"keywords +{breakdown['keywords']:.0f} ({hits})")
        badge = ('<span class="badge seed">seed artist</span>' if breakdown.get("proximity", 0) >= 35
                 else f'<span class="badge">{html.escape(r.record_type)}</span>')
        cover = (f'<img src="{html.escape(r.cover)}" alt="" loading="lazy">'
                 if r.cover else "")
        cards.append(f"""
<div class="card">
  {cover}
  <div class="body">
    <div class="title">{html.escape(r.title)}</div>
    <div class="artist">{html.escape(r.artist_name)}</div>
    <div class="meta"><span>{html.escape(r.release_date)}</span>{badge}</div>
    <div class="meta"><span class="score">{r.score:.1f}</span>
      <span class="why">{html.escape(' · '.join(why))}</span></div>
    <a class="listen" href="{html.escape(r.link)}">Listen on Deezer</a>
  </div>
</div>""")

    body = ("\n".join(cards) if cards
            else '<div class="empty">No releases tracked yet. Run <code>riff-radar scan</code>.</div>')
    doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>riff-radar</title>
<style>{CSS}</style>
</head><body>
<header>
  <h1>riff<span class="accent">-radar</span></h1>
  <div class="sub">{stats['releases']} releases tracked · {stats['artists']} artists ·
    {stats['scans']} scans · generated {date.today().isoformat()}</div>
</header>
<div class="grid">
{body}
</div>
<footer>Scores are explainable: recency (0-40) + artist proximity (0-35) + scene keywords (0-25).</footer>
</body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc)
    return out_path
