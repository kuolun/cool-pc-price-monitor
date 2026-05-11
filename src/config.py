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
        # Convention aligned with dotfiles/send-email skill + other personal projects
        # (fb-posts-saver, ivy-life-course-learning): GMAIL_USER + GMAIL_APP_PASSWORD.
        # TO_EMAIL optional — defaults to GMAIL_USER (send to self).
        required = {"GMAIL_USER", "GMAIL_APP_PASSWORD"}
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing env vars: {missing}")
        user = os.environ["GMAIL_USER"]
        return cls(
            user=user,
            password=os.environ["GMAIL_APP_PASSWORD"],
            to_email=os.environ.get("TO_EMAIL") or "kuolun@gmail.com",
        )


def load_products(path: Path | str) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    baseline = Baseline(**raw["baseline"])
    rules = [TrackingRule(**p) for p in raw["products"]]
    return AppConfig(baseline=baseline, rules=rules)
