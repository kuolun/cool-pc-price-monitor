"""Entrypoint: fetch → match → store → diff → render → notify."""

from __future__ import annotations

import argparse
import logging
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from src import notifier as _notifier
from src.config import SMTPConfig, load_products
from src.diff import build_daily_report
from src.fetchers.base import FetcherError
from src.fetchers.coolpc import CoolpcFetcher
from src.matcher import match
from src.renderer import render_alert, render_daily_report
from src.storage import Storage


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Coolpc price monitor daily run")
    p.add_argument("--dry-run", action="store_true", help="不發 email、不寫 DB（只印到 stdout）")
    p.add_argument("--config", default="config/products.yaml", help="YAML 設定檔路徑")
    p.add_argument("--db", default="data/prices.db", help="SQLite 資料庫路徑")
    return p.parse_args(argv)


def _compose_subject(run_date, total_today, delta_baseline, delta_yesterday) -> str:
    # 主旨用全形「｜」分段、CJK 段內不夾 ASCII 空白：Python 的 email 編碼器會把
    # 中英混排折成相鄰 encoded-word，而 RFC 2047 §6.2 規定兩個 encoded-word 之間
    # 的 LWSP 在顯示時要被丟掉。改用全形分隔字元就完全避開這個吃空白的雷。

    # vs 昨天：每日信最該一眼看到的「今天有沒有動」，沒昨資料就標明。
    if delta_yesterday is None:
        day = "昨無資料"
    elif delta_yesterday > 0:
        day = f"昨+{delta_yesterday:,}↑"
    elif delta_yesterday < 0:
        day = f"昨{delta_yesterday:,}↓"  # 負號已含在數字裡
    else:
        day = "昨持平"

    # vs 購買：東西已經買了，市價比買價高＝你買在低點、賺到。正向講「現省」，
    # 避免「+14,501」配紅字被讀成壞消息（方向其實相反）。
    if delta_baseline > 0:
        base = f"現省{delta_baseline:,}"
    elif delta_baseline < 0:
        base = f"比買價低{-delta_baseline:,}"
    else:
        base = "與買價同"

    return f"[原價屋] {run_date} ${total_today:,}｜{day}｜{base}"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log = logging.getLogger("coolpc")
    load_dotenv()
    args = _parse_args(argv)

    cfg = load_products(args.config)
    log.info("loaded config: %d rules, baseline date=%s", len(cfg.rules), cfg.baseline.date)

    now = datetime.now()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    store = Storage(args.db)
    run_id = store.record_run_start(now)
    t0 = time.monotonic()

    try:
        fetcher = CoolpcFetcher()
        raw = fetcher.fetch()
        option_count = len(raw)
        log.info("fetched %d options", option_count)

        matches = match(cfg.rules, raw)
        hit = sum(1 for m in matches if m.mode != "not_found")
        log.info("matched %d/%d items", hit, len(matches))
        print(f"fetched {option_count} options → matched {hit}/{len(matches)} items")

        store.record_snapshots(run_id, matches)

        report = build_daily_report(cfg=cfg, matches=matches, store=store, now=now)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        quantities = {r.key: r.quantity for r in cfg.rules}
        total_history = store.query_total_history(
            quantities,
            now - timedelta(days=30),
            now,
        )

        html, inline_images = render_daily_report(
            report,
            run_id=run_id,
            option_count=option_count,
            elapsed_ms=elapsed_ms,
            total_history=total_history,
        )
        subject = _compose_subject(
            report.run_date,
            report.total_today,
            report.total_delta_baseline_abs,
            report.total_delta_yesterday_abs,
        )

        print(
            f"today total ${report.total_today:,} "
            f"(vs baseline {report.total_delta_baseline_abs:+,})"
        )

        status = "partial" if report.missing_item_keys else "ok"

        if args.dry_run:
            print("--- dry-run: HTML preview ---")
            print(html)
            print("--- would send email with subject:", subject)
            store.record_run_end(run_id, datetime.now(), status, option_count)
            return 0

        smtp_cfg = SMTPConfig.from_env()
        _notifier.send_email(
            cfg=smtp_cfg, subject=subject, html_body=html,
            inline_images=inline_images,
        )
        store.record_run_end(run_id, datetime.now(), status, option_count)
        log.info("sent email to %s", smtp_cfg.to_email)
        return 0

    except FetcherError as e:
        log.error("fetcher failed: %s", e)
        store.record_run_end(
            run_id,
            datetime.now(),
            "failed",
            error=str(e),
        )
        if not args.dry_run:
            try:
                smtp_cfg = SMTPConfig.from_env()
                html = render_alert(
                    error_type="FetcherError",
                    error_message=str(e),
                    timestamp=datetime.now().isoformat(),
                    run_id=run_id,
                )
                _notifier.send_email(
                    cfg=smtp_cfg,
                    subject=f"[原價屋] ⚠️ 系統故障 run#{run_id}",
                    html_body=html,
                )
            except Exception:
                log.exception("alert email also failed")
        return 1

    except Exception as e:
        log.exception("unexpected failure")
        store.record_run_end(
            run_id,
            datetime.now(),
            "failed",
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
        )
        return 1
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
