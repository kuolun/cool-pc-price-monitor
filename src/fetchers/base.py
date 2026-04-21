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
