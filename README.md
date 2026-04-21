# Cool PC Price Monitor

Daily-run tool that monitors prices on coolpc.com.tw for a fixed shopping list and emails an HTML digest showing trends vs purchase date / 7-day low / 30-day low.

See `docs/superpowers/specs/2026-04-21-coolpc-price-monitor-design.md` for full design.

## Quick Start

```bash
uv sync
cp .env.example .env
# edit .env with Gmail app password
uv run python -m src.main --dry-run
```

## Schedule

GitHub Actions runs daily at 09:00 Taipei time (UTC 01:00). See `.github/workflows/daily.yml`.
