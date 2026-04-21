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


def test_smtp_config_from_env(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "u@g.com")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("TO_EMAIL", "t@g.com")
    smtp = SMTPConfig.from_env()
    assert smtp.user == "u@g.com"
    assert smtp.to_email == "t@g.com"


def test_smtp_config_missing_env_raises(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("TO_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="SMTP_USER"):
        SMTPConfig.from_env()
