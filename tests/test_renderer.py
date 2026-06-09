from datetime import date

from src.models import DailyReport, ItemDiff, TrackingRule
from src.renderer import (
    render_alert,
    render_daily_report,
    render_total_history_chart,
)


def _rule(key, label, qty=1, baseline=1000):
    return TrackingRule(
        key=key,
        label=label,
        quantity=qty,
        baseline_price=baseline,
        match_all=[key],
        exclude=[],
    )


def _item(
    rule,
    today=None,
    y=None,
    low7=None,
    low30=None,
    delta_base=None,
    is_7d_low=False,
    not_found=False,
    warning=None,
):
    return ItemDiff(
        rule=rule,
        today_price=today,
        today_line_total=(today * rule.quantity) if today is not None else None,
        yesterday_price=y,
        delta_yesterday_abs=(today - y) if (today is not None and y is not None) else None,
        delta_yesterday_pct=None,
        low_7d=low7,
        low_30d=low30,
        high_30d=None,
        delta_baseline_abs=delta_base,
        is_7d_low=is_7d_low,
        is_30d_low=False,
        not_found=not_found,
        warning=warning,
    )


def test_render_produces_nonempty_html():
    cpu = _rule("cpu", "AMD R7 7700 MPK", baseline=6490)
    report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[
            _item(cpu, today=6390, y=6490, low7=6390, low30=6390, delta_base=-100, is_7d_low=True)
        ],
        total_today=6390,
        total_baseline=6490,
        total_delta_baseline_abs=-100,
        total_delta_yesterday_abs=-100,
        missing_item_keys=[],
        fetcher_warnings=[],
    )
    html, _ = render_daily_report(report, run_id=42, option_count=1500, elapsed_ms=3200)
    assert "AMD R7 7700 MPK" in html
    assert "6,390" in html
    assert "-100" in html
    # Table is trimmed to 購買 / 今日 / Δ購買 — the daily-change and low
    # columns (and their 🔻⭐ markers) now live only in the trend chart.
    assert "Δ 購買" in html
    assert "7d low" not in html
    assert "30d low" not in html
    assert "🔻" not in html and "⭐" not in html


def test_render_shows_not_found_row():
    cpu = _rule("cpu", "CPU")
    report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, not_found=True)],
        total_today=0,
        total_baseline=1000,
        total_delta_baseline_abs=-1000,
        total_delta_yesterday_abs=None,
        missing_item_keys=["cpu"],
        fetcher_warnings=["cpu 未找到"],
    )
    html, _ = render_daily_report(report, run_id=1, option_count=1500, elapsed_ms=100)
    assert "今日未找到" in html
    assert "需注意" in html


def test_render_banner_bg_varies_by_baseline_delta():
    cpu = _rule("cpu", "CPU", baseline=1000)
    cheap_report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, today=900, y=1000, low7=900, low30=900, delta_base=-100)],
        total_today=900,
        total_baseline=1000,
        total_delta_baseline_abs=-100,
        total_delta_yesterday_abs=-100,
        missing_item_keys=[],
        fetcher_warnings=[],
    )
    html_cheap, _ = render_daily_report(cheap_report, run_id=1, option_count=1500, elapsed_ms=0)
    assert "#e8f5e8" in html_cheap

    dear_report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, today=1100, y=1000, low7=1000, low30=1000, delta_base=100)],
        total_today=1100,
        total_baseline=1000,
        total_delta_baseline_abs=100,
        total_delta_yesterday_abs=100,
        missing_item_keys=[],
        fetcher_warnings=[],
    )
    html_dear, _ = render_daily_report(dear_report, run_id=1, option_count=1500, elapsed_ms=0)
    assert "#fde4e4" in html_dear


def test_render_alert_contains_error_info():
    html = render_alert(
        error_type="FetcherError",
        error_message="Only 45 options — HTML structure may have changed",
        timestamp="2026-04-21T09:00:00+08:00",
        run_id=7,
    )
    assert "FetcherError" in html
    assert "45 options" in html
    assert "7" in html
    assert "probe.py" in html


def test_filters_handle_none_values():
    cpu = _rule("cpu", "CPU")
    report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, today=1000, y=None, low7=None, low30=None, delta_base=0)],
        total_today=1000,
        total_baseline=1000,
        total_delta_baseline_abs=0,
        total_delta_yesterday_abs=None,
        missing_item_keys=[],
        fetcher_warnings=[],
    )
    # None yesterday/low values must not break rendering of the trimmed table.
    html, _ = render_daily_report(report, run_id=1, option_count=1500, elapsed_ms=0)
    assert "CPU" in html
    assert "1,000" in html


def test_chart_empty_for_short_history():
    assert render_total_history_chart([], 50000) == ("", None)
    assert render_total_history_chart([("2026-05-20", 60000)], 50000) == ("", None)


def test_chart_returns_html_and_png_bytes():
    history = [
        ("2026-05-18", 64000),
        ("2026-05-19", 64500),
        ("2026-05-20", 64200),
    ]
    html, png = render_total_history_chart(history, baseline=50000)
    assert 'src="cid:trend-chart"' in html
    assert "總價趨勢" in html
    assert "05-18" in html and "05-20" in html
    assert png is not None and png[:8] == b"\x89PNG\r\n\x1a\n"


def test_chart_html_is_email_safe():
    history = [("2026-05-18", 64000), ("2026-05-19", 64500)]
    html, _ = render_total_history_chart(history, baseline=50000)
    assert "<svg" not in html
    assert "position:absolute" not in html
    assert "display:flex" not in html
    assert "transform:" not in html
    assert "data:image" not in html


def test_chart_renders_into_daily_email():
    cpu = _rule("cpu", "CPU", baseline=1000)
    report = DailyReport(
        run_date=date(2026, 5, 21),
        items=[_item(cpu, today=1100, y=1100, low7=1100, low30=1100, delta_base=100)],
        total_today=1100,
        total_baseline=1000,
        total_delta_baseline_abs=100,
        total_delta_yesterday_abs=0,
        missing_item_keys=[],
        fetcher_warnings=[],
    )
    history = [("2026-05-19", 1050), ("2026-05-20", 1100), ("2026-05-21", 1100)]
    html, inline_images = render_daily_report(
        report,
        run_id=1,
        option_count=1500,
        elapsed_ms=0,
        total_history=history,
    )
    assert "總價趨勢" in html
    assert 'src="cid:trend-chart"' in html
    assert "trend-chart" in inline_images
    assert inline_images["trend-chart"][:8] == b"\x89PNG\r\n\x1a\n"


def test_chart_section_skipped_when_history_empty():
    cpu = _rule("cpu", "CPU", baseline=1000)
    report = DailyReport(
        run_date=date(2026, 5, 21),
        items=[_item(cpu, today=1000, y=1000, low7=1000, low30=1000, delta_base=0)],
        total_today=1000,
        total_baseline=1000,
        total_delta_baseline_abs=0,
        total_delta_yesterday_abs=0,
        missing_item_keys=[],
        fetcher_warnings=[],
    )
    html, inline_images = render_daily_report(
        report,
        run_id=1,
        option_count=1500,
        elapsed_ms=0,
        total_history=[],
    )
    assert "總價趨勢" not in html
    assert inline_images == {}
