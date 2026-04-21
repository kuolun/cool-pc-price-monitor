# Cool PC Price Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每日監控原價屋 `evaluate.php` 上使用者 2026-02-24 購買的 8 項零件價格，日報式 HTML email 顯示 vs 購買日 / 7d low / 30d low 的趨勢。

**Architecture:** Python 3.11 + uv 依賴管理；pluggable `Fetcher` 介面；SQLite 存歷史（commit 回 branch by GHA）；Jinja2 渲染 HTML email；GitHub Actions cron 每日 09:00（Taipei）觸發；Gmail SMTP 發信。

**Tech Stack:** Python 3.11+, uv, httpx, pydantic v2, beautifulsoup4 + lxml, Jinja2, SQLite (stdlib), PyYAML, python-dotenv, pytest, ruff.

**Spec reference:** `docs/superpowers/specs/2026-04-21-coolpc-price-monitor-design.md`

---

## Task 1: 專案骨架 + uv 環境

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `CLAUDE.md`
- Create: `src/__init__.py`
- Create: `src/fetchers/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`
- Create: `data/.gitkeep`

- [ ] **Step 1: 建立 `pyproject.toml`**

```toml
[project]
name = "cool-pc-price-monitor"
version = "0.1.0"
description = "Daily price monitor for coolpc.com.tw evaluate.php"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.5",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "Jinja2>=3.1",
    "PyYAML>=6.0",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "ruff>=0.3",
    "syrupy>=4.6",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: 建立 `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
.pytest_cache/
.ruff_cache/

# Env
.env
!.env.example

# IDE
.vscode/
.idea/
```

**注意**：`data/prices.db` **不**放在 .gitignore，因為 GHA 要 commit 它。

- [ ] **Step 3: 建立 `.env.example`**

```
# Gmail SMTP (use App Password, not login password)
SMTP_USER=your.gmail@gmail.com
SMTP_PASS=xxxx-xxxx-xxxx-xxxx
TO_EMAIL=your.gmail@gmail.com
```

- [ ] **Step 4: 建立 `README.md`**

```markdown
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
```

- [ ] **Step 5: 建立 `CLAUDE.md`**

```markdown
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
```

- [ ] **Step 6: 建立 `src/__init__.py`、`src/fetchers/__init__.py`、`tests/__init__.py`、`tests/fixtures/.gitkeep`、`data/.gitkeep`**

內容皆為空檔案。`.gitkeep` 是空檔案讓空目錄能進 git。

- [ ] **Step 7: uv sync 裝依賴**

```bash
uv sync
```

Expected: 建立 `.venv/`、`uv.lock`，無錯誤。

- [ ] **Step 8: git init + 首次 commit（含 spec）**

```bash
git init
git add .
git commit -m "chore: project skeleton + spec

- pyproject.toml with httpx/pydantic/bs4/jinja2/pyyaml deps
- .gitignore (ignore .env, keep data/)
- README.md / CLAUDE.md / .env.example
- docs/superpowers/specs/2026-04-21-coolpc-price-monitor-design.md (from brainstorm)
- docs/superpowers/plans/2026-04-21-coolpc-price-monitor.md"
```

- [ ] **Step 9: 驗證**

```bash
uv run python -c "import httpx, pydantic, bs4, jinja2, yaml, dotenv; print('deps ok')"
```

Expected: `deps ok`

---

## Task 2: 手動探 coolpc HTML

**Files:**
- Create: `scripts/probe.py`
- Create: `tests/fixtures/evaluate_sample.html`
- Create: `docs/coolpc-html-notes.md`

這一步是**探索式**，不走 TDD。目標是抓真實 HTML 存成 fixture、觀察結構、判斷 `<option value>` 是否穩定，並把結論寫成文件給後續 task 使用。

- [ ] **Step 1: 建立 `scripts/probe.py`**

```python
"""Probe coolpc evaluate.php HTML: count options, check option_value stability, save fixture."""
import hashlib
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

URL = "https://www.coolpc.com.tw/evaluate.php"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
}

FIXTURE_PATH = Path("tests/fixtures/evaluate_sample.html")


def fetch_raw() -> bytes:
    resp = httpx.get(URL, headers=HEADERS, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def inspect(html_bytes: bytes, label: str) -> dict:
    # 試 UTF-8 再試 Big5
    for encoding in ("utf-8", "big5"):
        try:
            html = html_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError("Cannot decode HTML as utf-8 or big5")

    soup = BeautifulSoup(html, "lxml")
    selects = soup.select("select[name^='Y']")
    options = soup.select("select[name^='Y'] option")
    values = [o.get("value", "") for o in options]
    optgroups = soup.select("select[name^='Y'] optgroup")

    # 找我們 8 個品項的命中數（初版 match_all）
    targets = {
        "cpu":    ["AMD", "R7 7700 MPK"],
        "mb":     ["B650EM", "FORCE", "WIFI6E"],
        "ram":    ["UMAX", "64GB", "雙通32GB", "6000", "CL30"],
        "ssd":    ["金士頓", "KC3000", "2TB"],
        "cooler": ["九州風神", "AG500"],
        "case":   ["視博通", "SW300", "白"],
        "psu":    ["Montech", "CENTURY II", "850W"],
        "os":     ["Windows 11", "家用彩盒版", "64位元"],
    }
    hits = {}
    for key, kws in targets.items():
        matched = [
            (o.get("value"), o.get_text(strip=True))
            for o in options
            if all(kw in o.get_text(strip=True) for kw in kws)
        ]
        hits[key] = matched

    return {
        "label": label,
        "encoding": encoding,
        "n_selects": len(selects),
        "n_options": len(options),
        "n_optgroups": len(optgroups),
        "sha256_values": hashlib.sha256("\n".join(values).encode()).hexdigest()[:16],
        "hits": hits,
    }


def main() -> None:
    # 抓 3 次（間隔 5 秒），看 option_value 是否穩定
    snapshots = []
    for i in range(3):
        print(f"[probe] fetch {i + 1}/3 ...", file=sys.stderr)
        raw = fetch_raw()
        snapshots.append((raw, inspect(raw, f"run{i + 1}")))
        if i < 2:
            time.sleep(5)

    # 存第一次的結果為 fixture
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_bytes(snapshots[0][0])
    print(f"[probe] saved fixture to {FIXTURE_PATH}", file=sys.stderr)

    # 報告
    for raw, info in snapshots:
        print(f"\n=== {info['label']} ===")
        print(f"  encoding     : {info['encoding']}")
        print(f"  <select Y*>  : {info['n_selects']}")
        print(f"  <option>     : {info['n_options']}")
        print(f"  <optgroup>   : {info['n_optgroups']}")
        print(f"  sha16(values): {info['sha256_values']}")

    print("\n=== option_value stability ===")
    hashes = {info["sha256_values"] for _, info in snapshots}
    if len(hashes) == 1:
        print("  STABLE — upgrade to C mode (fill option_value_hint in YAML)")
    else:
        print("  UNSTABLE — stay on A mode (match_all only)")
        for _, info in snapshots:
            print(f"    {info['label']}: {info['sha256_values']}")

    print("\n=== per-item hits (using run1) ===")
    for key, matched in snapshots[0][1]["hits"].items():
        print(f"  [{key}] {len(matched)} candidates")
        for value, text in matched[:3]:
            print(f"    value={value!r}  text={text[:80]!r}")
        if len(matched) > 3:
            print(f"    ... and {len(matched) - 3} more")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑 probe**

```bash
uv run python scripts/probe.py 2>&1 | tee scripts/probe-output.txt
```

Expected output 範例（數字會隨實際回應變）：
```
=== run1 ===
  encoding     : utf-8
  <select Y*>  : 20
  <option>     : 1523
  <optgroup>   : 150
  sha16(values): a1b2c3d4e5f67890
...
=== option_value stability ===
  STABLE — upgrade to C mode (fill option_value_hint in YAML)
=== per-item hits ===
  [cpu] 1 candidates
    value='1234'  text='[搭板價] AMD R7 7700 MPK(含風扇) 【8核/16緒】...'
  [mb] 1 candidates
    ...
```

**若某品項 candidates = 0**：回去調整 `scripts/probe.py` 的 `targets` 對應關鍵字，直到 8 個品項皆至少 1 個候選。此為後續 `config/products.yaml` 的依據。

**若某品項 candidates > 1**：記錄下來，之後 YAML 要加 `exclude` 排除旁支版本。

- [ ] **Step 3: 寫 `docs/coolpc-html-notes.md`**

根據 probe 結果填入實際數字：

```markdown
# coolpc evaluate.php HTML 探勘筆記

> 日期：YYYY-MM-DD（填實際探勘日期）
> 對應 spec：`docs/superpowers/specs/2026-04-21-coolpc-price-monitor-design.md`

## 基本結構

- URL：<https://www.coolpc.com.tw/evaluate.php>
- 編碼：**（utf-8 或 big5，填實際值）**
- `<select name="Y*">` 數量：**N 個**
- `<option>` 總數：**M 個**
- `<optgroup label="...">` 數量：**K 個**
- 品質閾值：fetcher 若 option < 200 則 raise（正常 M 遠大於 200）

## option_value 穩定性

3 次抓取間隔 5 秒，values SHA-256 前 16 位：
- run1: `________________`
- run2: `________________`
- run3: `________________`

結論：**（STABLE 或 UNSTABLE）**

- 若 STABLE：後續 `config/products.yaml` 的每個 rule 填 `option_value_hint`，matcher 走 C 模式優先
- 若 UNSTABLE：YAML 不填 `option_value_hint`，matcher 只走 A 模式（match_all）

## 8 個品項的命中結果

| key | 關鍵字 | 候選數 | option_value（若穩定） | option_text |
|-----|--------|--------|-----------------------|-------------|
| cpu | AMD / R7 7700 MPK | | | |
| mb  | B650EM / FORCE / WIFI6E | | | |
| ram | UMAX / 64GB / 雙通32GB / 6000 / CL30 | | | |
| ssd | 金士頓 / KC3000 / 2TB | | | |
| cooler | 九州風神 / AG500 | | | |
| case | 視博通 / SW300 / 白 | | | |
| psu | Montech / CENTURY II / 850W | | | |
| os  | Windows 11 / 家用彩盒版 / 64位元 | | | |

## 需在 YAML 加 exclude 的品項

（若任一品項候選 > 1，列出該品項需要哪些 exclude 關鍵字）

## 後續 task 的 input

- Task 5 (config): `config/products.yaml` 的 8 筆 `match_all` / `exclude` / `option_value_hint` 請以此表填寫
- Task 6 (fetcher): 編碼處理參考本筆記第一節
- Task 7 (matcher): 測試 fixture 在 `tests/fixtures/evaluate_sample.html`
```

- [ ] **Step 4: commit**

```bash
git add scripts/probe.py scripts/probe-output.txt tests/fixtures/evaluate_sample.html docs/coolpc-html-notes.md
git commit -m "chore: probe coolpc HTML structure

- scripts/probe.py fetches 3x to test option_value stability
- saved fixture for fetcher unit tests
- docs/coolpc-html-notes.md documents encoding, option counts, per-item hits"
```

---

## Task 3: Pydantic 模型 (`src/models.py`)

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 寫失敗的測試**

`tests/test_models.py`:

```python
from datetime import date

import pytest
from pydantic import ValidationError

from src.models import (
    DailyReport,
    ItemDiff,
    MatchResult,
    RawProduct,
    TrackingRule,
)


def test_tracking_rule_requires_quantity_positive():
    with pytest.raises(ValidationError):
        TrackingRule(
            key="cpu", label="CPU", quantity=0, baseline_price=6490,
            match_all=["AMD"], exclude=[],
        )


def test_tracking_rule_option_value_hint_defaults_to_none():
    rule = TrackingRule(
        key="cpu", label="CPU", quantity=1, baseline_price=6490,
        match_all=["AMD"], exclude=[],
    )
    assert rule.option_value_hint is None


def test_raw_product_price_can_be_none():
    rp = RawProduct(option_value="1", option_text="foo", price=None, optgroup=None)
    assert rp.price is None


def test_match_result_mode_is_literal():
    rule = TrackingRule(
        key="cpu", label="CPU", quantity=1, baseline_price=6490,
        match_all=["AMD"], exclude=[],
    )
    with pytest.raises(ValidationError):
        MatchResult(rule=rule, raw=None, mode="invalid", confidence=0.0)


def test_item_diff_not_found_defaults():
    rule = TrackingRule(
        key="cpu", label="CPU", quantity=1, baseline_price=6490,
        match_all=["AMD"], exclude=[],
    )
    item = ItemDiff(
        rule=rule,
        today_price=None, today_line_total=None,
        yesterday_price=None,
        delta_yesterday_abs=None, delta_yesterday_pct=None,
        low_7d=None, low_30d=None, high_30d=None,
        delta_baseline_abs=None,
        is_7d_low=False, is_30d_low=False,
        not_found=True, warning=None,
    )
    assert item.not_found is True


def test_daily_report_composition():
    rule = TrackingRule(
        key="cpu", label="CPU", quantity=1, baseline_price=6490,
        match_all=["AMD"], exclude=[],
    )
    item = ItemDiff(
        rule=rule,
        today_price=6390, today_line_total=6390,
        yesterday_price=6490,
        delta_yesterday_abs=-100, delta_yesterday_pct=-1.54,
        low_7d=6390, low_30d=6390, high_30d=6500,
        delta_baseline_abs=-100,
        is_7d_low=True, is_30d_low=True,
        not_found=False, warning=None,
    )
    report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[item],
        total_today=6390,
        total_baseline=6490,
        total_delta_baseline_abs=-100,
        total_delta_yesterday_abs=-100,
        missing_item_keys=[],
        fetcher_warnings=[],
    )
    assert report.items[0].rule.key == "cpu"
    assert report.total_delta_baseline_abs == -100
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: 實作 `src/models.py`**

```python
"""Pydantic models shared across layers."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TrackingRule(BaseModel):
    key: str
    label: str
    quantity: int = Field(gt=0)
    baseline_price: int = Field(ge=0)
    match_all: list[str]
    exclude: list[str] = Field(default_factory=list)
    option_value_hint: str | None = None

    @field_validator("match_all")
    @classmethod
    def match_all_nonempty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("match_all must have at least one keyword")
        return v


class RawProduct(BaseModel):
    option_value: str
    option_text: str
    price: int | None
    optgroup: str | None


class MatchResult(BaseModel):
    rule: TrackingRule
    raw: RawProduct | None
    mode: Literal["option_value", "keyword", "not_found"]
    confidence: float = Field(ge=0.0, le=1.0)


class ItemDiff(BaseModel):
    rule: TrackingRule
    today_price: int | None
    today_line_total: int | None
    yesterday_price: int | None
    delta_yesterday_abs: int | None
    delta_yesterday_pct: float | None
    low_7d: int | None
    low_30d: int | None
    high_30d: int | None
    delta_baseline_abs: int | None
    is_7d_low: bool
    is_30d_low: bool
    not_found: bool
    warning: str | None


class DailyReport(BaseModel):
    run_date: date
    items: list[ItemDiff]
    total_today: int
    total_baseline: int
    total_delta_baseline_abs: int
    total_delta_yesterday_abs: int | None
    missing_item_keys: list[str]
    fetcher_warnings: list[str]
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 6 passed

- [ ] **Step 5: commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: pydantic models for TrackingRule / RawProduct / MatchResult / ItemDiff / DailyReport"
```

---

## Task 4: Config 載入 (`src/config.py` + `config/products.yaml`)

**Files:**
- Create: `config/products.yaml`
- Create: `src/config.py`
- Create: `tests/test_config.py`
- Create: `tests/fixtures/products_test.yaml`

- [ ] **Step 1: 建立 `config/products.yaml`**

根據 Task 2 的 `docs/coolpc-html-notes.md`。若 option_value 穩定，則 `option_value_hint` 填入探勘到的值；若不穩定，保持註解掉。

```yaml
baseline:
  date: "2026-02-24"
  notes: "現金優惠價 $56,919（含優惠 $90）"

products:
  - key: cpu
    label: "AMD R7 7700 MPK"
    quantity: 1
    baseline_price: 6490
    match_all: ["AMD", "R7 7700 MPK"]
    exclude: []
    # option_value_hint: "填入 probe 觀察到的穩定 value，若不穩定則刪掉本行"

  - key: mb
    label: "技嘉 B650EM FORCE WIFI6E"
    quantity: 1
    baseline_price: 3990
    match_all: ["B650EM", "FORCE", "WIFI6E"]
    exclude: []

  - key: ram
    label: "UMAX 64GB (32GB*2) DDR5-6000 CL30"
    quantity: 1
    baseline_price: 17999
    match_all: ["UMAX", "64GB", "雙通32GB", "6000", "CL30"]
    exclude: []

  - key: ssd
    label: "金士頓 KC3000 2TB"
    quantity: 2
    baseline_price: 9500
    match_all: ["金士頓", "KC3000", "2TB"]
    exclude: []

  - key: cooler
    label: "九州風神 AG500"
    quantity: 1
    baseline_price: 690
    match_all: ["九州風神", "AG500"]
    exclude: []

  - key: case
    label: "視博通 SW300 白"
    quantity: 1
    baseline_price: 1990
    match_all: ["視博通", "SW300", "白"]
    exclude: ["黑"]

  - key: psu
    label: "Montech CENTURY II 850W"
    quantity: 1
    baseline_price: 2990
    match_all: ["Montech", "CENTURY II", "850W"]
    exclude: []

  - key: os
    label: "Windows 11 家用彩盒版（組裝價）"
    quantity: 1
    baseline_price: 3860
    match_all: ["Windows 11", "家用彩盒版", "64位元", "組裝價"]
    exclude: []
```

**重要**：OS 的 baseline $3860 對應「組裝價」版 (value=12)，把「組裝價」加入 `match_all` 即可唯一命中；不加會變成中文標準版 ($4390)，跟 baseline 不符。詳見 `docs/coolpc-html-notes.md`。

- [ ] **Step 2: 建立 `tests/fixtures/products_test.yaml`**

```yaml
baseline:
  date: "2026-01-01"
  notes: "test baseline"

products:
  - key: cpu
    label: "Test CPU"
    quantity: 1
    baseline_price: 5000
    match_all: ["Test", "CPU"]
    exclude: []

  - key: ssd
    label: "Test SSD"
    quantity: 2
    baseline_price: 1000
    match_all: ["Test", "SSD"]
    exclude: []
    option_value_hint: "ABC123"
```

- [ ] **Step 3: 寫失敗的測試**

`tests/test_config.py`:

```python
from pathlib import Path

import pytest

from src.config import AppConfig, SMTPConfig, load_products

FIXTURE = Path(__file__).parent / "fixtures" / "products_test.yaml"


def test_load_products_from_yaml():
    cfg = load_products(FIXTURE)
    assert cfg.baseline.date == "2026-01-01"
    assert len(cfg.rules) == 2
    assert cfg.rules[0].key == "cpu"
    assert cfg.rules[1].quantity == 2
    assert cfg.rules[1].option_value_hint == "ABC123"


def test_load_products_validates_baseline_price():
    bad = """
baseline:
  date: "x"
products:
  - key: cpu
    label: CPU
    quantity: 1
    baseline_price: -10
    match_all: ["x"]
    exclude: []
"""
    path = Path("/tmp/_bad_products.yaml")
    path.write_text(bad)
    with pytest.raises(Exception):
        load_products(path)


def test_smtp_config_from_env(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "u@g.com")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("TO_EMAIL", "t@g.com")
    smtp = SMTPConfig.from_env()
    assert smtp.user == "u@g.com"
    assert smtp.to_email == "t@g.com"


def test_smtp_config_missing_env_raises(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("TO_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="SMTP_USER"):
        SMTPConfig.from_env()
```

- [ ] **Step 4: 跑測試，確認失敗**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 5: 實作 `src/config.py`**

```python
"""Config loading: YAML rules + .env SMTP."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.models import TrackingRule


class Baseline(BaseModel):
    date: str
    notes: str = ""


class AppConfig(BaseModel):
    baseline: Baseline
    rules: list[TrackingRule]


@dataclass(frozen=True)
class SMTPConfig:
    user: str
    password: str
    to_email: str
    host: str = "smtp.gmail.com"
    port: int = 587

    @classmethod
    def from_env(cls) -> SMTPConfig:
        required = {"SMTP_USER", "SMTP_PASS", "TO_EMAIL"}
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing env vars: {missing}")
        return cls(
            user=os.environ["SMTP_USER"],
            password=os.environ["SMTP_PASS"],
            to_email=os.environ["TO_EMAIL"],
        )


def load_products(path: Path | str) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    baseline = Baseline(**raw["baseline"])
    rules = [TrackingRule(**p) for p in raw["products"]]
    return AppConfig(baseline=baseline, rules=rules)
```

- [ ] **Step 6: 跑測試，確認通過**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 4 passed

- [ ] **Step 7: commit**

```bash
git add config/products.yaml src/config.py tests/test_config.py tests/fixtures/products_test.yaml
git commit -m "feat: config loader (YAML + SMTP from env)

- config/products.yaml with 8 items + baseline
- SMTPConfig from env vars (raises if missing)"
```

---

## Task 5: Fetcher 介面與例外 (`src/fetchers/base.py`)

**Files:**
- Create: `src/fetchers/base.py`
- Create: `tests/test_fetcher_base.py`

- [ ] **Step 1: 寫失敗的測試**

`tests/test_fetcher_base.py`:

```python
import pytest

from src.fetchers.base import Fetcher, FetcherError


def test_fetcher_is_abstract():
    with pytest.raises(TypeError):
        Fetcher()  # type: ignore[abstract]


def test_fetcher_error_is_exception():
    with pytest.raises(FetcherError, match="boom"):
        raise FetcherError("boom")
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
uv run pytest tests/test_fetcher_base.py -v
```

Expected: FAIL

- [ ] **Step 3: 實作 `src/fetchers/base.py`**

```python
"""Fetcher abstract base + exception."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import RawProduct


class FetcherError(Exception):
    """Raised when a fetcher cannot produce a valid snapshot."""


class Fetcher(ABC):
    @abstractmethod
    def fetch(self) -> list[RawProduct]:
        """Return raw products or raise FetcherError."""
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
uv run pytest tests/test_fetcher_base.py -v
```

Expected: 2 passed

- [ ] **Step 5: commit**

```bash
git add src/fetchers/base.py tests/test_fetcher_base.py
git commit -m "feat: Fetcher abstract base + FetcherError"
```

---

## Task 6: Coolpc Fetcher (`src/fetchers/coolpc.py`)

**Files:**
- Create: `src/fetchers/coolpc.py`
- Create: `tests/test_coolpc_fetcher.py`

- [ ] **Step 1: 寫失敗的測試（用 fixture HTML 做純解析測試）**

`tests/test_coolpc_fetcher.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from src.fetchers.base import FetcherError
from src.fetchers.coolpc import CoolpcFetcher

FIXTURE = Path(__file__).parent / "fixtures" / "evaluate_sample.html"


def test_parse_fixture_produces_many_options():
    html_bytes = FIXTURE.read_bytes()
    products = CoolpcFetcher.parse(html_bytes)
    assert len(products) >= 200, f"expected >=200, got {len(products)}"


def test_parse_extracts_prices():
    html_bytes = FIXTURE.read_bytes()
    products = CoolpcFetcher.parse(html_bytes)
    with_price = [p for p in products if p.price is not None]
    # 應該絕大多數 option 都有價格（coolpc 的 option text 裡都帶 "$..."）
    assert len(with_price) >= 200
    # 所有價格應為正整數
    for p in with_price:
        assert p.price > 0


def test_parse_extracts_amd_r7_7700_mpk():
    """確認 fixture 中有我們要盯的 CPU（驗證 probe 的結果）。"""
    html_bytes = FIXTURE.read_bytes()
    products = CoolpcFetcher.parse(html_bytes)
    hits = [
        p for p in products
        if "AMD" in p.option_text
        and "R7 7700 MPK" in p.option_text
        and p.price is not None
    ]
    assert len(hits) >= 1, "fixture should contain AMD R7 7700 MPK entry"


def test_parse_raises_when_too_few_options():
    tiny_html = b"<html><body><select name='Y1'><option value='1'>$100</option></select></body></html>"
    with pytest.raises(FetcherError, match="Only"):
        CoolpcFetcher.parse(tiny_html)


def test_parse_price_handles_comma_and_space():
    assert CoolpcFetcher._parse_price("foo $6,490 bar") == 6490
    assert CoolpcFetcher._parse_price("foo $ 6490 bar") == 6490
    assert CoolpcFetcher._parse_price("no price here") is None


def test_fetch_retries_on_transient_error(mocker):
    """httpx 連續失敗 2 次後第 3 次成功，應回傳正確結果。"""
    fixture_bytes = FIXTURE.read_bytes()

    # 前 2 次 raise，第 3 次回 200
    transient = httpx.ConnectError("transient")
    ok_resp = MagicMock()
    ok_resp.content = fixture_bytes
    ok_resp.text = fixture_bytes.decode("utf-8", errors="replace")
    ok_resp.raise_for_status = lambda: None

    get_mock = mocker.patch(
        "httpx.get",
        side_effect=[transient, transient, ok_resp],
    )
    mocker.patch("time.sleep")  # skip real sleeping

    fetcher = CoolpcFetcher()
    products = fetcher.fetch()

    assert len(products) >= 200
    assert get_mock.call_count == 3


def test_fetch_raises_after_max_retries(mocker):
    mocker.patch("httpx.get", side_effect=httpx.ConnectError("down"))
    mocker.patch("time.sleep")
    fetcher = CoolpcFetcher()
    with pytest.raises(FetcherError):
        fetcher.fetch()
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
uv run pytest tests/test_coolpc_fetcher.py -v
```

Expected: FAIL

- [ ] **Step 3: 實作 `src/fetchers/coolpc.py`**

```python
"""Coolpc evaluate.php fetcher."""
from __future__ import annotations

import random
import re
import time
from typing import ClassVar

import httpx
from bs4 import BeautifulSoup

from src.fetchers.base import Fetcher, FetcherError
from src.models import RawProduct

_PRICE_RE = re.compile(r"\$\s*([\d,]+)")
_MIN_OPTIONS = 200


class CoolpcFetcher(Fetcher):
    URL: ClassVar[str] = "https://www.coolpc.com.tw/evaluate.php"
    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    MAX_RETRIES: ClassVar[int] = 3
    BACKOFF_BASE: ClassVar[float] = 0.5

    def fetch(self) -> list[RawProduct]:
        time.sleep(random.uniform(1.0, 3.0))
        html_bytes = self._get_with_retry()
        return self.parse(html_bytes)

    def _get_with_retry(self) -> bytes:
        last_err: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = httpx.get(
                    self.URL, headers=self.HEADERS,
                    timeout=30.0, follow_redirects=True,
                )
                resp.raise_for_status()
                return resp.content
            except (httpx.HTTPError, httpx.HTTPStatusError) as e:
                last_err = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.BACKOFF_BASE * (2 ** attempt))
        raise FetcherError(f"HTTP failed after {self.MAX_RETRIES} attempts: {last_err}")

    @classmethod
    def parse(cls, html_bytes: bytes) -> list[RawProduct]:
        # Probe 發現 coolpc 雖宣告 charset=Big5，但實際需用 big5hkscs codec 才能正確解碼
        for encoding in ("big5hkscs", "utf-8"):
            try:
                html = html_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise FetcherError("Cannot decode HTML as big5hkscs or utf-8")

        soup = BeautifulSoup(html, "lxml")
        products: list[RawProduct] = []
        # Probe 發現：actual select names are n1..n30, not Y*
        for select in soup.select("select[name^='n']"):
            optgroup_label: str | None = None
            for el in select.descendants:
                if el.name == "optgroup":
                    optgroup_label = el.get("label")
                elif el.name == "option":
                    value = el.get("value", "") or ""
                    text = el.get_text(strip=True)
                    price = cls._parse_price(text)
                    products.append(RawProduct(
                        option_value=value,
                        option_text=text,
                        price=price,
                        optgroup=optgroup_label,
                    ))

        if len(products) < _MIN_OPTIONS:
            raise FetcherError(
                f"Only {len(products)} options — HTML structure may have changed"
            )
        return products

    @staticmethod
    def _parse_price(text: str) -> int | None:
        m = _PRICE_RE.search(text)
        return int(m.group(1).replace(",", "")) if m else None
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
uv run pytest tests/test_coolpc_fetcher.py -v
```

Expected: 7 passed

- [ ] **Step 5: commit**

```bash
git add src/fetchers/coolpc.py tests/test_coolpc_fetcher.py
git commit -m "feat: coolpc fetcher with retry + 200-option gate

- parse() handles utf-8/big5 encoding fallback
- fetch() retries 3x with exponential backoff on HTTPError
- raises FetcherError on <200 options"
```

---

## Task 7: Matcher (`src/matcher.py`)

**Files:**
- Create: `src/matcher.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: 寫失敗的測試（含 spec §9.2 五個必過案例）**

`tests/test_matcher.py`:

```python
from src.matcher import match
from src.models import RawProduct, TrackingRule


def _rule(key, match_all, exclude=None, quantity=1, baseline=1000, hint=None):
    return TrackingRule(
        key=key, label=key.upper(), quantity=quantity,
        baseline_price=baseline, match_all=match_all,
        exclude=exclude or [], option_value_hint=hint,
    )


def _raw(value, text, price):
    return RawProduct(option_value=value, option_text=text, price=price, optgroup=None)


# ---- 五個 must-pass 案例（spec §9.2）----

def test_ssd_rule_matches_single_unit_price_not_multiplied():
    """matcher 回單價，不管 quantity（quantity × unit 由 diff.py 算）。"""
    rule = _rule("ssd", ["KC3000", "2TB"], quantity=2, baseline=9500)
    raw = [_raw("1", "金士頓 KC3000 2TB $9500", 9500)]
    results = match([rule], raw)
    assert results[0].raw.price == 9500  # 單價，不是 19000


def test_case_white_not_matched_by_black():
    rule = _rule("case", ["視博通", "SW300", "白"], exclude=["黑"])
    raw = [
        _raw("1", "視博通 SW300 白 機殼 $1990", 1990),
        _raw("2", "視博通 SW300 黑 機殼 $1990", 1990),
    ]
    results = match([rule], raw)
    assert results[0].raw.option_value == "1"
    assert results[0].mode == "keyword"


def test_os_professional_version_excluded():
    rule = _rule("os", ["Windows 11", "家用彩盒版", "64位元"], exclude=["專業版"])
    raw = [
        _raw("1", "Windows 11 中文家用彩盒版 64位元 $3860", 3860),
        _raw("2", "Windows 11 專業版彩盒版 64位元 $5900", 5900),
    ]
    results = match([rule], raw)
    assert results[0].raw.price == 3860


def test_not_found_returns_null_price_does_not_raise():
    rule = _rule("cpu", ["AMD", "R7 7700 MPK"])
    raw = [_raw("1", "Intel i5-14600K $8500", 8500)]
    results = match([rule], raw)
    assert results[0].mode == "not_found"
    assert results[0].raw is None
    assert results[0].confidence == 0.0


def test_matcher_picks_shortest_when_multiple():
    rule = _rule("cpu", ["AMD", "R7 7700"])
    raw = [
        _raw("1", "AMD R7 7700 一般版 $6490", 6490),
        _raw("2", "AMD R7 7700 盒裝含散熱器 超值套餐版 $6890", 6890),
    ]
    results = match([rule], raw)
    assert results[0].raw.option_value == "1"
    assert results[0].confidence == 0.5  # 1/2 candidates


# ---- 其他行為測試 ----

def test_option_value_hint_priority():
    rule = _rule("cpu", ["AMD"], hint="STABLE123")
    raw = [
        _raw("STABLE123", "AMD R7 搭板 $6490", 6490),
        _raw("OTHER", "AMD R9 $12000", 12000),
    ]
    results = match([rule], raw)
    assert results[0].mode == "option_value"
    assert results[0].raw.option_value == "STABLE123"
    assert results[0].confidence == 1.0


def test_option_value_hint_falls_back_to_keyword_if_missing():
    """hint 填了但抓不到時，matcher 應降級到 keyword 模式。"""
    rule = _rule("cpu", ["AMD", "R7 7700 MPK"], hint="GONE")
    raw = [_raw("NEW", "AMD R7 7700 MPK $6490", 6490)]
    results = match([rule], raw)
    assert results[0].mode == "keyword"
    assert results[0].raw.option_value == "NEW"


def test_option_value_hint_ignored_if_match_all_fails():
    """probe 發現不同 <select> 的 option_value 會重複（例如 case/psu 都是 140）。
    若該 option_value 存在但 match_all 不通過，必須降級到 keyword 模式找對的產品。"""
    rule = _rule("case", ["視博通", "SW300", "白"], hint="140")
    raw = [
        # 同樣 value=140 的 psu（錯誤產品）
        _raw("140", "Montech CENTURY II 850W $2990", 2990),
        # 真正的 case
        _raw("999", "視博通 SW300 白 機殼 $1990", 1990),
    ]
    results = match([rule], raw)
    # value=140 的產品沒通過 match_all，應降級 keyword 找到正確的 value=999
    assert results[0].mode == "keyword"
    assert results[0].raw.option_value == "999"


def test_skips_options_with_null_price():
    """有些 option 沒有價格（例如分類標題），不應被 match 到。"""
    rule = _rule("cpu", ["AMD", "R7 7700"])
    raw = [
        _raw("1", "AMD R7 7700 (沒報價)", None),
        _raw("2", "AMD R7 7700 $6490", 6490),
    ]
    results = match([rule], raw)
    assert results[0].raw.option_value == "2"
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
uv run pytest tests/test_matcher.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.matcher'`

- [ ] **Step 3: 實作 `src/matcher.py`**

```python
"""Match TrackingRule[] against RawProduct[] using A+C hybrid."""
from __future__ import annotations

from src.models import MatchResult, RawProduct, TrackingRule


def match(rules: list[TrackingRule], raw: list[RawProduct]) -> list[MatchResult]:
    return [_match_one(rule, raw) for rule in rules]


def _match_one(rule: TrackingRule, raw: list[RawProduct]) -> MatchResult:
    # C mode: option_value_hint + 必須同時通過 match_all 過濾
    # (probe 發現 option_value 在不同 <select> 間會重複，例如 case 跟 psu 都是 value=140，
    #  所以必須以 match_all 作雙重驗證才不會誤認)
    if rule.option_value_hint:
        for r in raw:
            if (
                r.option_value == rule.option_value_hint
                and r.price is not None
                and all(kw in r.option_text for kw in rule.match_all)
                and not any(kw in r.option_text for kw in rule.exclude)
            ):
                return MatchResult(
                    rule=rule, raw=r, mode="option_value", confidence=1.0
                )
        # hint 失效或 match_all 不通過 → 降級到 A

    # A mode: match_all ALL, exclude NONE, price present
    candidates = [
        r for r in raw
        if all(kw in r.option_text for kw in rule.match_all)
        and not any(kw in r.option_text for kw in rule.exclude)
        and r.price is not None
    ]

    if not candidates:
        return MatchResult(rule=rule, raw=None, mode="not_found", confidence=0.0)

    if len(candidates) == 1:
        return MatchResult(
            rule=rule, raw=candidates[0], mode="keyword", confidence=1.0
        )

    # 多重命中 → 挑最短 option_text；confidence 下降
    best = min(candidates, key=lambda r: len(r.option_text))
    return MatchResult(
        rule=rule, raw=best, mode="keyword",
        confidence=1.0 / len(candidates),
    )
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
uv run pytest tests/test_matcher.py -v
```

Expected: 8 passed

- [ ] **Step 5: commit**

```bash
git add src/matcher.py tests/test_matcher.py
git commit -m "feat: A+C hybrid matcher

- C mode (option_value_hint) tried first, falls back to A on miss
- A mode: match_all ALL + exclude NONE + price present
- Multiple candidates: picks shortest option_text, confidence = 1/N"
```

---

## Task 8: Storage (`src/storage.py`)

**Files:**
- Create: `src/storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: 寫失敗的測試**

`tests/test_storage.py`:

```python
from datetime import datetime

import pytest

from src.models import MatchResult, RawProduct, TrackingRule
from src.storage import Storage


@pytest.fixture
def store():
    return Storage(":memory:")


def _rule(key):
    return TrackingRule(
        key=key, label=key.upper(), quantity=1, baseline_price=1000,
        match_all=[key], exclude=[],
    )


def _match(rule, price, value="1", mode="keyword"):
    raw = None if mode == "not_found" else RawProduct(
        option_value=value, option_text=f"{rule.key} $ {price}", price=price, optgroup=None,
    )
    return MatchResult(
        rule=rule, raw=raw, mode=mode,
        confidence=1.0 if mode != "not_found" else 0.0,
    )


def test_schema_is_created_on_init(store):
    cur = store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "runs" in tables
    assert "snapshots" in tables


def test_record_run_and_snapshots(store):
    run_id = store.record_run_start(datetime(2026, 4, 21, 1, 0))
    assert run_id > 0

    matches = [
        _match(_rule("cpu"), 6490),
        _match(_rule("mb"), 3990),
    ]
    store.record_snapshots(run_id, matches)
    store.record_run_end(run_id, datetime(2026, 4, 21, 1, 0, 10), "ok", 1500)

    cur = store.conn.execute(
        "SELECT rule_key, price, match_mode FROM snapshots WHERE run_id=? ORDER BY rule_key",
        (run_id,),
    )
    rows = cur.fetchall()
    assert rows == [("cpu", 6490, "keyword"), ("mb", 3990, "keyword")]


def test_not_found_stored_as_null_price(store):
    run_id = store.record_run_start(datetime(2026, 4, 21))
    store.record_snapshots(run_id, [_match(_rule("cpu"), 0, mode="not_found")])

    cur = store.conn.execute("SELECT price, match_mode FROM snapshots")
    row = cur.fetchone()
    assert row[0] is None
    assert row[1] == "not_found"


def test_query_last_price_before_today(store):
    # 昨天 run
    r1 = store.record_run_start(datetime(2026, 4, 20, 1, 0))
    store.record_snapshots(r1, [_match(_rule("cpu"), 6490)])
    store.record_run_end(r1, datetime(2026, 4, 20, 1, 0, 5), "ok", 1500)

    # 今天 run
    r2 = store.record_run_start(datetime(2026, 4, 21, 1, 0))
    store.record_snapshots(r2, [_match(_rule("cpu"), 6390)])
    store.record_run_end(r2, datetime(2026, 4, 21, 1, 0, 5), "ok", 1500)

    yesterday = store.query_last_price_before("cpu", datetime(2026, 4, 21, 0, 0))
    assert yesterday == 6490


def test_query_low_over_window(store):
    # 7 天 5 筆資料
    prices = [6500, 6450, 6400, 6500, 6390]
    for i, p in enumerate(prices):
        ts = datetime(2026, 4, 17 + i, 1, 0)
        run_id = store.record_run_start(ts)
        store.record_snapshots(run_id, [_match(_rule("cpu"), p)])
        store.record_run_end(run_id, ts, "ok", 1500)

    low = store.query_low("cpu", datetime(2026, 4, 17), datetime(2026, 4, 21, 23, 59))
    assert low == 6390


def test_query_low_returns_none_when_all_null(store):
    run_id = store.record_run_start(datetime(2026, 4, 21))
    store.record_snapshots(run_id, [_match(_rule("cpu"), 0, mode="not_found")])

    low = store.query_low("cpu", datetime(2026, 4, 1), datetime(2026, 4, 30))
    assert low is None
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
uv run pytest tests/test_storage.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.storage'`

- [ ] **Step 3: 實作 `src/storage.py`**

```python
"""SQLite storage for runs + snapshots."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from src.models import MatchResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  fetched_option_count INTEGER,
  error TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  rule_key TEXT NOT NULL,
  match_mode TEXT NOT NULL,
  price INTEGER,
  option_value TEXT,
  option_text TEXT,
  UNIQUE(run_id, rule_key)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_rule_price
  ON snapshots(rule_key, price);
"""


class Storage:
    def __init__(self, path: str | Path) -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def record_run_start(self, started_at: datetime) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (started_at, status) VALUES (?, 'running')",
            (started_at.isoformat(),),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def record_run_end(
        self, run_id: int, ended_at: datetime,
        status: str, fetched_option_count: int | None = None,
        error: str | None = None,
    ) -> None:
        self.conn.execute(
            "UPDATE runs SET ended_at=?, status=?, fetched_option_count=?, error=? "
            "WHERE id=?",
            (ended_at.isoformat(), status, fetched_option_count, error, run_id),
        )
        self.conn.commit()

    def record_snapshots(self, run_id: int, matches: list[MatchResult]) -> None:
        rows = []
        for m in matches:
            if m.raw is None:
                rows.append((run_id, m.rule.key, m.mode, None, None, None))
            else:
                rows.append((
                    run_id, m.rule.key, m.mode,
                    m.raw.price, m.raw.option_value, m.raw.option_text,
                ))
        self.conn.executemany(
            "INSERT INTO snapshots (run_id, rule_key, match_mode, price, option_value, option_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def query_last_price_before(
        self, rule_key: str, before: datetime,
    ) -> int | None:
        cur = self.conn.execute(
            "SELECT s.price FROM snapshots s JOIN runs r ON s.run_id = r.id "
            "WHERE s.rule_key=? AND r.started_at < ? AND s.price IS NOT NULL "
            "ORDER BY r.started_at DESC LIMIT 1",
            (rule_key, before.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def query_low(
        self, rule_key: str, start: datetime, end: datetime,
    ) -> int | None:
        cur = self.conn.execute(
            "SELECT MIN(s.price) FROM snapshots s JOIN runs r ON s.run_id = r.id "
            "WHERE s.rule_key=? AND r.started_at BETWEEN ? AND ? "
            "AND s.price IS NOT NULL",
            (rule_key, start.isoformat(), end.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None

    def query_high(
        self, rule_key: str, start: datetime, end: datetime,
    ) -> int | None:
        cur = self.conn.execute(
            "SELECT MAX(s.price) FROM snapshots s JOIN runs r ON s.run_id = r.id "
            "WHERE s.rule_key=? AND r.started_at BETWEEN ? AND ? "
            "AND s.price IS NOT NULL",
            (rule_key, start.isoformat(), end.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None

    def close(self) -> None:
        self.conn.close()
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
uv run pytest tests/test_storage.py -v
```

Expected: 6 passed

- [ ] **Step 5: commit**

```bash
git add src/storage.py tests/test_storage.py
git commit -m "feat: SQLite storage (runs + snapshots)

- schema auto-migration on connect
- record_run_start/end, record_snapshots
- query_last_price_before / query_low / query_high for diff layer"
```

---

## Task 9: Diff (`src/diff.py`)

**Files:**
- Create: `src/diff.py`
- Create: `tests/test_diff.py`

- [ ] **Step 1: 寫失敗的測試**

`tests/test_diff.py`:

```python
from datetime import datetime

import pytest

from src.config import AppConfig, Baseline
from src.diff import build_daily_report
from src.matcher import match
from src.models import MatchResult, RawProduct, TrackingRule
from src.storage import Storage


def _rule(key, qty=1, baseline=1000):
    return TrackingRule(
        key=key, label=key.upper(), quantity=qty, baseline_price=baseline,
        match_all=[key], exclude=[],
    )


def _match_for(rule, price):
    raw = RawProduct(
        option_value="x", option_text=f"{rule.key} $ {price}",
        price=price, optgroup=None,
    )
    return MatchResult(rule=rule, raw=raw, mode="keyword", confidence=1.0)


def _not_found(rule):
    return MatchResult(rule=rule, raw=None, mode="not_found", confidence=0.0)


def _seed_history(store, rule_key, prices_by_day):
    """prices_by_day: dict {datetime: int}"""
    for ts, price in prices_by_day.items():
        run_id = store.record_run_start(ts)
        if price is None:
            store.conn.execute(
                "INSERT INTO snapshots (run_id, rule_key, match_mode, price) "
                "VALUES (?, ?, 'not_found', NULL)",
                (run_id, rule_key),
            )
            store.conn.commit()
        else:
            raw = RawProduct(option_value="x", option_text="x", price=price, optgroup=None)
            rule = TrackingRule(
                key=rule_key, label=rule_key, quantity=1, baseline_price=1000,
                match_all=[rule_key], exclude=[],
            )
            m = MatchResult(rule=rule, raw=raw, mode="keyword", confidence=1.0)
            store.record_snapshots(run_id, [m])
        store.record_run_end(run_id, ts, "ok", 1500)


def test_delta_yesterday_is_today_minus_yesterday_single_rule():
    store = Storage(":memory:")
    _seed_history(store, "cpu", {datetime(2026, 4, 20, 1, 0): 6490})

    rule = _rule("cpu", baseline=6490)
    today = [_match_for(rule, 6390)]
    cfg = AppConfig(
        baseline=Baseline(date="2026-02-24", notes=""),
        rules=[rule],
    )

    report = build_daily_report(
        cfg=cfg, matches=today, store=store, now=datetime(2026, 4, 21, 1, 0),
    )
    item = report.items[0]
    assert item.today_price == 6390
    assert item.yesterday_price == 6490
    assert item.delta_yesterday_abs == -100
    assert item.delta_baseline_abs == -100


def test_line_total_equals_price_times_quantity():
    store = Storage(":memory:")
    rule = _rule("ssd", qty=2, baseline=9500)
    today = [_match_for(rule, 9500)]
    cfg = AppConfig(
        baseline=Baseline(date="2026-02-24", notes=""),
        rules=[rule],
    )
    report = build_daily_report(cfg=cfg, matches=today, store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    item = report.items[0]
    assert item.today_line_total == 19000


def test_is_7d_low_when_below_past_7d_min():
    store = Storage(":memory:")
    # 過去 7 天最低是 6400
    history = {
        datetime(2026, 4, 15, 1, 0): 6500,
        datetime(2026, 4, 16, 1, 0): 6450,
        datetime(2026, 4, 17, 1, 0): 6420,
        datetime(2026, 4, 18, 1, 0): 6400,
        datetime(2026, 4, 19, 1, 0): 6450,
        datetime(2026, 4, 20, 1, 0): 6500,
    }
    _seed_history(store, "cpu", history)

    rule = _rule("cpu", baseline=6490)
    today = [_match_for(rule, 6390)]  # 新低
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""), rules=[rule])

    report = build_daily_report(cfg=cfg, matches=today, store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    assert report.items[0].is_7d_low is True


def test_not_found_item_in_report():
    store = Storage(":memory:")
    rule = _rule("cpu", baseline=6490)
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""), rules=[rule])

    report = build_daily_report(
        cfg=cfg, matches=[_not_found(rule)], store=store,
        now=datetime(2026, 4, 21, 1, 0),
    )
    item = report.items[0]
    assert item.not_found is True
    assert item.today_price is None
    assert item.today_line_total is None
    assert "cpu" in report.missing_item_keys
    # spec §8.1：not_found 要進 fetcher_warnings 才能觸發 email 警告 banner
    assert any("cpu" in w for w in report.fetcher_warnings)


def test_total_today_skips_not_found_items():
    store = Storage(":memory:")
    cpu = _rule("cpu", baseline=6490)
    mb = _rule("mb", baseline=3990)
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""),
                    rules=[cpu, mb])
    matches = [_match_for(cpu, 6390), _not_found(mb)]

    report = build_daily_report(cfg=cfg, matches=matches, store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    # total 只加有價的；not_found 的 mb 不算
    assert report.total_today == 6390


def test_total_baseline_sums_all_items():
    store = Storage(":memory:")
    cpu = _rule("cpu", baseline=6490)
    mb = _rule("mb", baseline=3990)
    ssd = _rule("ssd", qty=2, baseline=9500)
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""),
                    rules=[cpu, mb, ssd])
    matches = [_match_for(cpu, 6490), _match_for(mb, 3990), _match_for(ssd, 9500)]

    report = build_daily_report(cfg=cfg, matches=matches, store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    # 6490 + 3990 + 9500×2 = 28,980 (對應 baseline: 6490 + 3990 + 19000 = 29,480)
    assert report.total_baseline == 29480


def test_match_with_low_confidence_emits_warning():
    store = Storage(":memory:")
    cpu = _rule("cpu", baseline=6490)
    cfg = AppConfig(baseline=Baseline(date="2026-02-24", notes=""), rules=[cpu])

    raw = RawProduct(option_value="x", option_text="AMD $6490", price=6490, optgroup=None)
    low_conf = MatchResult(rule=cpu, raw=raw, mode="keyword", confidence=0.5)

    report = build_daily_report(cfg=cfg, matches=[low_conf], store=store,
                                now=datetime(2026, 4, 21, 1, 0))
    item = report.items[0]
    assert item.warning is not None
    assert "2" in item.warning or "候選" in item.warning
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
uv run pytest tests/test_diff.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.diff'`

- [ ] **Step 3: 實作 `src/diff.py`**

```python
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
        assert price is not None, "matcher 保證非 not_found 時 price 不為 None"

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

        # is_7d_low / is_30d_low：今天價格 <= 過去 N 天的最低（含今天沒 push 進歷史的情況下）
        is_7d_low = low_7d is None or price <= low_7d
        is_30d_low = low_30d is None or price <= low_30d

        warning: str | None = None
        if m.confidence < 1.0:
            n_candidates = int(round(1.0 / m.confidence)) if m.confidence > 0 else 0
            warning = f"多重候選 {n_candidates} 個，confidence {m.confidence:.2f}"
            warnings.append(f"{rule.key}: {warning}")
        elif m.mode == "keyword" and rule.option_value_hint:
            warning = f"option_value_hint 失效，已用 keyword fallback"
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

    # total_delta_yesterday：若所有 items 的 yesterday 都有 → 可算；任一 missing → None
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
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
uv run pytest tests/test_diff.py -v
```

Expected: 7 passed

- [ ] **Step 5: commit**

```bash
git add src/diff.py tests/test_diff.py
git commit -m "feat: diff layer builds DailyReport from matches + history

- computes today_line_total = price × quantity
- queries yesterday / 7d low / 30d low from storage
- is_7d_low / is_30d_low flags
- warnings for low-confidence matches and hint fallback
- total_today skips not_found items; total_baseline sums all"
```

---

## Task 10: Renderer + Email 模板

**Files:**
- Create: `templates/email.html.j2`
- Create: `templates/alert.html.j2`
- Create: `src/renderer.py`
- Create: `tests/test_renderer.py`

- [ ] **Step 1: 建立 `templates/email.html.j2`**

內容照 spec §7.2。從 spec 直接複製 Jinja2 模板（已定稿）。

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, 'PingFang TC', sans-serif; max-width: 680px; margin: 0 auto;">

  <div style="background: {{ banner_bg }}; padding: 20px; border-radius: 8px;">
    <h2 style="margin: 0;">原價屋價格日報</h2>
    <div style="font-size: 13px; opacity: 0.8;">{{ run_date }}（購買日 2026-02-24）</div>
    <div style="font-size: 32px; font-weight: bold; margin-top: 8px;">
      今日總價 ${{ total_today | comma }}
    </div>
    <div style="font-size: 18px; color: {{ delta_color }};">
      vs 購買 {{ delta_baseline | signed_comma }}
      {% if delta_yesterday_abs is not none %}
        　vs 昨天 {{ delta_yesterday_abs | signed_comma }}
      {% endif %}
    </div>
  </div>

  {% if warnings %}
  <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 16px 0;">
    <strong>⚠️ 需注意：</strong>
    <ul style="margin: 4px 0;">
      {% for w in warnings %}<li>{{ w }}</li>{% endfor %}
    </ul>
  </div>
  {% endif %}

  <table cellpadding="8" style="width: 100%; border-collapse: collapse; margin-top: 16px;">
    <thead>
      <tr style="background: #f5f5f5; text-align: left; font-size: 13px;">
        <th>品項</th>
        <th style="text-align: right;">今日</th>
        <th style="text-align: right;">Δ 昨</th>
        <th style="text-align: right;">7d low</th>
        <th style="text-align: right;">30d low</th>
        <th style="text-align: right;">Δ 購買</th>
      </tr>
    </thead>
    <tbody>
      {% for item in items %}
      <tr style="border-bottom: 1px solid #eee;">
        <td>
          <div style="font-weight: 600;">{{ item.rule.label }}</div>
          <div style="font-size: 11px; color: #888;">
            {{ item.rule.key | upper }}
            {% if item.rule.quantity > 1 %} × {{ item.rule.quantity }}{% endif %}
            {% if item.warning %} · <span style="color: #c00;">{{ item.warning }}</span>{% endif %}
          </div>
        </td>
        {% if item.not_found %}
          <td colspan="5" style="text-align: center; color: #c00;">⚠️ 今日未找到</td>
        {% else %}
          <td style="text-align: right;">
            ${{ item.today_price | comma }}
            {% if item.is_7d_low %}<span title="近 7 天最低">🔻</span>{% endif %}
            {% if item.is_30d_low %}<span title="近 30 天最低">⭐</span>{% endif %}
          </td>
          <td style="text-align: right; color: {{ item.delta_yesterday_color }};">
            {{ item.delta_yesterday_abs | signed_comma_or_dash }}
          </td>
          <td style="text-align: right;">${{ item.low_7d | comma_or_dash }}</td>
          <td style="text-align: right;">${{ item.low_30d | comma_or_dash }}</td>
          <td style="text-align: right; color: {{ item.delta_baseline_color }};">
            {{ item.delta_baseline_abs | signed_comma }}
          </td>
        {% endif %}
      </tr>
      {% endfor %}
    </tbody>
    <tfoot>
      <tr style="font-weight: bold; background: #fafafa;">
        <td>合計</td>
        <td style="text-align: right;">${{ total_today | comma }}</td>
        <td style="text-align: right; color: {{ total_delta_yesterday_color }};">
          {{ total_delta_yesterday_abs | signed_comma_or_dash }}
        </td>
        <td colspan="2"></td>
        <td style="text-align: right; color: {{ total_delta_baseline_color }};">
          {{ total_delta_baseline_abs | signed_comma }}
        </td>
      </tr>
    </tfoot>
  </table>

  <div style="margin-top: 24px; font-size: 11px; color: #888;">
    baseline: 2026-02-24 現金優惠價 $56,919
    · run: {{ run_id }} · fetched {{ option_count }} options · took {{ elapsed_ms }}ms<br>
    <a href="https://www.coolpc.com.tw/evaluate.php">原價屋配單</a>
  </div>
</body>
</html>
```

- [ ] **Step 2: 建立 `templates/alert.html.j2`**

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, 'PingFang TC', sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #fde4e4; border-left: 6px solid #c92a2a; padding: 20px;">
    <h2 style="margin: 0; color: #c92a2a;">⚠️ 原價屋價格監控故障</h2>
    <div style="margin-top: 12px;">
      <strong>時間：</strong>{{ timestamp }}<br>
      <strong>錯誤類型：</strong>{{ error_type }}<br>
      <strong>訊息：</strong><code>{{ error_message }}</code><br>
      {% if run_id %}<strong>run_id：</strong>{{ run_id }}<br>{% endif %}
    </div>
    <div style="margin-top: 16px; font-size: 13px;">
      建議動作：檢查 GitHub Actions logs，若是 HTML 結構變了，手動跑 <code>scripts/probe.py</code> 查看新結構並更新 <code>config/products.yaml</code>。
    </div>
  </div>
</body>
</html>
```

- [ ] **Step 3: 寫失敗的測試**

`tests/test_renderer.py`:

```python
from datetime import date

from src.models import DailyReport, ItemDiff, TrackingRule
from src.renderer import render_daily_report, render_alert


def _rule(key, label, qty=1, baseline=1000):
    return TrackingRule(
        key=key, label=label, quantity=qty, baseline_price=baseline,
        match_all=[key], exclude=[],
    )


def _item(rule, today=None, y=None, low7=None, low30=None, delta_base=None,
          is_7d_low=False, not_found=False, warning=None):
    return ItemDiff(
        rule=rule,
        today_price=today,
        today_line_total=(today * rule.quantity) if today is not None else None,
        yesterday_price=y,
        delta_yesterday_abs=(today - y) if (today is not None and y is not None) else None,
        delta_yesterday_pct=None,
        low_7d=low7, low_30d=low30, high_30d=None,
        delta_baseline_abs=delta_base,
        is_7d_low=is_7d_low, is_30d_low=False,
        not_found=not_found, warning=warning,
    )


def test_render_produces_nonempty_html():
    cpu = _rule("cpu", "AMD R7 7700 MPK", baseline=6490)
    report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, today=6390, y=6490, low7=6390, low30=6390, delta_base=-100, is_7d_low=True)],
        total_today=6390, total_baseline=6490,
        total_delta_baseline_abs=-100,
        total_delta_yesterday_abs=-100,
        missing_item_keys=[], fetcher_warnings=[],
    )
    html = render_daily_report(report, run_id=42, option_count=1500, elapsed_ms=3200)
    assert "AMD R7 7700 MPK" in html
    assert "$6,390" in html
    assert "-100" in html
    assert "🔻" in html  # is_7d_low icon


def test_render_shows_not_found_row():
    cpu = _rule("cpu", "CPU")
    report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, not_found=True)],
        total_today=0, total_baseline=1000,
        total_delta_baseline_abs=-1000,
        total_delta_yesterday_abs=None,
        missing_item_keys=["cpu"], fetcher_warnings=["cpu 未找到"],
    )
    html = render_daily_report(report, run_id=1, option_count=1500, elapsed_ms=100)
    assert "今日未找到" in html
    assert "需注意" in html


def test_render_banner_bg_varies_by_baseline_delta():
    cpu = _rule("cpu", "CPU", baseline=1000)
    # 便宜了 → 綠底
    cheap_report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, today=900, y=1000, low7=900, low30=900, delta_base=-100)],
        total_today=900, total_baseline=1000,
        total_delta_baseline_abs=-100,
        total_delta_yesterday_abs=-100,
        missing_item_keys=[], fetcher_warnings=[],
    )
    html_cheap = render_daily_report(cheap_report, run_id=1, option_count=1500, elapsed_ms=0)
    assert "#e8f5e8" in html_cheap

    # 變貴了 → 紅底
    dear_report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, today=1100, y=1000, low7=1000, low30=1000, delta_base=100)],
        total_today=1100, total_baseline=1000,
        total_delta_baseline_abs=100,
        total_delta_yesterday_abs=100,
        missing_item_keys=[], fetcher_warnings=[],
    )
    html_dear = render_daily_report(dear_report, run_id=1, option_count=1500, elapsed_ms=0)
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
    """signed_comma_or_dash / comma_or_dash 對 None 回 '—'。"""
    cpu = _rule("cpu", "CPU")
    # 沒歷史資料（剛跑第一次）
    report = DailyReport(
        run_date=date(2026, 4, 21),
        items=[_item(cpu, today=1000, y=None, low7=None, low30=None, delta_base=0)],
        total_today=1000, total_baseline=1000,
        total_delta_baseline_abs=0,
        total_delta_yesterday_abs=None,
        missing_item_keys=[], fetcher_warnings=[],
    )
    html = render_daily_report(report, run_id=1, option_count=1500, elapsed_ms=0)
    assert "—" in html  # yesterday delta 應為 dash
```

- [ ] **Step 4: 跑測試，確認失敗**

```bash
uv run pytest tests/test_renderer.py -v
```

Expected: FAIL

- [ ] **Step 5: 實作 `src/renderer.py`**

```python
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

    # 為每個 item 注入顏色欄位（Jinja 裡直接用）
    items_with_color = []
    for it in report.items:
        d = it.model_dump()
        d["rule"] = it.rule  # 保留原物件方便 template 用 .label / .key
        d["delta_yesterday_color"] = _color_for(it.delta_yesterday_abs)
        d["delta_baseline_color"] = _color_for(it.delta_baseline_abs)
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
```

- [ ] **Step 6: 跑測試，確認通過**

```bash
uv run pytest tests/test_renderer.py -v
```

Expected: 5 passed

- [ ] **Step 7: commit**

```bash
git add templates/email.html.j2 templates/alert.html.j2 src/renderer.py tests/test_renderer.py
git commit -m "feat: Jinja2 renderer for daily + alert emails

- email.html.j2 with banner, warnings, 6-col table, footer
- alert.html.j2 for fetcher failures
- custom filters: comma / comma_or_dash / signed_comma / signed_comma_or_dash
- color helpers: green=cheaper, red=more expensive, gray=flat"
```

---

## Task 11: Notifier (`src/notifier.py`)

**Files:**
- Create: `src/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: 寫失敗的測試**

`tests/test_notifier.py`:

```python
from unittest.mock import MagicMock

import pytest

from src.config import SMTPConfig
from src.notifier import send_email


@pytest.fixture
def smtp_cfg():
    return SMTPConfig(user="u@g.com", password="pw", to_email="t@g.com")


def test_send_email_calls_smtp(mocker, smtp_cfg):
    fake_smtp = MagicMock()
    mocker.patch("smtplib.SMTP", return_value=fake_smtp)

    send_email(
        cfg=smtp_cfg,
        subject="test subject",
        html_body="<p>hi</p>",
    )

    fake_smtp.__enter__.assert_called_once()
    smtp_instance = fake_smtp.__enter__.return_value
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("u@g.com", "pw")
    smtp_instance.send_message.assert_called_once()


def test_send_email_retries_on_smtp_error(mocker, smtp_cfg):
    import smtplib

    fake_smtp = MagicMock()
    # 第一次拋例外，第二次成功
    call_count = [0]
    def _ctx_enter(*a, **k):
        return fake_smtp.__enter__.return_value

    def _send_message_side(*a, **k):
        call_count[0] += 1
        if call_count[0] == 1:
            raise smtplib.SMTPException("transient")
        # 成功第二次
    fake_smtp.__enter__.return_value.send_message = MagicMock(side_effect=_send_message_side)

    mocker.patch("smtplib.SMTP", return_value=fake_smtp)
    mocker.patch("time.sleep")

    send_email(cfg=smtp_cfg, subject="s", html_body="<p>x</p>")

    assert call_count[0] == 2


def test_send_email_raises_after_max_retries(mocker, smtp_cfg):
    import smtplib

    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value.send_message = MagicMock(
        side_effect=smtplib.SMTPException("down")
    )
    mocker.patch("smtplib.SMTP", return_value=fake_smtp)
    mocker.patch("time.sleep")

    with pytest.raises(smtplib.SMTPException):
        send_email(cfg=smtp_cfg, subject="s", html_body="<p>x</p>")
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
uv run pytest tests/test_notifier.py -v
```

Expected: FAIL

- [ ] **Step 3: 實作 `src/notifier.py`**

```python
"""SMTP email sending with retry."""
from __future__ import annotations

import smtplib
import time
from email.message import EmailMessage

from src.config import SMTPConfig

_MAX_RETRIES = 2


def send_email(
    *, cfg: SMTPConfig, subject: str, html_body: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.user
    msg["To"] = cfg.to_email
    msg.set_content("此信為 HTML 版本，請用支援 HTML 的郵件客戶端閱讀。")
    msg.add_alternative(html_body, subtype="html")

    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(cfg.host, cfg.port) as server:
                server.starttls()
                server.login(cfg.user, cfg.password)
                server.send_message(msg)
            return
        except smtplib.SMTPException as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(1.0 * (2 ** attempt))
    assert last_err is not None
    raise last_err
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
uv run pytest tests/test_notifier.py -v
```

Expected: 3 passed

- [ ] **Step 5: commit**

```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat: SMTP notifier with 2x retry on SMTPException"
```

---

## Task 12: Main entrypoint (`src/main.py`)

**Files:**
- Create: `src/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: 寫整合測試（dry-run 流程，mock fetcher）**

`tests/test_main.py`:

```python
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.main import main


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "prices.db"


@pytest.fixture
def products_yaml(tmp_path):
    yaml_path = tmp_path / "products.yaml"
    yaml_path.write_text("""
baseline:
  date: "2026-02-24"
  notes: test

products:
  - key: cpu
    label: "Test CPU"
    quantity: 1
    baseline_price: 6490
    match_all: ["AMD", "R7 7700 MPK"]
    exclude: []

  - key: ssd
    label: "Test SSD"
    quantity: 2
    baseline_price: 9500
    match_all: ["金士頓", "KC3000", "2TB"]
    exclude: []
""", encoding="utf-8")
    return yaml_path


def _fake_raw_products():
    from src.models import RawProduct
    return [
        RawProduct(option_value="1", option_text="AMD R7 7700 MPK $6490", price=6490, optgroup="CPU"),
        RawProduct(option_value="2", option_text="金士頓 KC3000 2TB $9500", price=9500, optgroup="SSD"),
    ] + [
        RawProduct(option_value=str(i), option_text=f"filler{i} ${100 + i}",
                   price=100 + i, optgroup=None)
        for i in range(300)
    ]


def test_main_dry_run_does_not_send_email(mocker, tmp_db, products_yaml, capsys):
    mocker.patch("src.fetchers.coolpc.CoolpcFetcher.fetch", return_value=_fake_raw_products())
    send_mock = mocker.patch("src.notifier.send_email")

    rc = main(argv=["--dry-run",
                    "--config", str(products_yaml),
                    "--db", str(tmp_db)])

    assert rc == 0
    assert send_mock.call_count == 0
    captured = capsys.readouterr()
    assert "matched 2/2" in captured.out
    assert "would send" in captured.out or "dry-run" in captured.out


def test_main_real_run_sends_email(mocker, tmp_db, products_yaml):
    mocker.patch("src.fetchers.coolpc.CoolpcFetcher.fetch", return_value=_fake_raw_products())
    send_mock = mocker.patch("src.notifier.send_email")
    mocker.patch.dict("os.environ", {
        "SMTP_USER": "u@g.com", "SMTP_PASS": "pw", "TO_EMAIL": "t@g.com",
    })

    rc = main(argv=["--config", str(products_yaml),
                    "--db", str(tmp_db)])

    assert rc == 0
    assert send_mock.call_count == 1
    # 驗證傳入 send_email 的主旨格式
    kwargs = send_mock.call_args.kwargs
    assert "原價屋" in kwargs["subject"]


def test_main_fetcher_failure_sends_alert_and_exits_nonzero(mocker, tmp_db, products_yaml):
    from src.fetchers.base import FetcherError
    mocker.patch("src.fetchers.coolpc.CoolpcFetcher.fetch",
                 side_effect=FetcherError("Only 45 options"))
    send_mock = mocker.patch("src.notifier.send_email")
    mocker.patch.dict("os.environ", {
        "SMTP_USER": "u@g.com", "SMTP_PASS": "pw", "TO_EMAIL": "t@g.com",
    })

    rc = main(argv=["--config", str(products_yaml), "--db", str(tmp_db)])

    assert rc == 1
    # 應寄 alert email
    assert send_mock.call_count == 1
    subject = send_mock.call_args.kwargs["subject"]
    assert "故障" in subject or "alert" in subject.lower()
```

- [ ] **Step 2: 跑測試，確認失敗**

```bash
uv run pytest tests/test_main.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.main'`

- [ ] **Step 3: 實作 `src/main.py`**

```python
"""Entrypoint: fetch → match → store → diff → render → notify."""
from __future__ import annotations

import argparse
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.config import SMTPConfig, load_products
from src.diff import build_daily_report
from src.fetchers.base import FetcherError
from src.fetchers.coolpc import CoolpcFetcher
from src.matcher import match
from src.notifier import send_email
from src.renderer import render_alert, render_daily_report
from src.storage import Storage


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Coolpc price monitor daily run")
    p.add_argument("--dry-run", action="store_true",
                   help="不發 email、不寫 DB（只印到 stdout）")
    p.add_argument("--config", default="config/products.yaml",
                   help="YAML 設定檔路徑")
    p.add_argument("--db", default="data/prices.db",
                   help="SQLite 資料庫路徑")
    return p.parse_args(argv)


def _compose_subject(run_date, total_today, delta_baseline) -> str:
    sign = "+" if delta_baseline > 0 else ""
    return f"[原價屋] {run_date} 今日 ${total_today:,}（vs 購買 {sign}{delta_baseline:,}）"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log = logging.getLogger("coolpc")
    load_dotenv()
    args = _parse_args(argv)

    cfg = load_products(args.config)
    log.info("loaded config: %d rules, baseline date=%s",
             len(cfg.rules), cfg.baseline.date)

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

        html = render_daily_report(
            report, run_id=run_id, option_count=option_count, elapsed_ms=elapsed_ms,
        )
        subject = _compose_subject(
            report.run_date, report.total_today, report.total_delta_baseline_abs,
        )

        print(f"today total ${report.total_today:,} "
              f"(vs baseline {report.total_delta_baseline_abs:+,})")

        status = "partial" if report.missing_item_keys else "ok"

        if args.dry_run:
            print("--- dry-run: HTML preview ---")
            print(html)
            print("--- would send email with subject:", subject)
            store.record_run_end(run_id, datetime.now(), status, option_count)
            return 0

        smtp_cfg = SMTPConfig.from_env()
        send_email(cfg=smtp_cfg, subject=subject, html_body=html)
        store.record_run_end(run_id, datetime.now(), status, option_count)
        log.info("sent email to %s", smtp_cfg.to_email)
        return 0

    except FetcherError as e:
        log.error("fetcher failed: %s", e)
        store.record_run_end(
            run_id, datetime.now(), "failed", error=str(e),
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
                send_email(
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
            run_id, datetime.now(), "failed", error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
        )
        return 1
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑測試，確認通過**

```bash
uv run pytest tests/test_main.py -v
```

Expected: 3 passed

- [ ] **Step 5: 跑全部 suite 確認所有測試通過**

```bash
uv run pytest -v
```

Expected: 所有測試 passed（models 6 + config 4 + fetcher_base 2 + coolpc 7 + matcher 8 + storage 6 + diff 7 + renderer 5 + notifier 3 + main 3 = 51 passed）

- [ ] **Step 6: lint**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: `All checks passed!` / no diffs.

若 format 有 diff，跑 `uv run ruff format .` 修掉再 commit。

- [ ] **Step 7: 真實 dry-run（需要網路）驗證**

```bash
uv run python -m src.main --dry-run
```

Expected: 終端印出
```
fetched <N> options → matched 8/8 items
today total $<xxx> (vs baseline <+/-xx>)
--- dry-run: HTML preview ---
<HTML 內容>
--- would send email with subject: [原價屋] 2026-04-21 今日 $xxx（vs 購買 ...）
```

**若某品項 not_found**：回去調 `config/products.yaml` 的 `match_all` / `exclude`，重跑直到 `matched 8/8`。

- [ ] **Step 8: commit**

```bash
git add src/main.py tests/test_main.py
git commit -m "feat: main entrypoint wires fetch→match→store→diff→render→notify

- --dry-run skips email + DB writes
- FetcherError → alert email + exit 1
- unexpected Exception → runs.status='failed' + exit 1
- logs + stdout summary"
```

---

## Task 13: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/daily.yml`

這一步主要是靜態設定檔 + 手動驗證（需要 push 到 GitHub 才能測，沒法本地跑全流程）。

- [ ] **Step 1: 建立 `.github/workflows/daily.yml`**

```yaml
name: Daily price check

on:
  schedule:
    - cron: "0 1 * * *"          # UTC 01:00 = Taipei 09:00
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Dry run (不發 email)"
        type: boolean
        default: false

permissions:
  contents: write

jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    concurrency:
      group: daily-check
      cancel-in-progress: false

    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true

      - name: Install deps
        run: uv sync --frozen

      - name: Run watcher
        env:
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          TO_EMAIL:  ${{ secrets.TO_EMAIL }}
          TZ: Asia/Taipei
        run: |
          if [ "${{ inputs.dry_run }}" = "true" ]; then
            uv run python -m src.main --dry-run
          else
            uv run python -m src.main
          fi

      - name: Commit DB update
        if: success() && inputs.dry_run != 'true'
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/prices.db
          if git diff --staged --quiet; then
            echo "No DB changes"
          else
            git commit -m "chore: daily snapshot $(date -Iseconds)"
            git push
          fi

      - name: Monthly tag backup
        if: success() && inputs.dry_run != 'true'
        run: |
          TAG="snapshot-$(date +%Y-%m)"
          if ! git rev-parse "$TAG" >/dev/null 2>&1; then
            git tag "$TAG"
            git push --tags
          fi
```

- [ ] **Step 2: commit workflow**

```bash
git add .github/workflows/daily.yml
git commit -m "ci: daily GitHub Actions cron at 09:00 Taipei

- cron 0 1 * * * (UTC)
- workflow_dispatch with dry_run toggle
- commits data/prices.db back on success (non-dry-run)
- monthly tag backup (snapshot-YYYY-MM)
- concurrency guard prevents overlapping runs"
```

- [ ] **Step 3: 把 repo push 到 GitHub**

```bash
# 先在 GitHub 手動建 repo（或 gh repo create cool-pc-price-monitor --private --source=. --push）
gh repo create cool-pc-price-monitor --private --source=. --push
```

- [ ] **Step 4: 設 GitHub Secrets**

```bash
gh secret set SMTP_USER -b "your.gmail@gmail.com"
gh secret set SMTP_PASS -b "xxxx-xxxx-xxxx-xxxx"  # Gmail 應用程式密碼
gh secret set TO_EMAIL  -b "your.gmail@gmail.com"
```

或在 GitHub UI：Settings → Secrets and variables → Actions → New repository secret。

- [ ] **Step 5: 設 branch protection（禁止 force push main）**

GitHub UI：Settings → Branches → Add rule → Branch name pattern `main` → 勾 "Do not allow bypassing the above settings" + "Restrict pushes that create matching branches" / "Require linear history" 視需求。關鍵是 "Allow force pushes: disabled"。

- [ ] **Step 6: 手動觸發一次 dry_run**

```bash
gh workflow run "Daily price check" -f dry_run=true
gh run watch
```

Expected: workflow 綠燈；logs 顯示 `fetched N options → matched 8/8 items → would send`。

- [ ] **Step 7: 手動觸發一次 real run（第一次實際寄信）**

```bash
gh workflow run "Daily price check" -f dry_run=false
gh run watch
```

Expected: workflow 綠燈；信箱收到一封 HTML email；repo 多一個 commit `chore: daily snapshot ...`。

- [ ] **Step 8: 驗收 spec §11 的標準**

- [ ] 收到的 email 在手機上表格能正常顯示（橫軸不跑版）
- [ ] 表格 6 欄齊全、顏色正確
- [ ] `data/prices.db` 在 repo 上被 commit

---

## Task 14: 文件收尾

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新 `README.md`**

重寫 README，加入「如何新增品項」「如何換 baseline」「如何處理 option_value_hint 失效」等運維說明。

```markdown
# Cool PC Price Monitor

Daily-run tool that monitors prices on coolpc.com.tw for a fixed 8-item shopping list and emails an HTML digest tracking price trends vs purchase date / 7-day low / 30-day low. Single user, personal tool. Runs via GitHub Actions daily at 09:00 Taipei.

Spec: `docs/superpowers/specs/2026-04-21-coolpc-price-monitor-design.md`
Plan: `docs/superpowers/plans/2026-04-21-coolpc-price-monitor.md`

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
uv run python scripts/probe.py          # re-probe coolpc HTML
```

## Schedule

GitHub Actions `daily.yml` runs at UTC 01:00 (= Taipei 09:00). Manual trigger:

```bash
gh workflow run "Daily price check" -f dry_run=true
gh workflow run "Daily price check"
```

## Adding / Changing Items

Edit `config/products.yaml`. Each entry:

```yaml
- key: <short-id>
  label: <display name>
  quantity: 1
  baseline_price: <your purchase price, unit>
  match_all: [<keywords all must appear in option_text>]
  exclude: [<keywords that must NOT appear>]
  # option_value_hint: <optional stable <option value> — see probe notes>
```

After editing:
1. `uv run python -m src.main --dry-run` to confirm `matched N/N items`
2. Commit YAML change

## Resetting the Baseline

If you buy a new set and want to re-anchor the trend:
1. Edit `config/products.yaml`:
   - Update each item's `baseline_price` and `quantity`
   - Update `baseline.date` and `baseline.notes`
2. Commit + push — next run will show `vs 購買` relative to the new baseline

The SQLite DB is unaffected (still has full price history).

## When option_value_hint Fails

If a product's `<option value>` changes (coolpc reshuffles IDs), matcher falls back to keyword mode and email shows a warning. To fix:
1. `uv run python scripts/probe.py` — find the new stable value
2. Update the affected item's `option_value_hint` in `config/products.yaml`
3. `--dry-run` to verify

## Tests

See `tests/`. Key fixtures in `tests/fixtures/`. To regenerate the evaluate.php fixture:

```bash
uv run python scripts/probe.py
```

## Storage

SQLite DB at `data/prices.db`, committed back to the repo by GitHub Actions after each successful real run. Monthly tag backup (`snapshot-YYYY-MM`) guards against force-push data loss.

## Architecture

See `CLAUDE.md` for non-obvious design decisions.
```

- [ ] **Step 2: 驗證 `CLAUDE.md`**

Task 1 已建 `CLAUDE.md`；確認內容涵蓋：
- Project overview（指向 spec）
- Tech stack
- Commands
- Architecture non-obvious points（pluggable fetcher / baseline in YAML / A+C matching / not_found non-fatal / fetcher fatal / DB commit guard / 200-option gate）
- Reference to implementation plan

若有遺漏，補上。

- [ ] **Step 3: commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: README operations guide + CLAUDE.md confirmation"
```

- [ ] **Step 4: 最終驗收**

- [ ] `uv run pytest -v` — 全綠
- [ ] `uv run ruff check .` — clean
- [ ] `uv run python -m src.main --dry-run` — `matched 8/8`，印出 HTML
- [ ] 手動把某個 `match_all` 改壞（例如 `["AMD", "XXXXX"]`），再 dry-run → `matched 7/8`，HTML 有警告區塊。改回來。
- [ ] GitHub Actions 手動觸發 real run 成功，信箱收到 email，DB 被 commit 回 main

---

## 驗收標準（整個 plan 結束後）

- [ ] `uv run python -m src.main --dry-run` 印出：
      `fetched <N> options → matched 8/8 items`
      `today total $<xxx> (vs baseline <+/-xx>)`
      `--- would send email with subject: [原價屋] YYYY-MM-DD 今日 $xxx（vs 購買 ...）`
- [ ] 當天跑兩次，第二次 email 的「Δ 昨」欄會反映跟第一次的差（不是 0）
- [ ] 故意把 `cpu` 的 `match_all` 改壞 → dry-run 顯示 CPU 在 `missing_item_keys`，HTML 頂部有黃色警告區塊
- [ ] GitHub Actions 第一次 real run 後，信箱收到一封 HTML email（手機顯示正常），`data/prices.db` 被 commit 回 main

---

## 未來工作（Spec §12）

**2026-05-21 提醒節點**：累積 1 個月資料後加 GitHub Pages 趨勢圖視覺化（Spec §12 D 方案）。使用者已要求屆時提醒——brainstorming 階段已存入 project memory，將由 `schedule` skill 建遠端 trigger。
