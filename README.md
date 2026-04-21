# Cool PC Price Monitor

Daily-run tool that monitors prices on coolpc.com.tw for a fixed 8-item shopping list and emails an HTML digest tracking price trends vs purchase date / 7-day low / 30-day low. Single user, personal tool. Runs via GitHub Actions daily at 09:00 Taipei.

- Spec: `docs/superpowers/specs/2026-04-21-coolpc-price-monitor-design.md`
- Plan: `docs/superpowers/plans/2026-04-21-coolpc-price-monitor.md`
- HTML probe notes: `docs/coolpc-html-notes.md`

## Setup

```bash
uv sync
cp .env.example .env
# edit .env: SMTP_USER / SMTP_PASS (Gmail app password) / TO_EMAIL
```

## Commands

```bash
uv run python -m src.main --dry-run     # no email, no DB write
uv run python -m src.main               # real run
uv run pytest                           # all tests
uv run pytest tests/test_matcher.py -v  # single file
uv run ruff check .                     # lint
uv run ruff format .                    # format
uv run python scripts/probe.py          # re-probe coolpc HTML (updates fixture + notes)
```

## Schedule

GitHub Actions workflow `.github/workflows/daily.yml` runs at UTC 01:00 (= Taipei 09:00) daily. Manual trigger:

```bash
gh workflow run "Daily price check" -f dry_run=true    # dry-run
gh workflow run "Daily price check"                    # real
```

## Adding / Changing Items

Edit `config/products.yaml`. Each entry:

```yaml
- key: <short-id>
  label: <display name>
  quantity: 1
  baseline_price: <purchase price per unit>
  match_all: [<keywords all must appear in option_text>]
  exclude: [<keywords that must NOT appear>]
  option_value_hint: "<stable <option value> from scripts/probe.py>"   # optional
```

After editing:
1. `uv run python -m src.main --dry-run` — confirm `matched N/N items`
2. Commit the YAML change

## Resetting the Baseline

If you buy a new set and want to re-anchor the trend:
1. Edit `config/products.yaml`:
   - Update each item's `baseline_price` and `quantity`
   - Update `baseline.date` and `baseline.notes`
2. Commit + push — next run will show `vs 購買` relative to the new baseline

SQLite at `data/prices.db` is unaffected (keeps full price history).

## When option_value_hint Fails

If a product's `<option value>` changes (coolpc reshuffles IDs), matcher falls back to keyword mode (A mode) and email shows a warning. To fix:
1. `uv run python scripts/probe.py` — re-probes and shows new stable values
2. Update the affected item's `option_value_hint` in `config/products.yaml`
3. `--dry-run` to verify

## Tests

See `tests/`. Fixtures in `tests/fixtures/`. To regenerate the evaluate.php fixture:

```bash
uv run python scripts/probe.py
```

## Storage

SQLite DB at `data/prices.db` is committed back to the repo by GitHub Actions after each successful real run. Monthly tag backup (`snapshot-YYYY-MM`) guards against force-push data loss.

## Architecture

See `CLAUDE.md` for non-obvious design decisions (pluggable fetcher, A+C hybrid matching, not_found handling, DB commit guard, 200-option quality gate).
