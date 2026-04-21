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
