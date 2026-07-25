from datetime import date

from riff_radar.config import Config
from riff_radar.digest import render_digest
from riff_radar.store import Store
from riff_radar.deezer import Release

TODAY = date(2026, 7, 25)


def _release(rid, title, artist, rtype="album"):
    return Release(id=rid, title=title, artist_id=rid, artist_name=artist,
                   release_date="2026-07-20", record_type=rtype,
                   link=f"https://deezer.com/album/{rid}", cover="")


def _store(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_release(_release(1, "Seed Album", "Sleep Token"),
                      90.0, "{}", "2026-07-24T08:00:00")
    store.add_release(_release(2, "Related Single", "New Band", "single"),
                      55.5, "{}", "2026-07-23T08:00:00")
    store.add_release(_release(3, "Old One", "Sleep Token"),
                      80.0, "{}", "2026-07-01T08:00:00")
    store.commit()
    return store


def test_digest_lists_recent_finds(tmp_path):
    store = _store(tmp_path)
    text = render_digest(store, Config(), days=7, today=TODAY)
    assert "riff-radar digest, 2026-07-18 to 2026-07-25 (7 days)" in text
    assert "2 new release(s), 1 from seed artists" in text
    assert "Sleep Token - Seed Album (album, 2026-07-20)" in text
    assert "New Band - Related Single (single, 2026-07-20)" in text
    assert "Old One" not in text
    assert "https://deezer.com/album/1" in text
    store.close()


def test_digest_splits_seed_artists_from_discoveries(tmp_path):
    store = _store(tmp_path)
    text = render_digest(store, Config(seed_artists=["Sleep Token"]),
                         days=7, today=TODAY)
    seed_section = text.split("\nseed artists\n")[1].split("\ndiscoveries\n")[0]
    assert "*  90.0  Sleep Token" in seed_section
    disco_section = text.split("discoveries")[1]
    assert "New Band" in disco_section
    assert "Sleep Token" not in disco_section
    store.close()


def test_digest_empty_state(tmp_path):
    store = Store(tmp_path / "t.db")
    text = render_digest(store, Config(), days=7, today=TODAY)
    assert "no new releases. quiet week." in text
    store.close()


def test_digest_days_window_respected(tmp_path):
    store = _store(tmp_path)
    text = render_digest(store, Config(), days=30, today=TODAY)
    assert "3 new release(s)" in text
    assert "Old One" in text
    store.close()


def test_digest_seed_match_is_case_insensitive(tmp_path):
    store = _store(tmp_path)
    text = render_digest(store, Config(seed_artists=["sleep token"]),
                         days=7, today=TODAY)
    assert "1 from seed artists" in text
    store.close()
