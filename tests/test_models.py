from datetime import date

import pytest
from pydantic import ValidationError

from src.models import (
    DailyReport,
    ItemDiff,
    MatchResult,
    RawProduct,
    TrackingRule,
)


def test_tracking_rule_requires_quantity_positive():
    with pytest.raises(ValidationError):
        TrackingRule(
            key="cpu", label="CPU", quantity=0, baseline_price=6490,
            match_all=["AMD"], exclude=[],
        )


def test_tracking_rule_option_value_hint_defaults_to_none():
    rule = TrackingRule(
        key="cpu", label="CPU", quantity=1, baseline_price=6490,
        match_all=["AMD"], exclude=[],
    )
    assert rule.option_value_hint is None


def test_raw_product_price_can_be_none():
    rp = RawProduct(option_value="1", option_text="foo", price=None, optgroup=None)
    assert rp.price is None


def test_match_result_mode_is_literal():
    rule = TrackingRule(
        key="cpu", label="CPU", quantity=1, baseline_price=6490,
        match_all=["AMD"], exclude=[],
    )
    with pytest.raises(ValidationError):
        MatchResult(rule=rule, raw=None, mode="invalid", confidence=0.0)


def test_item_diff_not_found_defaults():
    rule = TrackingRule(
        key="cpu", label="CPU", quantity=1, baseline_price=6490,
        match_all=["AMD"], exclude=[],
    )
    item = ItemDiff(
        rule=rule,
        today_price=None, today_line_total=None,
        yesterday_price=None,
        delta_yesterday_abs=None, delta_yesterday_pct=None,
        low_7d=None, low_30d=None, high_30d=None,
        delta_baseline_abs=None,
        is_7d_low=False, is_30d_low=False,
        not_found=True, warning=None,
    )
    assert item.not_found is True


def test_daily_report_composition():
    rule = TrackingRule(
        key="cpu", label="CPU", quantity=1, baseline_price=6490,
        match_all=["AMD"], exclude=[],
    )
    item = ItemDiff(
        rule=rule,
        today_price=6390, today_line_total=6390,
        yesterday_price=6490,
        delta_yesterday_abs=-100, delta_yesterday_pct=-1.54,
        low_7d=6390, low_30d=6390, high_30d=6500,
        delta_baseline_abs=-100,
        is_7d_low=True, is_30d_low=True,
        not_found=False, warning=None,
    )
    report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[item],
        total_today=6390,
        total_baseline=6490,
        total_delta_baseline_abs=-100,
        total_delta_yesterday_abs=-100,
        missing_item_keys=[],
        fetcher_warnings=[],
    )
    assert report.items[0].rule.key == "cpu"
    assert report.total_delta_baseline_abs == -100
