"""Command line interface: scan / report / stats / init / artists."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Config, load, save, add_seeds, remove_seeds, DEFAULT_CONFIG_PATH
from .deezer import DeezerClient
from .digest import render_digest
from .report import render
from .scanner import scan
from .store import Store


def _store(cfg: Config) -> Store:
    return Store(cfg.data_path / "riff-radar.db")


def cmd_init(args) -> int:
    cfg = Config()
    path = save(cfg, Path(args.config) if args.config else None)
    print(f"wrote default config to {path}")
    print("add seed artists with: riff-radar track \"Artist Name\", then: riff-radar scan")
    return 0


def cmd_scan(args) -> int:
    cfg = load(Path(args.config) if args.config else None)
    store = _store(cfg)
    client = DeezerClient(delay=0 if args.fast else 0.15)
    result = scan(client, store, cfg)
    store.close()

    print(f"scanned {result.artists_scanned} artists "
          f"({len(cfg.seed_artists)} seeds + related)")
    if result.seed_names_missing:
        print(f"seeds not found on Deezer: {', '.join(result.seed_names_missing)}")
    if result.errors:
        print(f"errors ({len(result.errors)}):")
        for e in result.errors[:5]:
            print(f"  - {e}")
    if not result.new_releases:
        print("no new releases in window. quiet week.")
        return 0
    print(f"\n{len(result.new_releases)} new release(s):\n")
    for s in result.new_releases:
        tag = "*" if s.is_seed_artist else " "
        r = s.release
        print(f" {tag} {s.score:5.1f}  {r.artist_name} - {r.title}")
        print(f"        {r.record_type} · {r.release_date} · {r.link}")
    return 0


def cmd_report(args) -> int:
    cfg = load(Path(args.config) if args.config else None)
    store = _store(cfg)
    out = Path(args.out) if args.out else cfg.data_path / "report.html"
    path = render(store, out, limit=args.limit)
    store.close()
    print(f"report written to {path}")
    return 0


def cmd_digest(args) -> int:
    cfg = load(Path(args.config) if args.config else None)
    store = _store(cfg)
    print(render_digest(store, cfg, days=args.days), end="")
    store.close()
    return 0


def cmd_stats(args) -> int:
    cfg = load(Path(args.config) if args.config else None)
    store = _store(cfg)
    stats = store.stats()
    store.close()
    print(f"releases tracked: {stats['releases']}")
    print(f"artists seen:     {stats['artists']}")
    print(f"scans run:        {stats['scans']}")
    return 0


def cmd_artists(args) -> int:
    cfg = load(Path(args.config) if args.config else None)
    store = _store(cfg)
    rows = store.conn.execute(
        "SELECT artist_name, COUNT(*) c FROM releases "
        "GROUP BY artist_name ORDER BY c DESC").fetchall()
    store.close()
    for r in rows:
        print(f"{r['c']:4d}  {r['artist_name']}")
    return 0


def _config_path(args) -> Path | None:
    return Path(args.config) if args.config else None


def cmd_track(args) -> int:
    cfg = load(_config_path(args))
    added, skipped = add_seeds(cfg, args.names)
    if added:
        save(cfg, _config_path(args))
        print(f"tracking: {', '.join(added)}")
    if skipped:
        print(f"already tracked: {', '.join(skipped)}")
    print(f"seed artists ({len(cfg.seed_artists)}): {', '.join(cfg.seed_artists)}")
    return 0


def cmd_untrack(args) -> int:
    cfg = load(_config_path(args))
    removed, not_found = remove_seeds(cfg, args.names)
    if removed:
        save(cfg, _config_path(args))
        print(f"untracked: {', '.join(removed)}")
    for name in not_found:
        print(f"not a seed artist: {name}")
    print(f"seed artists ({len(cfg.seed_artists)}): {', '.join(cfg.seed_artists)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="riff-radar",
        description="New-release radar for metal, post-hardcore, and alt-rock.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", help=f"config path (default {DEFAULT_CONFIG_PATH})")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="write a default config file")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("scan", help="scan for new releases")
    sp.add_argument("--fast", action="store_true",
                    help="skip the polite delay between API calls")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("report", help="render the HTML report")
    sp.add_argument("--out", help="output path (default <data_dir>/report.html)")
    sp.add_argument("--limit", type=int, default=100)
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("stats", help="show tracking stats")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("digest", help="plain-text summary of recent finds")
    sp.add_argument("--days", type=int, default=7,
                    help="how far back to look (default 7)")
    sp.set_defaults(func=cmd_digest)

    sp = sub.add_parser("artists", help="list artists seen, most releases first")
    sp.set_defaults(func=cmd_artists)

    sp = sub.add_parser("track", help="add seed artists to the config")
    sp.add_argument("names", nargs="+", help="artist names to track")
    sp.set_defaults(func=cmd_track)

    sp = sub.add_parser("untrack", help="remove seed artists from the config")
    sp.add_argument("names", nargs="+", help="artist names to stop tracking")
    sp.set_defaults(func=cmd_untrack)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
