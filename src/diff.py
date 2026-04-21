"""Build DailyReport from today's matches + history."""
from __future__ import annotations

from datetime import datetime, timedelta

from src.config import AppConfig
from src.models import DailyReport, ItemDiff, MatchResult
from src.storage import Storage


def build_daily_report(
    *, cfg: AppConfig, matches: list[MatchResult],
    store: Storage, now: datetime,
) -> DailyReport:
    items: list[ItemDiff] = []
    missing_keys: list[str] = []
    warnings: list[str] = []

    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for m in matches:
        rule = m.rule

        if m.mode == "not_found" or m.raw is None:
            missing_keys.append(rule.key)
            warnings.append(f"{rule.key}（{rule.label}）：今日未找到")
            items.append(ItemDiff(
                rule=rule,
                today_price=None, today_line_total=None,
                yesterday_price=None,
                delta_yesterday_abs=None, delta_yesterday_pct=None,
                low_7d=None, low_30d=None, high_30d=None,
                delta_baseline_abs=None,
                is_7d_low=False, is_30d_low=False,
                not_found=True,
                warning=f"{rule.label} 今日未找到",
            ))
            continue

        price = m.raw.price
        assert price is not None

        yesterday = store.query_last_price_before(rule.key, start_of_today)

        low_7d = store.query_low(rule.key, now - timedelta(days=7), now)
        low_30d = store.query_low(rule.key, now - timedelta(days=30), now)
        high_30d = store.query_high(rule.key, now - timedelta(days=30), now)

        delta_y_abs = price - yesterday if yesterday is not None else None
        delta_y_pct = (
            100.0 * delta_y_abs / yesterday
            if yesterday is not None and yesterday > 0 and delta_y_abs is not None
            else None
        )
        delta_baseline_abs = price - rule.baseline_price

        is_7d_low = low_7d is None or price <= low_7d
        is_30d_low = low_30d is None or price <= low_30d

        warning: str | None = None
        if m.confidence < 1.0:
            n_candidates = int(round(1.0 / m.confidence)) if m.confidence > 0 else 0
            warning = f"多重候選 {n_candidates} 個，confidence {m.confidence:.2f}"
            warnings.append(f"{rule.key}: {warning}")
        elif m.mode == "keyword" and rule.option_value_hint:
            warning = "option_value_hint 失效，已用 keyword fallback"
            warnings.append(f"{rule.key}: {warning}")

        items.append(ItemDiff(
            rule=rule,
            today_price=price,
            today_line_total=price * rule.quantity,
            yesterday_price=yesterday,
            delta_yesterday_abs=delta_y_abs,
            delta_yesterday_pct=delta_y_pct,
            low_7d=low_7d, low_30d=low_30d, high_30d=high_30d,
            delta_baseline_abs=delta_baseline_abs,
            is_7d_low=is_7d_low, is_30d_low=is_30d_low,
            not_found=False,
            warning=warning,
        ))

    total_today = sum(
        (it.today_line_total for it in items if it.today_line_total is not None), 0
    )
    total_baseline = sum(r.baseline_price * r.quantity for r in cfg.rules)
    total_delta_baseline_abs = total_today - total_baseline

    ys_by_key = {
        it.rule.key: it.yesterday_price for it in items if not it.not_found
    }
    if ys_by_key and all(v is not None for v in ys_by_key.values()):
        total_yesterday = sum(
            (ys_by_key[it.rule.key] or 0) * it.rule.quantity
            for it in items if not it.not_found
        )
        total_delta_yesterday_abs: int | None = total_today - total_yesterday
    else:
        total_delta_yesterday_abs = None

    return DailyReport(
        run_date=now.date(),
        items=items,
        total_today=total_today,
        total_baseline=total_baseline,
        total_delta_baseline_abs=total_delta_baseline_abs,
        total_delta_yesterday_abs=total_delta_yesterday_abs,
        missing_item_keys=missing_keys,
        fetcher_warnings=warnings,
    )
