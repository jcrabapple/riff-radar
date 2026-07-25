from datetime import date, timedelta

from riff_radar.config import Config
from riff_radar.deezer import Artist, Release
from riff_radar.scanner import scan, build_artist_graph
from riff_radar.store import Store

TODAY = date(2026, 7, 24)


def make_release(rid, artist, days_old, title="Song", rtype="single"):
    return Release(
        id=rid, title=title, artist_id=rid * 10, artist_name=artist,
        release_date=(TODAY - timedelta(days=days_old)).isoformat(),
        record_type=rtype, link=f"https://deezer.com/album/{rid}", cover="",
    )


class FakeClient:
    """In-memory Deezer stand-in."""
    def __init__(self):
        self.artists = {"Seed Band": Artist(1, "Seed Band")}
        self.related = {1: [Artist(2, "Related Act")]}
        self.albums = {
            1: [make_release(100, "Seed Band", 1, title="Fresh Metalcore Drop")],
            2: [
                make_release(200, "Related Act", 3),
                make_release(201, "Related Act", 40, title="Old News"),
            ],
        }

    def search_artist(self, name):
        return self.artists.get(name)

    def related_artists(self, artist_id, limit=10):
        return self.related.get(artist_id, [])[:limit]

    def artist_releases(self, artist_id, limit=25, artist_name=""):
        releases = self.albums.get(artist_id, [])
        if artist_name:
            for r in releases:
                r.artist_name = r.artist_name or artist_name
        return releases


def make_store(tmp_path):
    return Store(tmp_path / "test.db")


def make_cfg(**kw):
    base = dict(seed_artists=["Seed Band"], keywords=["metalcore"],
                window_days=14, related_per_seed=5, max_artists_per_scan=10,
                data_dir="/tmp/unused")
    base.update(kw)
    return Config(**base)


def test_graph_contains_seed_and_related(tmp_path):
    graph, missing, errors = build_artist_graph(FakeClient(), make_cfg())
    assert graph[1][1] is True   # seed flag
    assert graph[2][1] is False  # related
    assert missing == [] and errors == []


def test_missing_seed_reported(tmp_path):
    graph, missing, _ = build_artist_graph(FakeClient(), make_cfg(seed_artists=["Nope"]))
    assert missing == ["Nope"]


def test_scan_finds_new_in_window_only(tmp_path):
    store = make_store(tmp_path)
    result = scan(FakeClient(), store, make_cfg(), today=TODAY)
    ids = {s.release.id for s in result.new_releases}
    assert ids == {100, 200}  # 201 is 40 days old, outside window
    store.close()


def test_scan_dedupes_on_second_run(tmp_path):
    store = make_store(tmp_path)
    scan(FakeClient(), store, make_cfg(), today=TODAY)
    result2 = scan(FakeClient(), store, make_cfg(), today=TODAY)
    assert result2.new_releases == []
    store.close()


def test_seed_release_outranks_related(tmp_path):
    store = make_store(tmp_path)
    result = scan(FakeClient(), store, make_cfg(), today=TODAY)
    top = result.new_releases[0]
    assert top.release.id == 100
    assert top.is_seed_artist
    store.close()


def test_scan_records_history(tmp_path):
    store = make_store(tmp_path)
    scan(FakeClient(), store, make_cfg(), today=TODAY)
    stats = store.stats()
    assert stats["scans"] == 1
    assert stats["releases"] == 2
    store.close()
