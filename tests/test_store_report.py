from riff_radar.report import render
from riff_radar.store import Store
from riff_radar.deezer import Release


def test_store_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    rel = Release(id=1, title="T", artist_id=1, artist_name="A",
                  release_date="2026-07-01", record_type="album",
                  link="https://x", cover="")
    store.add_release(rel, 55.0, '{"recency": 30}', "2026-07-24T00:00:00")
    store.record_scan("2026-07-24T00:00:00", 5, 1)
    store.commit()
    assert store.seen_ids() == {1}
    assert store.stats()["releases"] == 1
    assert store.recent_releases()[0].title == "T"
    store.close()


def test_report_renders_release(tmp_path):
    store = Store(tmp_path / "t.db")
    rel = Release(id=2, title="Report Me", artist_id=1, artist_name="Band",
                  release_date="2026-07-20", record_type="single",
                  link="https://deezer.com/album/2", cover="")
    store.add_release(rel, 61.5, '{"recency": 40, "proximity": 35}', "2026-07-24T00:00:00")
    store.commit()
    out = render(store, tmp_path / "report.html")
    html = out.read_text()
    assert "Report Me" in html
    assert "61.5" in html
    assert "Listen on Deezer" in html
    store.close()


def test_report_empty_state(tmp_path):
    store = Store(tmp_path / "t.db")
    out = render(store, tmp_path / "report.html")
    assert "No releases tracked yet" in out.read_text()
    store.close()


def test_report_score_breakdown_collapsible(tmp_path):
    store = Store(tmp_path / "t.db")
    rel = Release(id=3, title="Breakdown Me", artist_id=1, artist_name="Band",
                  release_date="2026-07-20", record_type="album",
                  link="https://deezer.com/album/3", cover="")
    breakdown = ('{"recency": 40, "proximity": 35, "keywords": 12,'
                 ' "keyword_hits": ["metal"]}')
    store.add_release(rel, 87.0, breakdown, "2026-07-24T00:00:00")
    store.commit()
    html = render(store, tmp_path / "report.html").read_text()
    assert '<details class="breakdown">' in html
    assert "<summary>score breakdown</summary>" in html
    # recency 40/40 is a full bar, keywords 12/25 is roughly half
    assert 'style="width:100%"' in html
    assert 'style="width:48%"' in html
    assert "matched: metal" in html
    store.close()


def test_report_breakdown_handles_missing_data(tmp_path):
    store = Store(tmp_path / "t.db")
    rel = Release(id=4, title="No Breakdown", artist_id=1, artist_name="Band",
                  release_date="2026-07-20", record_type="single",
                  link="https://deezer.com/album/4", cover="")
    store.add_release(rel, 10.0, "", "2026-07-24T00:00:00")
    store.commit()
    html = render(store, tmp_path / "report.html").read_text()
    assert '<details class="breakdown">' in html
    assert 'style="width:0%"' in html
    assert "matched:" not in html
    store.close()
