from datetime import date, timedelta

from riff_radar.scoring import (
    RECENCY_MAX, KEYWORD_MAX,
    parse_date, recency_score, keyword_hits, keyword_score, score_release,
)

TODAY = date(2026, 7, 24)


def test_parse_date_valid():
    assert parse_date("2026-07-20") == date(2026, 7, 20)


def test_parse_date_garbage():
    assert parse_date("0000-00-00") is None
    assert parse_date("not-a-date") is None
    assert parse_date("") is None


def test_recency_today_is_max():
    assert recency_score(TODAY, TODAY, 14) == RECENCY_MAX


def test_recency_future_is_max():
    assert recency_score(TODAY + timedelta(days=7), TODAY, 14) == RECENCY_MAX


def test_recency_decays_to_zero_outside_window():
    assert recency_score(TODAY - timedelta(days=15), TODAY, 14) == 0.0


def test_recency_monotonic():
    scores = [recency_score(TODAY - timedelta(days=d), TODAY, 14) for d in range(15)]
    assert all(a >= b for a, b in zip(scores, scores[1:]))


def test_keyword_hits_case_insensitive():
    hits = keyword_hits("METALCORE anthem", ["metalcore"])
    assert hits == ["metalcore"]


def test_keyword_score_capped():
    assert keyword_score("metal metalcore hardcore djent emo",
                         ["metal", "metalcore", "hardcore", "djent", "emo"]) <= KEYWORD_MAX


def test_score_breakdown_sums_to_total():
    total, parts = score_release(
        TODAY - timedelta(days=2), "New Metal Single", "Some Band",
        is_seed=True, is_related=False,
        keywords=["metal"], today=TODAY, window_days=14,
    )
    assert abs(total - (parts["recency"] + parts["proximity"] + parts["keywords"])) < 0.2


def test_seed_beats_related():
    seed, _ = score_release(TODAY, "X", "Y", is_seed=True, is_related=False,
                            keywords=[], today=TODAY, window_days=14)
    rel, _ = score_release(TODAY, "X", "Y", is_seed=False, is_related=True,
                           keywords=[], today=TODAY, window_days=14)
    assert seed > rel
