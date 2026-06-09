from datetime import datetime

from src.config import AppConfig, Baseline
from src.diff import build_daily_report
from src.models import MatchResult, RawProduct, TrackingRule
from src.storage import Storage


def _rule(key, qty=1, baseline=1000):
    return TrackingRule(
        key=key, label=key.upper(), quantity=qty, baseline_price=baseline,
        match_all=[key], exclude=[],
    )


def _match_for(rule, price):
    raw = RawProduct(
        option_value="x", option_text=f"{rule.key} $ {price}",
        price=price, optgroup=None,
    )
    return MatchResult(rule=rule, raw=raw, mode="keyword", confidence=1.0)


def _not_found(rule):
    return MatchResult(rule=rule, raw=None, mode="not_found", confidence=0.0)


def _seed_history(store, rule_key, prices_by_day):
    for ts, price in prices_by_day.items():
        run_id = store.record_run_start(ts)
        if price is None:
            store.conn.execute(
                "INSERT INTO snapshots (run_id, rule_key, match_mode, price) "
                "VALUES (?, ?, 'not_found', NULL)",
                (run_id, rule_key),
            )
            store.conn.commit()
        else:
            raw = RawProduct(option_value="x", option_text="x", price=price, optgroup=None)
            rule = TrackingRule(
                key=rule_key, label=rule_key, quantity=1, baseline_price=1000,
                match_all=[rule_key], exclude=[],
            )
            m = MatchResult(rule=rule, raw=raw, mode="keyword", confidence=1.0)
            store.record_snapshots(run_id, [m])
        store.record_run_end(run_id, ts, "ok", 1500)


def test_delta_yesterday_is_today_minus_yesterday_single_rule():
    store = Storage(":memory:")
    _seed_history(store, "cpu", {datetime(2026, 4, 20, 1, 0): 6490})

    rule = _rule("cpu", baseline=6490)
    today = [_match_for(rule, 6390)]
    cfg = AppConfig(
        baseline=Baseline(date="2026-02-24", notes=""),
        rules=[rule],
    )

    report = build_daily_report(
        cfg=cfg, matches=today, store=store, now=datetime(2026, 4, 21, 1, 0),
    )
    item = report.items[0]
    assert item.today_price == 6390
    assert item.yesterday_price == 6490
    assert item.delta_yesterday_abs == -100
    assert item.delta_baseline_abs == -100


def test_line_total_equals_price_times_quantity():
    store = Storage(":memory:")
    rule = _rule("ssd", qty=2, baseline=9500)
    today = [_match_for(rule, 9500)]
    cfg = AppConfig(
        baseline=Baseline(date="2026-02-24", notes=""),
        rules=[rule],
    )
    report = build_daily_report(cfg=cfg, matches=today, store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    item = report.items[0]
    assert item.today_line_total == 19000


def test_is_7d_low_when_below_past_7d_min():
    store = Storage(":memory:")
    history = {
        datetime(2026, 4, 15, 1, 0): 6500,
        datetime(2026, 4, 16, 1, 0): 6450,
        datetime(2026, 4, 17, 1, 0): 6420,
        datetime(2026, 4, 18, 1, 0): 6400,
        datetime(2026, 4, 19, 1, 0): 6450,
        datetime(2026, 4, 20, 1, 0): 6500,
    }
    _seed_history(store, "cpu", history)

    rule = _rule("cpu", baseline=6490)
    today = [_match_for(rule, 6390)]
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""), rules=[rule])

    report = build_daily_report(cfg=cfg, matches=today, store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    assert report.items[0].is_7d_low is True


def test_not_found_item_in_report():
    store = Storage(":memory:")
    rule = _rule("cpu", baseline=6490)
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""), rules=[rule])

    report = build_daily_report(
        cfg=cfg, matches=[_not_found(rule)], store=store,
        now=datetime(2026, 4, 21, 1, 0),
    )
    item = report.items[0]
    assert item.not_found is True
    assert item.today_price is None
    assert item.today_line_total is None
    assert "cpu" in report.missing_item_keys
    # spec §8.1: not_found must enter fetcher_warnings to trigger banner
    assert any("cpu" in w for w in report.fetcher_warnings)


def test_total_today_skips_not_found_items():
    store = Storage(":memory:")
    cpu = _rule("cpu", baseline=6490)
    mb = _rule("mb", baseline=3990)
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""),
                    rules=[cpu, mb])
    matches = [_match_for(cpu, 6390), _not_found(mb)]

    report = build_daily_report(cfg=cfg, matches=matches, store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    assert report.total_today == 6390


def test_total_baseline_sums_all_items():
    store = Storage(":memory:")
    cpu = _rule("cpu", baseline=6490)
    mb = _rule("mb", baseline=3990)
    ssd = _rule("ssd", qty=2, baseline=9500)
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""),
                    rules=[cpu, mb, ssd])
    matches = [_match_for(cpu, 6490), _match_for(mb, 3990), _match_for(ssd, 9500)]

    report = build_daily_report(cfg=cfg, matches=matches, store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    assert report.total_baseline == 29480


def test_low_confidence_logs_but_stays_out_of_email(caplog):
    """Match-machinery diagnostics (low confidence / hint fallback) are
    operational noise the user can't act on — they go to the log, not the
    email. So item.warning stays None and fetcher_warnings excludes them."""
    store = Storage(":memory:")
    cpu = _rule("cpu", baseline=6490)
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""), rules=[cpu])

    raw = RawProduct(option_value="x", option_text="AMD $6490", price=6490, optgroup=None)
    low_conf = MatchResult(rule=cpu, raw=raw, mode="keyword", confidence=0.5)

    with caplog.at_level("WARNING", logger="coolpc"):
        report = build_daily_report(cfg=cfg, matches=[low_conf], store=store,
                                    now=datetime(2026, 4, 21, 1, 0))

    item = report.items[0]
    assert item.warning is None
    assert report.fetcher_warnings == []
    assert any("confidence" in r.message for r in caplog.records)
