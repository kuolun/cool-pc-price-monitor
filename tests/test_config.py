from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import SMTPConfig, load_products

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
    with pytest.raises(ValidationError):
        load_products(path)


def test_smtp_config_from_env_with_explicit_to_email(monkeypatch):
    monkeypatch.setenv("GMAIL_USER", "u@g.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pass")
    monkeypatch.setenv("TO_EMAIL", "t@g.com")
    smtp = SMTPConfig.from_env()
    assert smtp.user == "u@g.com"
    assert smtp.to_email == "t@g.com"


def test_smtp_config_to_email_defaults_to_gmail_user(monkeypatch):
    monkeypatch.setenv("GMAIL_USER", "u@g.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pass")
    monkeypatch.delenv("TO_EMAIL", raising=False)
    smtp = SMTPConfig.from_env()
    assert smtp.to_email == "u@g.com"


def test_smtp_config_missing_env_raises(monkeypatch):
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("TO_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="GMAIL_USER"):
        SMTPConfig.from_env()
