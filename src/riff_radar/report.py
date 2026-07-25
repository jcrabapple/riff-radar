"""Static HTML report: dark theme, cover grid, explainable scores."""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

from .scoring import KEYWORD_MAX, PROXIMITY_SEED, RECENCY_MAX
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
details.breakdown { font-size:0.75rem; color:#8b8b96; }
details.breakdown summary { cursor:pointer; color:#a9a9b4; font-size:0.75rem;
                            list-style:none; user-select:none; }
details.breakdown summary::before { content:"\\25B8 "; color:#ff4d2e; }
details.breakdown[open] summary::before { content:"\\25BE "; }
details.breakdown summary:hover { color:#e8e6e3; }
.breakdown .row { display:grid; grid-template-columns:4.5rem 1fr 2.6rem;
                  align-items:center; gap:0.5rem; padding:0.15rem 0;
                  font-variant-numeric:tabular-nums; }
.breakdown .track { height:5px; background:#26262e; border-radius:3px;
                    overflow:hidden; }
.breakdown .fill { height:100%; background:#ff4d2e; border-radius:3px; }
.breakdown .hits { padding-top:0.25rem; color:#6f6f7a; font-size:0.7rem; }
a.listen { margin-top:0.35rem; text-align:center; text-decoration:none;
           padding:0.45rem; border-radius:6px; background:#ff4d2e;
           color:#0d0d10; font-weight:650; font-size:0.85rem; }
a.listen:hover { background:#ff6a4f; }
.filters { display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;
           padding:1rem 2rem 0; }
.filters button { background:#16161c; color:#c9c9d4; border:1px solid #26262e;
                  border-radius:999px; padding:0.35rem 0.9rem; font-size:0.8rem;
                  cursor:pointer; }
.filters button:hover { border-color:#ff4d2e; color:#e8e6e3; }
.filters button.active { background:#ff4d2e; border-color:#ff4d2e;
                         color:#0d0d10; font-weight:650; }
.filters .count { color:#55555e; font-size:0.75rem; margin-left:auto; }
.card.hidden { display:none; }
.empty { padding:4rem 2rem; text-align:center; color:#8b8b96; }
footer { padding:1rem 2rem 2rem; color:#55555e; font-size:0.75rem; }
"""

JS = """
const buttons = document.querySelectorAll('.filters button');
const cards = document.querySelectorAll('.card');
const count = document.querySelector('.filters .count');
function applyFilter(filter) {
  let shown = 0;
  cards.forEach(card => {
    const seed = card.dataset.seed === '1';
    const type = card.dataset.type;
    const show = filter === 'all'
      || (filter === 'seed' && seed)
      || (filter === 'single' && type === 'single')
      || (filter === 'album' && (type === 'album' || type === 'ep'));
    card.classList.toggle('hidden', !show);
    if (show) shown += 1;
  });
  if (count) count.textContent = 'showing ' + shown + ' of ' + cards.length;
}
buttons.forEach(btn => btn.addEventListener('click', () => {
  buttons.forEach(b => b.classList.toggle('active', b === btn));
  applyFilter(btn.dataset.filter);
}));
applyFilter('all');
"""


def _bar_row(label: str, value: float, maximum: float) -> str:
    pct = max(0.0, min(100.0, 100.0 * value / maximum)) if maximum else 0.0
    return (f'<div class="row"><span>{label}</span>'
            f'<span class="track"><span class="fill" style="width:{pct:.0f}%"></span></span>'
            f'<span>+{value:.0f}</span></div>')


def _breakdown_html(breakdown: dict) -> str:
    """Collapsible per-component score breakdown for a card."""
    rows = [
        _bar_row("recency", float(breakdown.get("recency", 0)), RECENCY_MAX),
        _bar_row("proximity", float(breakdown.get("proximity", 0)), PROXIMITY_SEED),
        _bar_row("keywords", float(breakdown.get("keywords", 0)), KEYWORD_MAX),
    ]
    hits = breakdown.get("keyword_hits") or []
    hits_html = (f'<div class="hits">matched: {html.escape(", ".join(hits))}</div>'
                 if hits else "")
    return ('<details class="breakdown"><summary>score breakdown</summary>'
            + "".join(rows) + hits_html + "</details>")


def body_html(store: Store, limit: int = 100) -> str:
    """Filters bar + card grid, shared by the static report and the web UI."""
    releases = store.recent_releases(limit=limit)
    cards = []
    for r in releases:
        try:
            breakdown = json.loads(r.breakdown) if r.breakdown else {}
        except json.JSONDecodeError:
            breakdown = {}
        is_seed = breakdown.get("proximity", 0) >= 35
        badge = ('<span class="badge seed">seed artist</span>' if is_seed
                 else f'<span class="badge">{html.escape(r.record_type)}</span>')
        cover = (f'<img src="{html.escape(r.cover)}" alt="" loading="lazy">'
                 if r.cover else "")
        cards.append(f"""
<div class="card" data-seed="{1 if is_seed else 0}" data-type="{html.escape(r.record_type)}">
  {cover}
  <div class="body">
    <div class="title">{html.escape(r.title)}</div>
    <div class="artist">{html.escape(r.artist_name)}</div>
    <div class="meta"><span>{html.escape(r.release_date)}</span>{badge}</div>
    <div class="meta"><span class="score">{r.score:.1f}</span></div>
    {_breakdown_html(breakdown)}
    <a class="listen" href="{html.escape(r.link)}">Listen on Deezer</a>
  </div>
</div>""")

    body = ("\n".join(cards) if cards
            else '<div class="empty">No releases tracked yet. Run <code>riff-radar scan</code>.</div>')
    filters = ""
    if cards:
        filters = """
<div class="filters">
  <button class="active" data-filter="all">All</button>
  <button data-filter="seed">Seed artists</button>
  <button data-filter="single">Singles</button>
  <button data-filter="album">Albums</button>
  <span class="count"></span>
</div>"""
    return filters + '\n<div class="grid">\n' + body + '\n</div>'


def render(store: Store, out_path: Path, limit: int = 100) -> Path:
    stats = store.stats()
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
{body_html(store, limit)}
<footer>Scores are explainable: recency (0-40) + artist proximity (0-35) + scene keywords (0-25).</footer>
<script>{JS}</script>
</body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc)
    return out_path
