# riff-radar roadmap

Working list for iteration. Each cron run: pick the highest-priority unchecked
item, implement it fully (with tests), update this file, commit, push.

Priority order is top-to-bottom within a section. When a section is done, move
to the next. When everything is done, invent the next section and keep going.

## v0.2 — smarter radar

- [x] `track`/`untrack` CLI commands to manage seed artists without editing JSON
- [x] per-artist release type filter (skip "compile" and karaoke/tribute noise)
- [ ] tribute/karaoke detection: filter artist names containing "tribute", "karaoke", "cover of", "made famous by"
- [ ] `riff-radar digest` — plain-text summary of the week's finds, suitable for piping into email or a chat message
- [ ] `--since` flag on scan to override the window ad hoc
- [ ] JSON output mode for scan (`--json`) for scripting

## v0.3 — better report

- [ ] collapsible score-breakdown tooltip on each card
- [ ] filter buttons: all / seed artists only / singles only / albums only
- [ ] dark/light toggle
- [ ] "new since last report" highlight banner
- [ ] favicon + Open Graph meta tags
- [ ] RSS feed generation alongside the HTML report

## v0.4 — deeper discovery

- [ ] two-hop related-artist crawl (related of related), capped + deduped
- [ ] artist blacklist in config (never show these)
- [ ] genre-aware scoring via Deezer genre endpoint on albums
- [ ] popularity signal: use Deezer fans count on artists to weight proximity
- [ ] release-type aware recency (albums stay "new" longer than singles)

## v0.5 — polish & packaging

- [ ] GitHub Actions CI: pytest on 3.10-3.13
- [ ] type checking with mypy, lint with ruff
- [ ] Dockerfile / container image
- [ ] publish to PyPI
- [ ] man page / rich --help examples
- [ ] CHANGELOG.md automation from conventional commits

## Housekeeping rules for the iterating agent

1. Never break `pytest`. Run it before every commit.
2. Keep the runtime stdlib-only. Dev dependencies are fine.
3. Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`.
4. Update README when behavior changes.
5. Check the box in this file when an item ships.
6. One item per run, done properly, beats three items done halfway.
