# Cool PC 價格監控 — 設計文件

> 日期：2026-04-21
> 狀態：Draft — 待使用者審閱後定稿
> 作者：kuolun（與 Claude Code 共同 brainstorm）

## 1. 目標與動機

每日監控原價屋線上報價 (<https://www.coolpc.com.tw/evaluate.php>) 上使用者 2026-02-24 購買的 8 項組裝電腦零件，追蹤漲跌趨勢並每日發送 HTML email 日報。

**使用者視角**：已購買完畢，通知為資訊用途（「買早還是買貴」的趨勢）而非觸發行動。因此漲跌都要通知，目的是**看趨勢**，不是**觸發決策**。

單一使用者、個人工具、無對外服務。

## 2. Baseline 資料（購買日 2026-02-24 11:06）

| 品項 | 品名 | 數量 | 單價 | 小計 |
|------|------|------|------|------|
| CPU | AMD R7 7700 MPK（含風扇）| 1 | 6490 | 6490 |
| MB | 技嘉 B650EM FORCE WIFI6E | 1 | 3990 | 3990 |
| RAM | UMAX 64GB (32GB*2) DDR5-6000 CL30 | 1 | 17999 | 17999 |
| SSD | 金士頓 KC3000 2TB | 2 | 9500 | 19000 |
| 散熱 | 九州風神 AG500 | 1 | 690 | 690 |
| 機殼 | 視博通 SW300 白 | 1 | 1990 | 1990 |
| 電源 | Montech CENTURY II 850W | 1 | 2990 | 2990 |
| OS | Windows 11 家用彩盒版 | 1 | 3860 | 3860 |
| **合計現金價** | | | | **57009** |
| 優惠 | | | | −90 |
| **現金優惠價（baseline）** | | | | **56919** |

Baseline 存 YAML 設定檔，不存 DB。使用者可隨時編輯（例如重設基準）。

## 3. 需求決策

| ID | 決策 | 選項 |
|----|------|------|
| Q1 | 監控範圍 | **A**：精準清單模式（只盯這 8 項，關鍵字比對商品名稱） |
| Q2 | 通知觸發 | **A**：任何變動都通知（漲跌皆發，目的看趨勢） |
| Q3 | 頻率 + Email 結構 | **A**：每日 09:00 跑一次，日報式 email，內嵌 7/30 天對比 |
| Q4 | 商品比對策略 | **A+C 混合**：YAML 白名單 (`match_all` / `exclude`) + 若 `<option value>` 穩定則升級為編號比對。找不到 → email 警告。 |
| Q5 | Email 格式 | **A**：HTML 表格（Jinja2 + 顏色碼 + 手機友善） |
| 架構 | 抽象程度 | **方向 1**：Mirror house-watcher（pluggable fetcher, SQLite commit 回 branch） |

## 4. 架構

### 4.1 檔案結構

```
cool-pc-price-monitor/
├── src/
│   ├── __init__.py
│   ├── main.py            # entrypoint, argparse, --dry-run / --force-email
│   ├── config.py          # 讀 config/products.yaml + .env（SMTP）
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py        # class Fetcher: def fetch() -> list[RawProduct]
│   │   └── coolpc.py      # 解析 https://www.coolpc.com.tw/evaluate.php
│   ├── models.py          # pydantic: RawProduct, TrackingRule, ItemDiff, DailyReport
│   ├── matcher.py         # RawProduct[] × config rules → MatchResult[]
│   ├── storage.py         # sqlite3 CRUD
│   ├── diff.py            # 對每個品項算 vs yesterday / 7d low / 30d low / baseline
│   ├── renderer.py        # Jinja2 → HTML string
│   └── notifier.py        # smtplib 寄信
├── templates/
│   ├── email.html.j2      # 日報模板
│   └── alert.html.j2      # 系統故障模板
├── config/
│   └── products.yaml      # 8 個品項的 match_all / exclude / quantity / baseline_price
├── data/
│   └── prices.db          # commit 回 branch by GitHub Actions
├── tests/
│   ├── fixtures/
│   │   └── evaluate_sample.html
│   ├── test_coolpc_fetcher.py
│   ├── test_matcher.py
│   ├── test_storage.py
│   ├── test_diff.py
│   └── test_renderer.py
├── docs/
│   ├── coolpc-html-notes.md       # 實作前探 HTML 的結論
│   └── superpowers/specs/          # 本文件
├── .github/workflows/
│   └── daily.yml          # cron: 0 1 * * *  (UTC 01:00 = Taipei 09:00)
├── pyproject.toml         # uv
├── .env.example           # SMTP_USER / SMTP_PASS / TO_EMAIL
├── .gitignore
├── CLAUDE.md
└── README.md
```

### 4.2 端到端流程（單次 `python -m src.main`）

1. 讀 `config/products.yaml` → 8 個 `TrackingRule`
2. `fetchers.coolpc.fetch()`
   - GET `evaluate.php`（httpx, UA 標頭, 1~3s random sleep）
   - BeautifulSoup 解析 `<select>` 裡的 `<option>`
   - 每個 option → `RawProduct(option_value, option_text, price, optgroup)`
   - 若 `<option>` 總數 < 200 → 判定 HTML 結構變了，raise `FetcherError`
3. `matcher.match(rules, raw_products)`
   - 對每個 `TrackingRule`：先試 `option_value_hint`（C 模式），再退回 `match_all`/`exclude`（A 模式）
   - 回傳 `[MatchResult]`：(rule, raw_product | None, mode, confidence)
4. `storage.record_run(run_id, timestamp, status)`
   `storage.record_snapshot(run_id, matches)`
5. `diff(storage, matches)` → 對每個品項算 `ItemDiff`：today_price, delta_yesterday, low_7d, low_30d, delta_baseline, is_7d_low, is_30d_low
6. `renderer.render(DailyReport)` → HTML 字串
7. `notifier.send(html)`（若 `--dry-run` 則印 stdout）
8. 任一品項 `not_found` → HTML 頂部顯示警告區塊，**仍寄信**，不中斷
9. 若 fetcher 整個失敗 → 寄「系統故障」alert email（`templates/alert.html.j2`），exit 1

### 4.3 關鍵邊界

- **`Fetcher` 是抽象介面**：未來加樂屋、欣亞，新增一個 fetcher 檔不動 matcher/diff/renderer
- **`storage.py` 只暴露函數**：`record_*` / `query_*`，不讓上層碰 SQL
- **`diff.py` 純函數**：讀 storage + 當次 matches 產 `DailyReport`，好測

## 5. 資料模型

### 5.1 Pydantic 模型（`src/models.py`）

```python
class TrackingRule(BaseModel):
    key: str                       # "cpu" / "mb" / "ram" / "ssd" / ...
    label: str                     # 顯示用標籤
    quantity: int                  # 1, 2, ...
    baseline_price: int            # 單價（SSD 9500，不是 19000）
    match_all: list[str]           # 必含關鍵字
    exclude: list[str] = []        # 排除關鍵字
    option_value_hint: str | None = None   # 若已鎖定穩定 ID

class RawProduct(BaseModel):
    option_value: str
    option_text: str
    price: int | None              # 從 "$6490" 解出；某些 option 沒價格
    optgroup: str | None           # 分類文字

class MatchResult(BaseModel):
    rule: TrackingRule
    raw: RawProduct | None
    mode: Literal["option_value", "keyword", "not_found"]
    confidence: float              # 1.0 = option_value；keyword = 1/候選數

class ItemDiff(BaseModel):
    rule: TrackingRule
    today_price: int | None
    today_line_total: int | None   # today_price × quantity
    yesterday_price: int | None
    delta_yesterday_abs: int | None
    delta_yesterday_pct: float | None
    low_7d: int | None
    low_30d: int | None
    high_30d: int | None
    delta_baseline_abs: int | None      # today - baseline
    is_7d_low: bool
    is_30d_low: bool
    not_found: bool
    warning: str | None            # "match_all 命中但多重候選" 之類

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

### 5.2 SQLite Schema（`data/prices.db`）

```sql
CREATE TABLE runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,              -- ISO8601 UTC
  ended_at TEXT,
  status TEXT NOT NULL,                  -- 'ok' | 'partial' | 'failed'
  fetched_option_count INTEGER,
  error TEXT
);

CREATE TABLE snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  rule_key TEXT NOT NULL,                -- 'cpu' 'mb' 'ram' ...
  match_mode TEXT NOT NULL,              -- 'option_value' | 'keyword' | 'not_found'
  price INTEGER,                         -- 單價；NULL = not_found
  option_value TEXT,
  option_text TEXT,
  UNIQUE(run_id, rule_key)
);

CREATE INDEX idx_snapshots_rule_price ON snapshots(rule_key, price);
```

**資料量試算**：8 品項 × 365 天 = 2,920 rows/年，SQLite 含索引 <200 KB，commit 回 branch 完全可行。

### 5.3 YAML 設定檔（`config/products.yaml`）

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
    label: "Windows 11 家用彩盒版"
    quantity: 1
    baseline_price: 3860
    match_all: ["Windows 11", "家用彩盒版", "64位元"]
    exclude: ["專業版", "教育版"]
```

## 6. Fetcher & Matcher 細節

### 6.1 `fetchers/coolpc.py`

```python
class CoolpcFetcher(Fetcher):
    URL = "https://www.coolpc.com.tw/evaluate.php"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9",
    }

    def fetch(self) -> list[RawProduct]:
        time.sleep(random.uniform(1.0, 3.0))
        resp = self._get_with_retry(self.URL)      # retry × 3, backoff 0.5→1→2s
        html = resp.text                            # 注意編碼，實作時確認 Big5 or UTF-8
        soup = BeautifulSoup(html, "lxml")
        products = []
        for select in soup.select("select[name^='Y']"):
            optgroup_label = None
            for el in select.descendants:
                if el.name == "optgroup":
                    optgroup_label = el.get("label")
                elif el.name == "option":
                    value = el.get("value", "")
                    text = el.get_text(strip=True)
                    price = self._parse_price(text)
                    products.append(RawProduct(
                        option_value=value,
                        option_text=text,
                        price=price,
                        optgroup=optgroup_label,
                    ))
        if len(products) < 200:
            raise FetcherError(f"Only {len(products)} options — HTML structure changed?")
        return products

    @staticmethod
    def _parse_price(text: str) -> int | None:
        m = re.search(r"\$\s*([\d,]+)", text)
        return int(m.group(1).replace(",", "")) if m else None
```

**故障邏輯**：
- HTTP 錯誤 → retry × 3，仍失敗 raise `FetcherError`
- `<option>` 總數 < 200 → raise（coolpc 正常 1000+ options）
- 編碼失敗 → raise
- 個別 option 解析失敗 → `price=None`，不 raise

### 6.2 `matcher.py`（A+C 混合）

```python
def match(rules: list[TrackingRule], raw: list[RawProduct]) -> list[MatchResult]:
    return [_match_one(rule, raw) for rule in rules]

def _match_one(rule: TrackingRule, raw: list[RawProduct]) -> MatchResult:
    # C 模式：option_value_hint 優先
    if rule.option_value_hint:
        for r in raw:
            if r.option_value == rule.option_value_hint and r.price is not None:
                return MatchResult(rule=rule, raw=r, mode="option_value", confidence=1.0)
        # hint 失效 → 降級到 A（renderer 會 warn）

    # A 模式：match_all 全含 + exclude 全不含
    candidates = [
        r for r in raw
        if all(kw in r.option_text for kw in rule.match_all)
        and not any(kw in r.option_text for kw in rule.exclude)
        and r.price is not None
    ]

    if not candidates:
        return MatchResult(rule=rule, raw=None, mode="not_found", confidence=0.0)

    if len(candidates) == 1:
        return MatchResult(rule=rule, raw=candidates[0], mode="keyword", confidence=1.0)

    # 多重命中 → 挑最短（基本款），但 confidence 下降
    best = min(candidates, key=lambda r: len(r.option_text))
    return MatchResult(
        rule=rule, raw=best, mode="keyword",
        confidence=1.0 / len(candidates),
    )
```

### 6.3 實作前必做：探 HTML

在寫 `coolpc.py` 之前（類比 house-watcher 的「先驗證 591 API」），必須手動探一次：

1. `curl https://www.coolpc.com.tw/evaluate.php > tests/fixtures/evaluate_sample.html`
2. `scripts/probe.py` 或 `notebook/explore.ipynb`：
   - 確認編碼（Big5 或 UTF-8）
   - 數 `<option>` 總數、`<select>` 總數
   - 檢查 `<optgroup label="...">` 是否存在、有無品項分類
   - **關鍵：連抓 3 次比對 `<option value="...">` 是否穩定**（穩定 → 升級 C 模式）
   - 驗證 8 個品項各自能被 YAML 的 `match_all` 唯一命中，必要時微調關鍵字
3. 結論寫進 `docs/coolpc-html-notes.md`
4. 若 option_value 穩定：把每個 rule 的 `option_value_hint` 填進 YAML
   若不穩定：YAML 不填 hint，純靠 `match_all`

## 7. Email 模板

### 7.1 主旨

`[原價屋] 2026-04-21 今日 $56,820（vs 購買 -$99）`

### 7.2 HTML 結構（`templates/email.html.j2`）

主要區塊：
- **頂部 Banner**：大字「今日總價」、vs 購買日、vs 昨天；背景色依 baseline 差額變（綠=便宜、紅=貴、灰=持平）
- **警告區塊**（有 `not_found` 或 `confidence < 1.0` 時才顯示）：黃色 alert box 列出需注意項目
- **逐項表格**：6 欄（品項 / 今日 / Δ 昨 / 7d low / 30d low / Δ 購買）；`not_found` 的列顯示 `⚠️ 今日未找到`
- **合計列**：今日總價、Δ 昨、Δ 購買
- **Footer**：baseline 日期、run_id、option_count、耗時、原價屋連結

模板草稿：

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, 'PingFang TC', sans-serif; max-width: 680px; margin: 0 auto;">

  <!-- 頂部大標 -->
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

  <!-- 警告區塊 -->
  {% if warnings %}
  <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 16px 0;">
    <strong>⚠️ 需注意：</strong>
    <ul style="margin: 4px 0;">
      {% for w in warnings %}<li>{{ w }}</li>{% endfor %}
    </ul>
  </div>
  {% endif %}

  <!-- 逐項表格 -->
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
          <td style="text-align: right;">${{ item.low_7d | comma }}</td>
          <td style="text-align: right;">${{ item.low_30d | comma }}</td>
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

  <!-- Footer -->
  <div style="margin-top: 24px; font-size: 11px; color: #888;">
    baseline: 2026-02-24 現金優惠價 $56,919
    · run: {{ run_id }} · fetched {{ option_count }} options · took {{ elapsed_ms }}ms<br>
    <a href="https://www.coolpc.com.tw/evaluate.php">原價屋配單</a>
  </div>
</body>
</html>
```

### 7.3 顏色規則

使用者是**買方視角**，降價永遠綠、漲價永遠紅（vs 昨 / vs 購買日都一致）。

| 情境 | 文字色 | banner 背景 |
|------|--------|-------------|
| 今日 < baseline（便宜了） | `#2d7a2d` 綠 | `#e8f5e8` 淡綠 |
| 今日 > baseline（買貴了） | `#c92a2a` 紅 | `#fde4e4` 淡紅 |
| 持平 | `#666` 灰 | `#f5f5f5` 淡灰 |

### 7.4 Icons

- `🔻` 近 7 天最低
- `⭐` 近 30 天最低
- `⚠️` 找不到 / confidence < 1.0

### 7.5 Jinja2 filters

```python
comma(n)                 → "6,490"
signed_comma(n)          → "-99" / "+201"
signed_comma_or_dash(n)  → "-99" / "—"（n 為 None 時）
```

## 8. 錯誤處理 & 部署

### 8.1 錯誤分級

| 情境 | 偵測 | 動作 |
|------|------|------|
| HTTP 失敗 | `httpx.HTTPError` / 4xx / 5xx | retry × 3 (0.5→1→2s)，仍失敗 → raise `FetcherError` |
| HTML 結構變了 | `<option>` 總數 < 200 | raise `FetcherError` |
| 編碼解碼失敗 | `UnicodeDecodeError` | raise `FetcherError` |
| `FetcherError`（任一） | main.py catch | 寄 alert email，`runs.status='failed'`，exit 1 |
| 單一品項 not_found | matcher 回 `not_found` | 不 raise，`price=NULL` 存進 DB，email 警告區塊列出 |
| match confidence < 1.0 | matcher 多重命中 | 存 `keyword` + confidence，email 該列顯示「N 個候選」 |
| `option_value_hint` 失效 | hint 填但抓不到 | 降級 keyword，email warn「hint 失效，請檢查 YAML」 |
| SMTP 寄信失敗 | `smtplib.SMTPException` | retry × 2，仍失敗 → print 到 stdout（GHA log），exit 1 |
| SQLite 寫入失敗 | `sqlite3.Error` | exit 1；下次跑時 runs 少一筆但不影響歷史 |

**Alert vs 日報**用不同模板：`alert.html.j2` 簡短（錯誤類型、時間、run_id、建議動作）。

### 8.2 GitHub Actions（`.github/workflows/daily.yml`）

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
  contents: write                  # commit DB 需要

jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    concurrency:
      group: daily-check
      cancel-in-progress: false    # 不互相取消，避免資料遺失
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

### 8.3 Secrets

GitHub Repository Secrets：
- `SMTP_USER` — Gmail 帳號
- `SMTP_PASS` — Gmail 應用程式密碼（**不是**登入密碼）
- `TO_EMAIL` — 收件人

本地 `.env` 同樣這 3 個變數，`.env.example` 提供模板，`.env` 進 `.gitignore`。

### 8.4 資料遺失防護

- Branch protection rule：禁止對 main 做 force push
- 月度 tag backup（workflow 最後一步）：每月第一次成功 run 打 `snapshot-YYYY-MM` tag，tag 不會被 force push 刪

## 9. 測試策略

### 9.1 測試類型

| 類型 | 範圍 | 工具 |
|------|------|------|
| Fetcher 單元測試 | 用 fixture HTML 驗證 parser：option 數、價格、optgroup | `pytest` + fixture 檔 |
| Matcher 單元測試 | given rules + RawProduct[]，驗證命中行為 | `pytest` |
| Diff 單元測試 | in-memory SQLite 塞 7 天測資，驗證 low_7d / low_30d / delta 正確 | `pytest` |
| Renderer 快照測試 | 固定 DailyReport → HTML 與 snapshot 比對 | `pytest`（或 `syrupy`） |
| End-to-end（手動） | `python -m src.main --dry-run` 打真實 coolpc，肉眼檢查 8 項皆中 | 手動 |

### 9.2 必過案例（寫在 `test_matcher.py`）

```python
def test_ssd_quantity_2_produces_correct_line_total():
    # SSD 2 顆 × 9500 = 19000
    ...

def test_case_white_not_matched_by_black():
    # "視博通 SW300 黑" 存在，exclude:["黑"] 要排掉
    ...

def test_os_professional_version_excluded():
    # "Windows 11 專業版彩盒版 64位元" 存在，exclude:["專業版"] 排掉
    ...

def test_not_found_returns_null_price_not_raise():
    ...

def test_matcher_picks_shortest_when_multiple():
    ...
```

## 10. 實作順序

照 house-watcher 節奏，每步一個 commit 方便 code review：

1. **專案骨架 + uv 環境**
   - `pyproject.toml`, `.gitignore`, `.env.example`, `CLAUDE.md`, `README.md`
   - `uv sync`：httpx / pydantic / beautifulsoup4 / lxml / Jinja2 / pytest / ruff
   - `git init`（目前尚未是 git repo）並 commit spec 文件

2. **手動探 coolpc HTML**
   - 抓 HTML 存 `tests/fixtures/evaluate_sample.html`
   - `scripts/probe.py`：確認編碼、option 總數、optgroup、option_value 穩定性
   - 驗證 YAML `match_all` 能唯一命中 8 項，必要時微調
   - 結論寫 `docs/coolpc-html-notes.md`

3. `models.py` + `config.py`（+ `test_config.py`）

4. `fetchers/coolpc.py`（+ `test_coolpc_fetcher.py`）

5. `matcher.py`（+ `test_matcher.py` 含 5 個必過案例）

6. `storage.py`（schema migration、CRUD；+ `test_storage.py` in-memory）

7. `diff.py`（純函數；+ `test_diff.py` 塞 7 天測資）

8. `renderer.py` + `templates/email.html.j2`（+ `test_renderer.py` 快照）

9. `notifier.py` + `templates/alert.html.j2`（本地實際寄信驗證）

10. `main.py`（串全流程；`--dry-run` / `--force-email`）

11. GitHub Actions workflow（先 `workflow_dispatch` dry_run，設 secrets，開 cron）

12. README + CLAUDE.md 更新（風格對齊 house-watcher；含「如何新增品項」「如何換 baseline」「`option_value_hint` 維護」）

## 11. 驗收標準

- `python -m src.main --dry-run` 印出：
  `fetched 1234 options → matched 8/8 items → today total $56,820 (vs baseline -$99) → would send email`
- 當天跑兩次，第二次 email 的「Δ 昨」欄會反映跟第一次的差（不是 0）
- 故意把 `cpu` 的 `match_all` 改壞 → dry-run 顯示 `CPU not_found`，HTML 頂部有警告區塊
- GitHub Actions 第一次 real run 後，信箱收到一封 HTML email，表格在手機正常顯示
- SQLite DB 被自動 commit 回 branch

## 12. 未來工作（v2）

**2026-05-21 提醒節點**（使用者要求提醒）：
- 累積至少 1 個月資料後，做 **GitHub Pages 趨勢圖視覺化**：
  - 每日 workflow 額外產生 static HTML（含 Chart.js 或 plotly）部署到 `gh-pages` branch
  - Email 附連結到趨勢圖頁面
  - 8 個品項各一條 sparkline，總價一條主圖，baseline 畫水平參考線
- 將由 `schedule` skill 建遠端 trigger 提醒。

**其他 v2 候選（不排期）**：
- **同類比價模式**（Q1 B 模式）：加第二條路徑，每天額外列出「同規格更便宜的替代品」（例：R7 7700 系列其他款）
- **多站比價**：透過 pluggable fetcher 加樂屋、欣亞等
- **Threshold 過濾**：若使用者覺得每天都收信太吵，加 `--only-if-changed` flag
