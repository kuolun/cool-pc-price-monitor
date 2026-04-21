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
    rule = _rule("cpu", ["AMD", "R7 7700"], hint="STABLE123")
    raw = [
        _raw("STABLE123", "AMD R7 7700 搭板 $6490", 6490),
        _raw("OTHER", "AMD R7 7700 $6490", 6490),
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
        _raw("140", "Montech CENTURY II 850W $2990", 2990),
        _raw("999", "視博通 SW300 白 機殼 $1990", 1990),
    ]
    results = match([rule], raw)
    assert results[0].mode == "keyword"
    assert results[0].raw.option_value == "999"


def test_skips_options_with_null_price():
    rule = _rule("cpu", ["AMD", "R7 7700"])
    raw = [
        _raw("1", "AMD R7 7700 (沒報價)", None),
        _raw("2", "AMD R7 7700 $6490", 6490),
    ]
    results = match([rule], raw)
    assert results[0].raw.option_value == "2"
