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
    plot_h: int = 120,
) -> str:
    """HTML/CSS column chart of daily totals vs baseline.

    Pure inline-styled <table> — Gmail strips inline <svg>, but renders
    <table> with colored <div>s reliably. Each column = one day; bar height
    is proportional to (total − y_lo) / (y_hi − y_lo). Bars above baseline
    are red, below are green. Empty when <2 points so the caller can skip.
    """
    if len(history) < 2:
        return ""

    totals = [t for _, t in history]
    y_min = min(min(totals), baseline)
    y_max = max(max(totals), baseline)
    if y_max == y_min:
        y_max = y_min + 1
    pad = max(1, (y_max - y_min) * 0.08)
    y_lo = y_min - pad
    y_hi = y_max + pad
    span = y_hi - y_lo

    def bar_h(v: int) -> int:
        return max(1, round(plot_h * (v - y_lo) / span))

    baseline_h = round(plot_h * (baseline - y_lo) / span)
    min_total = min(totals)
    max_total = max(totals)
    last_total = totals[-1]
    first_date, last_date = history[0][0], history[-1][0]
    n = len(history)

    headline_color = (
        _RED if last_total > baseline
        else _GREEN if last_total < baseline
        else _GRAY
    )

    def _short(d: str) -> str:
        return d[5:] if len(d) >= 10 else d

    bars_html = []
    for _, t in history:
        h = bar_h(t)
        color = _RED if t > baseline else (_GREEN if t < baseline else _GRAY)
        bars_html.append(
            f'<td style="vertical-align:bottom; padding:0 1px; height:{plot_h}px;">'
            f'<div style="height:{h}px; background:{color}; min-width:6px;"></div>'
            f'</td>'
        )

    label_top_h = max(0, plot_h - baseline_h - 8)
    label_bot_h = max(0, baseline_h - 8)

    return f"""
<table cellspacing="0" cellpadding="0" border="0" width="100%"
       style="border-collapse:collapse; background:#fafafa; border-radius:6px; margin:16px 0;">
  <tr>
    <td style="padding:10px 14px 4px 14px;">
      <table cellspacing="0" cellpadding="0" border="0" width="100%"
             style="border-collapse:collapse; font-size:11px; color:#666;">
        <tr>
          <td align="left">總價趨勢 · {n} 天（{_short(first_date)} → {_short(last_date)}）</td>
          <td align="right" style="color:{headline_color}; font-weight:600;">最新 ${last_total:,}</td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td style="padding:0 14px 4px 14px;">
      <table cellspacing="0" cellpadding="0" border="0" width="100%"
             style="border-collapse:collapse; table-layout:fixed;">
        <tr>
          <td width="74" valign="top" align="right"
              style="font-size:10px; color:#999; padding-right:6px;">
            <div style="height:16px; line-height:16px;">${y_hi:,.0f}</div>
            <div style="height:{label_top_h}px;"></div>
            <div style="height:16px; line-height:16px; color:#888;">baseline ${baseline:,}</div>
            <div style="height:{label_bot_h}px;"></div>
            <div style="height:16px; line-height:16px;">${y_lo:,.0f}</div>
          </td>
          {"".join(bars_html)}
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td style="padding:0 14px 10px 14px;">
      <table cellspacing="0" cellpadding="0" border="0" width="100%"
             style="border-collapse:collapse; font-size:10px; color:#999;">
        <tr>
          <td align="left" style="padding-left:80px;">{_short(first_date)}</td>
          <td align="center">low ${min_total:,} · high ${max_total:,}</td>
          <td align="right">{_short(last_date)}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>
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
