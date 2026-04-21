import pytest

from src.fetchers.base import Fetcher, FetcherError


def test_fetcher_is_abstract():
    with pytest.raises(TypeError):
        Fetcher()  # type: ignore[abstract]


def test_fetcher_error_is_exception():
    with pytest.raises(FetcherError, match="boom"):
        raise FetcherError("boom")
