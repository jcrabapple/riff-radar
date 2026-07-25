import json

from riff_radar.cli import main
from riff_radar.config import Config, add_seeds, load, remove_seeds, save


def make_cfg(**kw):
    base = dict(seed_artists=["Sleep Token", "Spiritbox"])
    base.update(kw)
    return Config(**base)


def test_add_seeds_appends_new():
    cfg = make_cfg()
    added, skipped = add_seeds(cfg, ["Bad Omens"])
    assert added == ["Bad Omens"]
    assert skipped == []
    assert cfg.seed_artists[-1] == "Bad Omens"


def test_add_seeds_dedupes_case_insensitively():
    cfg = make_cfg()
    added, skipped = add_seeds(cfg, ["sleep token", "SLEEP TOKEN"])
    assert added == []
    assert skipped == ["sleep token", "SLEEP TOKEN"]
    assert cfg.seed_artists == ["Sleep Token", "Spiritbox"]


def test_add_seeds_strips_and_ignores_blank():
    cfg = make_cfg()
    added, skipped = add_seeds(cfg, ["  Knocked Loose  ", "   "])
    assert added == ["Knocked Loose"]
    assert skipped == []


def test_remove_seeds_case_insensitive():
    cfg = make_cfg()
    removed, not_found = remove_seeds(cfg, ["spiritbox"])
    assert removed == ["Spiritbox"]
    assert not_found == []
    assert cfg.seed_artists == ["Sleep Token"]


def test_remove_seeds_reports_missing():
    cfg = make_cfg()
    removed, not_found = remove_seeds(cfg, ["Nickelback"])
    assert removed == []
    assert not_found == ["Nickelback"]


def test_track_cli_writes_config(tmp_path, capsys):
    path = tmp_path / "config.json"
    save(make_cfg(), path)
    rc = main(["--config", str(path), "track", "Bad Omens"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tracking: Bad Omens" in out
    assert "Bad Omens" in load(path).seed_artists


def test_track_cli_idempotent(tmp_path, capsys):
    path = tmp_path / "config.json"
    save(make_cfg(), path)
    main(["--config", str(path), "track", "Sleep Token"])
    out = capsys.readouterr().out
    assert "already tracked: Sleep Token" in out
    assert load(path).seed_artists.count("Sleep Token") == 1


def test_track_cli_creates_config_if_missing(tmp_path, capsys):
    path = tmp_path / "fresh" / "config.json"
    rc = main(["--config", str(path), "track", "Loathe"])
    assert rc == 0
    cfg = load(path)
    assert "Loathe" in cfg.seed_artists
    # Defaults still present around it.
    assert "Sleep Token" in cfg.seed_artists


def test_untrack_cli_removes_and_saves(tmp_path, capsys):
    path = tmp_path / "config.json"
    save(make_cfg(), path)
    rc = main(["--config", str(path), "untrack", "spiritbox", "Nickelback"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "untracked: Spiritbox" in out
    assert "not a seed artist: Nickelback" in out
    assert load(path).seed_artists == ["Sleep Token"]


def test_untrack_cli_does_not_save_when_nothing_removed(tmp_path, capsys):
    path = tmp_path / "config.json"
    save(make_cfg(), path)
    before = json.loads(path.read_text())
    main(["--config", str(path), "untrack", "Nickelback"])
    assert json.loads(path.read_text()) == before
