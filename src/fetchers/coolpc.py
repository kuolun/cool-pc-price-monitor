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
                    self.URL,
                    headers=self.HEADERS,
                    timeout=30.0,
                    follow_redirects=True,
                )
                resp.raise_for_status()
                return resp.content
            except (httpx.HTTPError, httpx.HTTPStatusError) as e:
                last_err = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.BACKOFF_BASE * (2**attempt))
        raise FetcherError(f"HTTP failed after {self.MAX_RETRIES} attempts: {last_err}")

    @classmethod
    def parse(cls, html_bytes: bytes) -> list[RawProduct]:
        # Probe found coolpc declares charset=Big5 but actually needs big5hkscs codec
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
        # Probe found: actual select names are n1..n30, not Y*
        for select in soup.select("select[name^='n']"):
            optgroup_label: str | None = None
            for el in select.descendants:
                if el.name == "optgroup":
                    optgroup_label = el.get("label")
                elif el.name == "option":
                    value = el.get("value", "") or ""
                    text = el.get_text(strip=True)
                    price = cls._parse_price(text)
                    products.append(
                        RawProduct(
                            option_value=value,
                            option_text=text,
                            price=price,
                            optgroup=optgroup_label,
                        )
                    )

        if len(products) < _MIN_OPTIONS:
            raise FetcherError(
                f"Only {len(products)} options — HTML structure may have changed"
            )
        return products

    @staticmethod
    def _parse_price(text: str) -> int | None:
        # coolpc 常見格式：「$17999↗$25400」表示已從 $17999 漲到目前結帳價 $25400
        # （↗ 漲價、↘ 降價）。目前結帳價永遠是最後一個 $amount，所以取最後一筆。
        matches = _PRICE_RE.findall(text)
        if not matches:
            return None
        return int(matches[-1].replace(",", ""))
