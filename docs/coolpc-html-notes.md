# coolpc evaluate.php HTML 探勘筆記

> 日期：2026-04-21
> 對應 spec：`docs/superpowers/specs/2026-04-21-coolpc-price-monitor-design.md`

## 基本結構

- URL：<https://www.coolpc.com.tw/evaluate.php>
- 編碼：big5hkscs（HTTP 回應宣告 `charset=Big5`，但實際需用 `big5hkscs` codec 才能正確解碼）
- `<select name="n*">` 數量：30（注意：選單命名規則為 `n1`–`n30`，**不是** `Y*`）
- `<option>` 總數：7368
- `<optgroup label="...">` 數量：567
- 品質閾值：fetcher 若 option < 200 則 raise（正常 7368 遠大於 200）

## option_value 穩定性

3 次抓取間隔 5 秒，values SHA-256 前 16 位：
- run1: 9c6932bae2c7ca17
- run2: 9c6932bae2c7ca17
- run3: 9c6932bae2c7ca17

結論：**STABLE**

3 次抓取 option value 雜湊完全相同，matcher 可用 C 模式：優先以 `option_value_hint` 直接定位，再以 `match_all` 做雙重確認。Task 4 的 `config/products.yaml` 應填入下表的 `option_value_hint`。

## 8 個品項的命中結果

| key | 關鍵字 | 候選數 | option_value（若穩定）| option_text 摘要 |
|-----|--------|--------|----------------------|-----------------|
| cpu | AMD / R7 7700 MPK | 1 | 30 | AMD R7 7700 MPK(代理含風扇)【8核/16緒】3.8G(↑5.3G)65W /具內顯 /代理商三年保 |
| mb  | B650EM / FORCE / WIFI6E | 1 | 289 | 技嘉 B650EM FORCE WIFI6E(M-ATX/LAN 2.5G+無線/註冊五年)8+2+2相電源 |
| ram | UMAX / 64GB / 雙通32GB / 6000 / CL30 | 1 | 37 | UMAX 64GB(雙通32GB*2) DDR5 6000/CL30 含散熱片 |
| ssd | 金士頓 / KC3000 / 2TB | 1 | 175 | 金士頓 KC3000 2TB/Gen4 PCIe 4.0/讀7000/寫7000/TLC【五年保】 |
| cooler | 九州風神 / AG500 | 1 | 62 | 九州風神 AG500 /5導管(6mm)/高15.5cm/TDP:240W【WXZ】 |
| case | 視博通 / SW300 / 白 | 1 | 140 | 視博通 SW300 白 顯卡長34.5/CPU高16.3/前置Type-C/彈壓式防塵網/玻璃透側/E-ATX |
| psu | Montech / CENTURY II / 850W | 1 | 140 | Montech CENTURY II 850W 雙8/金牌/全模/ATX3.1(PCIe 5.1)/全日系/智慧停轉/10年 |
| os  | Windows 11 / 家用彩盒版 / 64位元 | 3 | 11（目標）| Windows 11 中文家用彩盒版 64位元 (USB)（須加 exclude 縮減至 1） |

備註 os：另外 2 筆命中為
- value=12：`Windows 11 中文家用彩盒版 64位元 (USB)【組裝價】`（較便宜的搭機價，非目標）
- value=16：`Windows 11 英文家用彩盒版 64位元【客訂】`（英文版，非目標）

## 需要在 YAML 加 exclude 的品項

**os** → `exclude: ["組裝價", "英文"]`
- 原因：`match_all: ["Windows 11", "家用彩盒版", "64位元"]` 命中 3 筆，需排除「組裝價」版（value=12）及英文版（value=16），目標為標準零售中文彩盒版（value=11，$4390）。

其餘 7 個品項各自只有 1 筆命中，無需 exclude。

## 後續 task 的 input

- Task 4 (config): `config/products.yaml` 的 8 筆 `match_all` / `exclude` / `option_value_hint` 請以此表填寫。
  - os 需加 `exclude: ["組裝價", "英文"]`；其餘品項直接帶入上表關鍵字與 option_value_hint。
  - 注意 `select` 名稱為 `n*`（不是 `Y*`），fetcher 選取器應對應調整。
- Task 6 (fetcher): 
  - 編碼處理 = `big5hkscs`（不是 `utf-8` 或 `big5`）
  - 選單選取器：`select[name^='n']`（非 `select[name^='Y']`）
  - 品質閾值：`len(options) < 200` → raise
- Task 7 (matcher): 測試 fixture 在 `tests/fixtures/evaluate_sample.html`
