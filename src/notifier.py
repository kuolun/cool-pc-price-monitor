"""SMTP email sending with retry."""
from __future__ import annotations

import smtplib
import time
from email.message import EmailMessage

from src.config import SMTPConfig

_MAX_RETRIES = 2


def send_email(
    *, cfg: SMTPConfig, subject: str, html_body: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.user
    msg["To"] = cfg.to_email
    msg.set_content("此信為 HTML 版本，請用支援 HTML 的郵件客戶端閱讀。")
    msg.add_alternative(html_body, subtype="html")

    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(cfg.host, cfg.port) as server:
                server.starttls()
                server.login(cfg.user, cfg.password)
                server.send_message(msg)
            return
        except smtplib.SMTPException as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(1.0 * (2 ** attempt))
    assert last_err is not None
    raise last_err
