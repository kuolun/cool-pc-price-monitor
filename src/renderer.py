"""Jinja2 rendering for daily HTML email + alert email."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models import DailyReport

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _comma(n: int | None) -> str:
    return f"{n:,}" if n is not None else ""


def _comma_or_dash(n: int | None) -> str:
    return f"{n:,}" if n is not None else "—"


def _signed_comma(n: int | None) -> str:
    if n is None:
        return ""
    if n > 0:
        return f"+{n:,}"
    return f"{n:,}"


def _signed_comma_or_dash(n: int | None) -> str:
    return _signed_comma(n) if n is not None else "—"


def _make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["comma"] = _comma
    env.filters["comma_or_dash"] = _comma_or_dash
    env.filters["signed_comma"] = _signed_comma
    env.filters["signed_comma_or_dash"] = _signed_comma_or_dash
    return env


_GREEN = "#2d7a2d"
_GREEN_BG = "#e8f5e8"
_RED = "#c92a2a"
_RED_BG = "#fde4e4"
_GRAY = "#666"
_GRAY_BG = "#f5f5f5"


def _color_for(delta: int | None) -> str:
    if delta is None:
        return _GRAY
    if delta < 0:
        return _GREEN
    if delta > 0:
        return _RED
    return _GRAY


def _banner_bg_for(delta: int) -> str:
    if delta < 0:
        return _GREEN_BG
    if delta > 0:
        return _RED_BG
    return _GRAY_BG


def render_daily_report(
    report: DailyReport, *,
    run_id: int, option_count: int, elapsed_ms: int,
) -> str:
    env = _make_env()
    tmpl = env.get_template("email.html.j2")

    items_with_color = []
    for it in report.items:
        d = it.model_dump()
        d["rule"] = it.rule
        d["delta_yesterday_color"] = _color_for(it.delta_yesterday_abs)
        d["delta_baseline_color"] = _color_for(it.delta_baseline_abs)
        # Line-total fields so per-row columns add up to the 合計 row when
        # quantity > 1. Stored deltas/lows are per-unit; renderer multiplies.
        qty = it.rule.quantity
        d["delta_yesterday_line"] = (
            it.delta_yesterday_abs * qty if it.delta_yesterday_abs is not None else None
        )
        d["delta_baseline_line"] = (
            it.delta_baseline_abs * qty if it.delta_baseline_abs is not None else None
        )
        d["low_7d_line"] = it.low_7d * qty if it.low_7d is not None else None
        d["low_30d_line"] = it.low_30d * qty if it.low_30d is not None else None
        items_with_color.append(d)

    return tmpl.render(
        run_date=report.run_date.isoformat(),
        items=items_with_color,
        total_today=report.total_today,
        delta_baseline=report.total_delta_baseline_abs,
        delta_yesterday_abs=report.total_delta_yesterday_abs,
        total_delta_baseline_abs=report.total_delta_baseline_abs,
        total_delta_yesterday_abs=report.total_delta_yesterday_abs,
        delta_color=_color_for(report.total_delta_baseline_abs),
        banner_bg=_banner_bg_for(report.total_delta_baseline_abs),
        total_delta_baseline_color=_color_for(report.total_delta_baseline_abs),
        total_delta_yesterday_color=_color_for(report.total_delta_yesterday_abs),
        warnings=report.fetcher_warnings,
        run_id=run_id,
        option_count=option_count,
        elapsed_ms=elapsed_ms,
    )


def render_alert(
    *, error_type: str, error_message: str,
    timestamp: str, run_id: int | None = None,
) -> str:
    env = _make_env()
    tmpl = env.get_template("alert.html.j2")
    return tmpl.render(
        error_type=error_type,
        error_message=error_message,
        timestamp=timestamp,
        run_id=run_id,
    )
