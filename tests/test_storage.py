from datetime import datetime

import pytest

from src.models import MatchResult, RawProduct, TrackingRule
from src.storage import Storage


@pytest.fixture
def store():
    return Storage(":memory:")


def _rule(key):
    return TrackingRule(
        key=key,
        label=key.upper(),
        quantity=1,
        baseline_price=1000,
        match_all=[key],
        exclude=[],
    )


def _match(rule, price, value="1", mode="keyword"):
    raw = (
        None
        if mode == "not_found"
        else RawProduct(
            option_value=value,
            option_text=f"{rule.key} $ {price}",
            price=price,
            optgroup=None,
        )
    )
    return MatchResult(
        rule=rule,
        raw=raw,
        mode=mode,
        confidence=1.0 if mode != "not_found" else 0.0,
    )


def test_schema_is_created_on_init(store):
    cur = store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "runs" in tables
    assert "snapshots" in tables


def test_record_run_and_snapshots(store):
    run_id = store.record_run_start(datetime(2026, 4, 21, 1, 0))
    assert run_id > 0

    matches = [
        _match(_rule("cpu"), 6490),
        _match(_rule("mb"), 3990),
    ]
    store.record_snapshots(run_id, matches)
    store.record_run_end(run_id, datetime(2026, 4, 21, 1, 0, 10), "ok", 1500)

    cur = store.conn.execute(
        "SELECT rule_key, price, match_mode FROM snapshots WHERE run_id=? ORDER BY rule_key",
        (run_id,),
    )
    rows = cur.fetchall()
    assert rows == [("cpu", 6490, "keyword"), ("mb", 3990, "keyword")]


def test_not_found_stored_as_null_price(store):
    run_id = store.record_run_start(datetime(2026, 4, 21))
    store.record_snapshots(run_id, [_match(_rule("cpu"), 0, mode="not_found")])

    cur = store.conn.execute("SELECT price, match_mode FROM snapshots")
    row = cur.fetchone()
    assert row[0] is None
    assert row[1] == "not_found"


def test_query_last_price_before_today(store):
    r1 = store.record_run_start(datetime(2026, 4, 20, 1, 0))
    store.record_snapshots(r1, [_match(_rule("cpu"), 6490)])
    store.record_run_end(r1, datetime(2026, 4, 20, 1, 0, 5), "ok", 1500)

    r2 = store.record_run_start(datetime(2026, 4, 21, 1, 0))
    store.record_snapshots(r2, [_match(_rule("cpu"), 6390)])
    store.record_run_end(r2, datetime(2026, 4, 21, 1, 0, 5), "ok", 1500)

    yesterday = store.query_last_price_before("cpu", datetime(2026, 4, 21, 0, 0))
    assert yesterday == 6490


def test_query_low_over_window(store):
    prices = [6500, 6450, 6400, 6500, 6390]
    for i, p in enumerate(prices):
        ts = datetime(2026, 4, 17 + i, 1, 0)
        run_id = store.record_run_start(ts)
        store.record_snapshots(run_id, [_match(_rule("cpu"), p)])
        store.record_run_end(run_id, ts, "ok", 1500)

    low = store.query_low("cpu", datetime(2026, 4, 17), datetime(2026, 4, 21, 23, 59))
    assert low == 6390


def test_query_low_returns_none_when_all_null(store):
    run_id = store.record_run_start(datetime(2026, 4, 21))
    store.record_snapshots(run_id, [_match(_rule("cpu"), 0, mode="not_found")])

    low = store.query_low("cpu", datetime(2026, 4, 1), datetime(2026, 4, 30))
    assert low is None


def _record_day(store, day, prices_by_key, status="ok"):
    """Write a (run, snapshots) tuple on `day` with given prices."""
    rid = store.record_run_start(day)
    matches = [_match(_rule(k), p) for k, p in prices_by_key.items()]
    store.record_snapshots(rid, matches)
    store.record_run_end(rid, day, status, 1500)


def test_query_total_history_aggregates_per_day(store):
    quantities = {"cpu": 1, "ssd": 2}
    _record_day(store, datetime(2026, 4, 20, 1, 0), {"cpu": 6500, "ssd": 9000})
    _record_day(store, datetime(2026, 4, 21, 1, 0), {"cpu": 6490, "ssd": 9100})

    history = store.query_total_history(
        quantities,
        datetime(2026, 4, 1),
        datetime(2026, 4, 30),
    )
    assert history == [
        ("2026-04-20", 6500 + 9000 * 2),
        ("2026-04-21", 6490 + 9100 * 2),
    ]


def test_query_total_history_skips_days_with_missing_rule(store):
    quantities = {"cpu": 1, "mb": 1}
    _record_day(store, datetime(2026, 4, 20, 1, 0), {"cpu": 6500})  # mb missing
    _record_day(store, datetime(2026, 4, 21, 1, 0), {"cpu": 6490, "mb": 3990})

    history = store.query_total_history(
        quantities,
        datetime(2026, 4, 1),
        datetime(2026, 4, 30),
    )
    assert history == [("2026-04-21", 6490 + 3990)]


def test_query_total_history_ignores_failed_runs(store):
    quantities = {"cpu": 1}
    _record_day(store, datetime(2026, 4, 20, 1, 0), {"cpu": 6500}, status="failed")
    _record_day(store, datetime(2026, 4, 21, 1, 0), {"cpu": 6490}, status="ok")

    history = store.query_total_history(
        quantities,
        datetime(2026, 4, 1),
        datetime(2026, 4, 30),
    )
    assert history == [("2026-04-21", 6490)]


def test_query_total_history_uses_latest_run_per_day(store):
    quantities = {"cpu": 1}
    _record_day(store, datetime(2026, 4, 20, 1, 0), {"cpu": 6500})
    _record_day(store, datetime(2026, 4, 20, 10, 0), {"cpu": 6400})

    history = store.query_total_history(
        quantities,
        datetime(2026, 4, 1),
        datetime(2026, 4, 30),
    )
    assert history == [("2026-04-20", 6400)]
