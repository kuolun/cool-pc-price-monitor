"""Jinja2 rendering for daily HTML email + alert email."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw, ImageFont

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


_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # GHA Ubuntu
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _dashed_line(
    draw: ImageDraw.ImageDraw,
    x0: int, y0: int, x1: int, y1: int,
    fill: str, width: int = 1,
    dash: int = 6, gap: int = 4,
) -> None:
    total = max(1, x1 - x0)
    step = dash + gap
    x = x0
    while x < x1:
        seg_end = min(x + dash, x1)
        draw.line([(x, y0), (seg_end, y1)], fill=fill, width=width)
        x += step


def _render_chart_png(
    history: list[tuple[str, int]],
    baseline: int,
    *,
    width: int = 1280,
    height: int = 400,
) -> bytes:
    """Render the trend chart as PNG bytes. Width/height are pixel dimensions
    of the source image — caller is expected to display it scaled down (CSS
    max-width:640) so the rendered email looks crisp on retina screens.
    """
    img = Image.new("RGB", (width, height), "#fafafa")
    draw = ImageDraw.Draw(img)

    f_title = _load_font(22)
    f_axis = _load_font(20)
    f_value = _load_font(24)

    pad_l, pad_r, pad_t, pad_b = 130, 40, 60, 70
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    totals = [t for _, t in history]
    y_min = min(min(totals), baseline)
    y_max = max(max(totals), baseline)
    if y_max == y_min:
        y_max = y_min + 1
    pad = max(1, (y_max - y_min) * 0.10)
    y_lo = y_min - pad
    y_hi = y_max + pad
    n = len(history)

    def x_at(i: int) -> int:
        return pad_l + round(plot_w * i / max(1, n - 1))

    def y_at(v: float) -> int:
        return pad_t + round(plot_h * (1 - (v - y_lo) / (y_hi - y_lo)))

    draw.line([(pad_l, pad_t), (pad_l, pad_t + plot_h)], fill="#ddd", width=2)
    draw.line(
        [(pad_l, pad_t + plot_h), (pad_l + plot_w, pad_t + plot_h)],
        fill="#ddd", width=2,
    )

    by = y_at(baseline)
    _dashed_line(draw, pad_l, by, pad_l + plot_w, by, fill="#888", width=2, dash=14, gap=10)
    draw.text(
        (pad_l + plot_w - 8, by - 28),
        f"baseline ${baseline:,}",
        fill="#888", font=f_axis, anchor="ra",
    )

    draw.text((pad_l - 12, pad_t - 8), f"${y_hi:,.0f}", fill="#999", font=f_axis, anchor="ra")
    draw.text(
        (pad_l - 12, pad_t + plot_h - 8),
        f"${y_lo:,.0f}", fill="#999", font=f_axis, anchor="ra",
    )

    last_total = totals[-1]
    line_color = (
        _RED if last_total > baseline
        else _GREEN if last_total < baseline
        else _GRAY
    )

    points = [(x_at(i), y_at(t)) for i, t in enumerate(totals)]
    if len(points) >= 2:
        draw.line(points, fill=line_color, width=4, joint="curve")
    for px, py in points:
        draw.ellipse([(px - 4, py - 4), (px + 4, py + 4)], fill=line_color)
    lx, ly = points[-1]
    draw.ellipse([(lx - 7, ly - 7), (lx + 7, ly + 7)], fill=line_color)

    draw.text((lx - 12, ly - 28), f"${last_total:,}", fill=line_color, font=f_value, anchor="ra")

    def _short(d: str) -> str:
        return d[5:] if len(d) >= 10 else d

    draw.text((pad_l, pad_t + plot_h + 16), _short(history[0][0]), fill="#666", font=f_axis)
    draw.text(
        (pad_l + plot_w, pad_t + plot_h + 16),
        _short(history[-1][0]), fill="#666", font=f_axis, anchor="ra",
    )

    title = (
        f"Total trend · {n} days ({_short(history[0][0])} → {_short(history[-1][0])})"
    )
    draw.text((pad_l, pad_t - 36), title, fill="#666", font=f_title)

    summary = f"low ${min(totals):,} · high ${max(totals):,}"
    draw.text(
        (pad_l + plot_w // 2, pad_t + plot_h + 16),
        summary, fill="#999", font=f_axis, anchor="ma",
    )

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def render_total_history_chart(
    history: list[tuple[str, int]],
    baseline: int,
) -> str:
    """Inline base64-PNG line chart of daily totals vs baseline.

    Gmail strips inline <svg>; <img src="data:image/png;base64,...">
    survives. Empty/single-point history collapses to an empty string so
    the caller can skip the section. Image is rendered at 2x for retina,
    displayed via CSS max-width 640px.
    """
    if len(history) < 2:
        return ""

    png = _render_chart_png(history, baseline)
    b64 = base64.b64encode(png).decode("ascii")
    n = len(history)
    first_date, last_date = history[0][0], history[-1][0]

    def _short(d: str) -> str:
        return d[5:] if len(d) >= 10 else d

    return (
        '<div style="margin:16px 0;">'
        f'<div style="font-size:12px; color:#666; margin-bottom:4px;">'
        f"總價趨勢 · {n} 天（{_short(first_date)} → {_short(last_date)}）"
        "</div>"
        f'<img src="data:image/png;base64,{b64}" alt="Total trend chart" '
        'style="width:100%; max-width:640px; height:auto; display:block; '
        'border-radius:6px;">'
        "</div>"
    )


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
