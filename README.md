# riff-radar

A new-release radar for metal, post-hardcore, and alt-rock.

Mainstream release radars are built for pop. riff-radar starts from the artists
*you* actually care about, crawls Deezer's related-artist graph, and catches
albums, singles, and EPs the week they drop — scored, deduped, and rendered
into a dark little HTML report you can host anywhere.

No API key. No account. Deezer's public endpoints only.

## Install

```bash
pip install .
# or for hacking:
pip install -e .[dev]
```

Requires Python 3.10+. Runtime dependencies: none (stdlib only).

## Usage

```bash
riff-radar init      # write ~/.config/riff-radar/config.json with sane defaults
riff-radar scan      # crawl the graph, find new releases
riff-radar report    # render ~/.local/share/riff-radar/report.html
riff-radar stats     # quick counters
riff-radar artists   # who's been showing up on the radar
riff-radar track "Knocked Loose"    # add seed artists (no JSON editing)
riff-radar untrack "Sleep Token"    # remove them again
```

Config is plain JSON, editable by hand or via `track`/`untrack`:

```json
{
  "seed_artists": ["Sleep Token", "Spiritbox", "Bad Omens"],
  "keywords": ["metalcore", "post-hardcore", "djent"],
  "window_days": 14,
  "related_per_seed": 10,
  "max_artists_per_scan": 60,
  "skip_record_types": ["compile"],
  "artist_skip_record_types": {"Some Artist": ["single"]}
}
```

`skip_record_types` drops Deezer record types globally ("compile" is where
karaoke, tribute, and reissue noise lives, so it is skipped by default).
`artist_skip_record_types` adds extra skips for one artist only, matched
case-insensitively against the artist name.

## How scoring works

Every release gets 0-100 points, and the report shows the breakdown:

- **Recency (0-40)** — linear decay across your scan window. Dropped today? Full marks.
- **Proximity (0-35)** — a seed artist's own release outranks a related artist's.
- **Keywords (0-25)** — scene words found in the title or artist name, with diminishing returns.

Dedupe is by Deezer album id in a local SQLite DB, so repeat scans stay quiet
unless something genuinely new shows up.

## Automation

Runs fine from cron or a systemd timer:

```cron
0 8 * * *  riff-radar scan --fast && riff-radar report --out /var/www/radar/index.html
```

## Development

```bash
pip install -e .[dev]
pytest
```

The API client is injectable — tests use an in-memory fake, no network needed.

## License

MIT
