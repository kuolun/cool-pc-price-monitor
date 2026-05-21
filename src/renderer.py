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


def render_total_history_chart(
    history: list[tuple[str, int]],
    baseline: int,
    *,
    width: int = 640,
    height: int = 200,
) -> str:
    """Inline SVG line chart of daily totals vs baseline.

    Email-safe: pure SVG, no scripts, no external assets. Empty/single-point
    history collapses to an empty string so the caller can skip the section.
    """
    if len(history) < 2:
        return ""

    pad_left, pad_right, pad_top, pad_bottom = 56, 12, 20, 28
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    totals = [t for _, t in history]
    y_min = min(min(totals), baseline)
    y_max = max(max(totals), baseline)
    if y_max == y_min:
        y_max = y_min + 1
    pad = max(1, (y_max - y_min) * 0.08)
    y_lo = y_min - pad
    y_hi = y_max + pad

    n = len(history)

    def x_at(i: int) -> float:
        return pad_left + (plot_w * i / (n - 1))

    def y_at(v: float) -> float:
        return pad_top + plot_h * (1 - (v - y_lo) / (y_hi - y_lo))

    points = " ".join(f"{x_at(i):.1f},{y_at(t):.1f}" for i, t in enumerate(totals))
    baseline_y = y_at(baseline)

    last_total_v = totals[-1]
    line_color = _RED if last_total_v > baseline else _GREEN if last_total_v < baseline else _GRAY

    first_date, first_total = history[0]
    last_date, _ = history[-1]
    min_total = min(totals)
    max_total = max(totals)

    def _date_short(d: str) -> str:
        return d[5:] if len(d) >= 10 else d

    y_axis_top = pad_top
    y_axis_bot = pad_top + plot_h

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"
     width="100%" style="max-width:{width}px; display:block; margin: 16px 0;">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa" rx="6"/>
  <text x="{pad_left}" y="14" font-size="11" fill="#666"
        font-family="-apple-system, 'PingFang TC', sans-serif">
    總價趨勢 · {n} 天（{_date_short(first_date)} → {_date_short(last_date)}）
  </text>
  <text x="{pad_left - 6}" y="{y_at(y_hi) + 4:.1f}" font-size="10" fill="#999"
        text-anchor="end">${y_hi:,.0f}</text>
  <text x="{pad_left - 6}" y="{y_at(y_lo) + 4:.1f}" font-size="10" fill="#999"
        text-anchor="end">${y_lo:,.0f}</text>
  <line x1="{pad_left}" y1="{y_axis_top}" x2="{pad_left}" y2="{y_axis_bot}"
        stroke="#ddd" stroke-width="1"/>
  <line x1="{pad_left}" y1="{y_axis_bot}" x2="{width - pad_right}" y2="{y_axis_bot}"
        stroke="#ddd" stroke-width="1"/>
  <line x1="{pad_left}" y1="{baseline_y:.1f}" x2="{width - pad_right}" y2="{baseline_y:.1f}"
        stroke="#888" stroke-width="1" stroke-dasharray="4,3"/>
  <text x="{width - pad_right - 2}" y="{baseline_y - 4:.1f}" font-size="10" fill="#888"
        text-anchor="end">baseline ${baseline:,}</text>
  <polyline fill="none" stroke="{line_color}" stroke-width="2" points="{points}"/>
  <circle cx="{x_at(0):.1f}" cy="{y_at(first_total):.1f}" r="2.5" fill="{line_color}"/>
  <circle cx="{x_at(n - 1):.1f}" cy="{y_at(last_total_v):.1f}" r="3.5" fill="{line_color}"/>
  <text x="{x_at(0):.1f}" y="{height - 12}" font-size="10" fill="#666"
        text-anchor="middle">{_date_short(first_date)}</text>
  <text x="{x_at(n - 1):.1f}" y="{height - 12}" font-size="10" fill="#666"
        text-anchor="middle">{_date_short(last_date)}</text>
  <text x="{x_at(n - 1) - 4:.1f}" y="{y_at(last_total_v) - 6:.1f}" font-size="11"
        fill="{line_color}" font-weight="600" text-anchor="end">${last_total_v:,}</text>
  <text x="{width - pad_right}" y="{height - 12}" font-size="10" fill="#999"
        text-anchor="end">low ${min_total:,} · high ${max_total:,}</text>
</svg>
""".strip()


def render_daily_report(
    report: DailyReport,
    *,
    run_id: int,
    option_count: int,
    elapsed_ms: int,
    total_history: list[tuple[str, int]] | None = None,
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
        d["baseline_line"] = it.rule.baseline_price * qty
        items_with_color.append(d)

    chart_svg = ""
    if total_history:
        chart_svg = render_total_history_chart(total_history, report.total_baseline)

    return tmpl.render(
        run_date=report.run_date.isoformat(),
        items=items_with_color,
        total_today=report.total_today,
        total_baseline=report.total_baseline,
        delta_baseline=report.total_delta_baseline_abs,
        delta_yesterday_abs=report.total_delta_yesterday_abs,
        total_delta_baseline_abs=report.total_delta_baseline_abs,
        total_delta_yesterday_abs=report.total_delta_yesterday_abs,
        delta_color=_color_for(report.total_delta_baseline_abs),
        banner_bg=_banner_bg_for(report.total_delta_baseline_abs),
        total_delta_baseline_color=_color_for(report.total_delta_baseline_abs),
        total_delta_yesterday_color=_color_for(report.total_delta_yesterday_abs),
        warnings=report.fetcher_warnings,
        chart_svg=chart_svg,
        run_id=run_id,
        option_count=option_count,
        elapsed_ms=elapsed_ms,
    )


def render_alert(
    *,
    error_type: str,
    error_message: str,
    timestamp: str,
    run_id: int | None = None,
) -> str:
    env = _make_env()
    tmpl = env.get_template("alert.html.j2")
    return tmpl.render(
        error_type=error_type,
        error_message=error_message,
        timestamp=timestamp,
        run_id=run_id,
    )
