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
    assert len(with_price) >= 200
    for p in with_price:
        assert p.price > 0


def test_parse_extracts_amd_r7_7700_mpk():
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
    tiny_html = (
        b"<html><body><select name='n1'>"
        b"<option value='1'>$100</option>"
        b"</select></body></html>"
    )
    with pytest.raises(FetcherError, match="Only"):
        CoolpcFetcher.parse(tiny_html)


def test_parse_price_handles_comma_and_space():
    assert CoolpcFetcher._parse_price("foo $6,490 bar") == 6490
    assert CoolpcFetcher._parse_price("foo $ 6490 bar") == 6490
    assert CoolpcFetcher._parse_price("no price here") is None


def test_fetch_retries_on_transient_error(mocker):
    fixture_bytes = FIXTURE.read_bytes()

    transient = httpx.ConnectError("transient")
    ok_resp = MagicMock()
    ok_resp.content = fixture_bytes
    ok_resp.text = fixture_bytes.decode("big5hkscs", errors="replace")
    ok_resp.raise_for_status = lambda: None

    get_mock = mocker.patch(
        "httpx.get",
        side_effect=[transient, transient, ok_resp],
    )
    mocker.patch("time.sleep")

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
