from datetime import date, timedelta

from riff_radar.config import Config
from riff_radar.deezer import Artist, Release
from riff_radar.scanner import scan, build_artist_graph, skipped_record_types
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


class CompileClient(FakeClient):
    """Adds compilation noise to the seed artist's releases."""
    def __init__(self):
        super().__init__()
        self.albums[1] = self.albums[1] + [
            make_release(300, "Seed Band", 1, title="Karaoke Hits", rtype="compile"),
        ]


def test_compile_releases_skipped_by_default(tmp_path):
    store = make_store(tmp_path)
    result = scan(CompileClient(), store, make_cfg(), today=TODAY)
    ids = {s.release.id for s in result.new_releases}
    assert ids == {100, 200}  # 300 is a compile, filtered out
    store.close()


def test_custom_skip_record_types(tmp_path):
    store = make_store(tmp_path)
    cfg = make_cfg(skip_record_types=["single"])
    result = scan(FakeClient(), store, cfg, today=TODAY)
    assert result.new_releases == []  # fake releases are all singles
    store.close()


def test_per_artist_skip_only_affects_that_artist(tmp_path):
    store = make_store(tmp_path)
    cfg = make_cfg(skip_record_types=[],
                   artist_skip_record_types={"related act": ["single"]})
    result = scan(FakeClient(), store, cfg, today=TODAY)
    ids = {s.release.id for s in result.new_releases}
    assert ids == {100}  # related act's single skipped, seed's kept
    store.close()


def test_skipped_record_types_merges_global_and_per_artist():
    cfg = make_cfg(skip_record_types=["Compile"],
                   artist_skip_record_types={"Seed Band": ["EP"]})
    assert skipped_record_types(cfg, "seed band") == {"compile", "ep"}
    assert skipped_record_types(cfg, "Someone Else") == {"compile"}


def test_skipped_releases_are_not_stored(tmp_path):
    store = make_store(tmp_path)
    scan(CompileClient(), store, make_cfg(), today=TODAY)
    assert store.stats()["releases"] == 2
    store.close()


class NoiseClient(FakeClient):
    """Adds a tribute act to the related graph and a karaoke release to the seed."""
    def __init__(self):
        super().__init__()
        self.related[1] = self.related[1] + [Artist(3, "Metalcore Tribute Karaoke")]
        self.albums[1] = self.albums[1] + [
            make_release(301, "Seed Band", 2,
                         title="Fresh Drop (Made Famous By Seed Band)"),
        ]
        self.albums[3] = [make_release(302, "Metalcore Tribute Karaoke", 1)]


def test_tribute_related_artists_never_enter_graph():
    graph, _, _ = build_artist_graph(NoiseClient(), make_cfg())
    assert set(graph) == {1, 2}  # artist 3 is tribute noise


def test_noise_titled_releases_skipped(tmp_path):
    store = make_store(tmp_path)
    result = scan(NoiseClient(), store, make_cfg(), today=TODAY)
    ids = {s.release.id for s in result.new_releases}
    assert ids == {100, 200}  # 301 is a "made famous by" title, 302's artist filtered
    assert store.stats()["releases"] == 2
    store.close()


def test_seed_artist_matching_noise_pattern_still_scanned(tmp_path):
    # If the user deliberately seeds a tribute band, respect that.
    client = NoiseClient()
    client.artists["Tribute Kings"] = Artist(9, "Tribute Kings")
    client.albums[9] = [make_release(900, "Tribute Kings", 1)]
    client.related[9] = []
    store = make_store(tmp_path)
    result = scan(client, store, make_cfg(seed_artists=["Tribute Kings"]), today=TODAY)
    assert {s.release.id for s in result.new_releases} == {900}
    store.close()


def test_noise_patterns_are_configurable(tmp_path):
    client = NoiseClient()
    store = make_store(tmp_path)
    cfg = make_cfg(noise_patterns=[])  # filtering disabled
    result = scan(client, store, cfg, today=TODAY)
    ids = {s.release.id for s in result.new_releases}
    assert ids == {100, 200, 301, 302}
    store.close()


def test_is_noise_case_insensitive():
    from riff_radar.scanner import is_noise
    pats = ["tribute", "karaoke", "cover of", "made famous by"]
    assert is_noise("A TRIBUTE to Metal", pats)
    assert is_noise("Karaoke Superhits", pats)
    assert is_noise("Cover of the Month", pats)
    assert is_noise("made famous by someone", pats)
    assert not is_noise("Fresh Metalcore Drop", pats)


def test_since_overrides_configured_window(tmp_path):
    store = make_store(tmp_path)
    since = TODAY - timedelta(days=45)
    result = scan(FakeClient(), store, make_cfg(), today=TODAY, since=since)
    ids = {s.release.id for s in result.new_releases}
    assert ids == {100, 200, 201}  # 201 is 40 days old, inside the since window
    store.close()


def test_since_recency_decays_across_override_window(tmp_path):
    store = make_store(tmp_path)
    since = TODAY - timedelta(days=45)
    result = scan(FakeClient(), store, make_cfg(), today=TODAY, since=since)
    rel200 = next(s for s in result.new_releases if s.release.id == 200)
    # 3 days old in a 45 day window
    assert rel200.breakdown["recency"] == round(40.0 * (1 - 3 / 45), 1)
    store.close()


def test_since_today_finds_nothing_older(tmp_path):
    store = make_store(tmp_path)
    result = scan(FakeClient(), store, make_cfg(), today=TODAY, since=TODAY)
    assert result.new_releases == []  # fake releases are 1+ days old
    store.close()


def test_scan_rejects_invalid_since_date(tmp_path, capsys):
    from riff_radar.cli import main
    rc = main(["--config", str(tmp_path / "missing.json"),
               "scan", "--since", "last-tuesday"])
    assert rc == 2
    assert "invalid --since" in capsys.readouterr().err


def test_result_to_dict_is_json_serializable(tmp_path):
    import json as json_mod
    from riff_radar.scanner import result_to_dict
    store = make_store(tmp_path)
    cfg = make_cfg()
    result = scan(FakeClient(), store, cfg, today=TODAY)
    payload = result_to_dict(result, cfg)
    text = json_mod.dumps(payload)  # must not raise
    assert payload["artists_scanned"] == 2
    assert payload["seed_artists"] == 1
    assert payload["window_days"] == 14
    assert payload["since"] is None
    assert payload["seed_names_missing"] == []
    assert payload["errors"] == []
    releases = payload["new_releases"]
    assert {r["id"] for r in releases} == {100, 200}
    top = releases[0]  # sorted by score, seed release first
    assert top["id"] == 100
    assert top["is_seed_artist"] is True
    assert top["artist"] == "Seed Band"
    assert top["record_type"] == "single"
    assert isinstance(top["score"], float)
    assert isinstance(top["breakdown"], dict)
    assert "recency" in top["breakdown"]
    assert json_mod.loads(text)["new_releases"][0]["id"] == 100
    store.close()


def test_result_to_dict_reflects_since(tmp_path):
    from riff_radar.scanner import result_to_dict
    store = make_store(tmp_path)
    since = TODAY - timedelta(days=45)
    result = scan(FakeClient(), store, make_cfg(), today=TODAY, since=since)
    payload = result_to_dict(result, make_cfg(), since)
    assert payload["since"] == since.isoformat()
    assert {r["id"] for r in payload["new_releases"]} == {100, 200, 201}
    store.close()


def _write_config(tmp_path, **kw):
    import json as json_mod
    cfg = make_cfg(data_dir=str(tmp_path / "data"), **kw)
    path = tmp_path / "config.json"
    path.write_text(json_mod.dumps({
        "seed_artists": cfg.seed_artists,
        "keywords": cfg.keywords,
        "window_days": cfg.window_days,
        "related_per_seed": cfg.related_per_seed,
        "max_artists_per_scan": cfg.max_artists_per_scan,
        "data_dir": cfg.data_dir,
    }))
    return path


def test_scan_json_flag_emits_parseable_json(tmp_path, capsys, monkeypatch):
    import json as json_mod
    import riff_radar.cli as cli
    monkeypatch.setattr(cli, "DeezerClient", lambda delay=0: FakeClient())
    cfg_path = _write_config(tmp_path)
    rc = cli.main(["--config", str(cfg_path), "scan", "--fast", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json_mod.loads(out)  # stdout is pure JSON, no human chatter
    assert payload["artists_scanned"] == 2
    assert {r["id"] for r in payload["new_releases"]} == {100, 200}
    assert payload["errors"] == []


def test_scan_json_flag_empty_window_still_valid(tmp_path, capsys, monkeypatch):
    import json as json_mod
    import riff_radar.cli as cli
    monkeypatch.setattr(cli, "DeezerClient", lambda delay=0: FakeClient())
    cfg_path = _write_config(tmp_path)
    rc = cli.main(["--config", str(cfg_path), "scan", "--fast", "--json",
                   "--since", date.today().isoformat()])
    assert rc == 0
    payload = json_mod.loads(capsys.readouterr().out)
    assert payload["new_releases"] == []
    assert payload["since"] == date.today().isoformat()


def test_scan_without_json_keeps_text_output(tmp_path, capsys, monkeypatch):
    import riff_radar.cli as cli
    monkeypatch.setattr(cli, "DeezerClient", lambda delay=0: FakeClient())
    cfg_path = _write_config(tmp_path)
    rc = cli.main(["--config", str(cfg_path), "scan", "--fast"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "scanned 2 artists" in out
    assert "Seed Band - Fresh Metalcore Drop" in out
