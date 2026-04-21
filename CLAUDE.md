# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Daily-run tool that scrapes coolpc.com.tw evaluate.php for a fixed 8-item shopping list and emails an HTML digest tracking price trends. Single user, personal tool. Runs via GitHub Actions daily cron.

The canonical design lives in `docs/superpowers/specs/2026-04-21-coolpc-price-monitor-design.md` — read it first, do not deviate without discussion.

## Tech Stack

- Python 3.11+, `uv` for deps
- httpx, pydantic v2, beautifulsoup4 + lxml, Jinja2, PyYAML, python-dotenv
- sqlite3 (stdlib), pytest, ruff

## Commands

```bash
uv sync                                    # install deps
uv run python -m src.main --dry-run        # run without sending email / commit
uv run python -m src.main                  # run for real
uv run pytest                              # full test suite
uv run pytest tests/test_matcher.py -v     # single file
uv run ruff check .                        # lint
uv run ruff format .                       # format
```

## Architecture — Non-Obvious Points

**Fetcher is pluggable.** `src/fetchers/base.py` defines abstract `Fetcher`; `coolpc.py` is first impl. Future sites (樂屋, 欣亞) add new fetcher files without touching matcher/diff/renderer/notifier.

**Baseline lives in YAML, not DB.** `config/products.yaml` stores the 2026-02-24 purchase baseline. DB only holds observed prices. To reset baseline, edit YAML; no DB migration needed.

**A+C hybrid matching.** Matcher first tries `option_value_hint` (stable HTML ID if probed and found stable), falls back to `match_all`/`exclude` keyword whitelist. If `match_all` yields multiple candidates, picks shortest `option_text` and lowers confidence; renderer emits a warning on `confidence < 1.0`.

**not_found is not fatal.** If matcher can't find a product today, snapshots row stores `price=NULL, match_mode='not_found'`. Email still sends with a warning banner. The run is still `status='ok'` (or `'partial'` if any items missing).

**Fetcher failures are fatal.** `FetcherError` → alert email via `templates/alert.html.j2`, `runs.status='failed'`, exit 1 (GHA red).

**DB commit guard.** GHA only commits `data/prices.db` back to the branch when the main run succeeds (not on dry-run, not on failure). See `.github/workflows/daily.yml`.

**Quality gate.** If fetcher parses < 200 options, raise `FetcherError` — coolpc normally has 1000+ options, sub-200 means HTML structure changed.

## Implementation Plan

Follow `docs/superpowers/plans/2026-04-21-coolpc-price-monitor.md` step-by-step. Commit after each task.
