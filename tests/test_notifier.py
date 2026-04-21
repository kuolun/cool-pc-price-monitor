from unittest.mock import MagicMock

import pytest

from src.config import SMTPConfig
from src.notifier import send_email


@pytest.fixture
def smtp_cfg():
    return SMTPConfig(user="u@g.com", password="pw", to_email="t@g.com")


def test_send_email_calls_smtp(mocker, smtp_cfg):
    fake_smtp = MagicMock()
    mocker.patch("smtplib.SMTP", return_value=fake_smtp)

    send_email(
        cfg=smtp_cfg,
        subject="test subject",
        html_body="<p>hi</p>",
    )

    fake_smtp.__enter__.assert_called_once()
    smtp_instance = fake_smtp.__enter__.return_value
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("u@g.com", "pw")
    smtp_instance.send_message.assert_called_once()


def test_send_email_retries_on_smtp_error(mocker, smtp_cfg):
    import smtplib

    fake_smtp = MagicMock()
    call_count = [0]

    def _send_message_side(*a, **k):
        call_count[0] += 1
        if call_count[0] == 1:
            raise smtplib.SMTPException("transient")
    fake_smtp.__enter__.return_value.send_message = MagicMock(side_effect=_send_message_side)

    mocker.patch("smtplib.SMTP", return_value=fake_smtp)
    mocker.patch("time.sleep")

    send_email(cfg=smtp_cfg, subject="s", html_body="<p>x</p>")

    assert call_count[0] == 2


def test_send_email_raises_after_max_retries(mocker, smtp_cfg):
    import smtplib

    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value.send_message = MagicMock(
        side_effect=smtplib.SMTPException("down")
    )
    mocker.patch("smtplib.SMTP", return_value=fake_smtp)
    mocker.patch("time.sleep")

    with pytest.raises(smtplib.SMTPException):
        send_email(cfg=smtp_cfg, subject="s", html_body="<p>x</p>")
