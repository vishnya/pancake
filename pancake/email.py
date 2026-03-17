"""Email notification utilities for Pancake.

Sends assignment and reminder emails via SMTP.
Config via env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM.
All sends are non-blocking (fire-and-forget in a background thread).
"""

import logging
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

def _smtp_config() -> dict | None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASS", ""),
        "from_addr": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    }


def _send_email(to_email: str, subject: str, html_body: str) -> None:
    """Send an email synchronously. Called from background thread."""
    config = _smtp_config()
    if not config:
        logger.warning("SMTP not configured, skipping email to %s", to_email)
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["from_addr"]
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(config["host"], config["port"], timeout=10) as server:
            server.ehlo()
            if config["port"] != 25:
                server.starttls()
                server.ehlo()
            if config["user"] and config["password"]:
                server.login(config["user"], config["password"])
            server.sendmail(config["from_addr"], [to_email], msg.as_string())
        logger.info("Email sent to %s: %s", to_email, subject)
    except Exception:
        logger.exception("Failed to send email to %s", to_email)


def _fire_and_forget(to_email: str, subject: str, html_body: str) -> None:
    """Send email in a background thread so the API doesn't block."""
    t = threading.Thread(target=_send_email, args=(to_email, subject, html_body), daemon=True)
    t.start()


def _base_html(content: str) -> str:
    """Wrap content in Pancake-themed dark HTML email template."""
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="margin:0;padding:0;background:#1a1a2e;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#1a1a2e;padding:32px 16px;">'
        '<tr><td align="center">'
        '<table width="480" cellpadding="0" cellspacing="0" style="background:#16213e;border:1px solid #2a3a5c;border-radius:12px;padding:24px;">'
        '<tr><td>'
        '<h2 style="color:#a0b4d0;font-size:18px;margin:0 0 16px 0;">Pancake</h2>'
        + content +
        '<p style="color:#556;font-size:11px;margin-top:24px;border-top:1px solid #2a3a5c;padding-top:12px;">'
        'This is an automated notification from Pancake.</p>'
        '</td></tr></table>'
        '</td></tr></table>'
        '</body></html>'
    )


def send_assignment_email(
    to_email: str,
    task_text: str,
    project: str,
    deadline: str,
    assigned_by: str,
    app_url: str = "",
) -> None:
    """Send a task assignment notification email."""
    if not to_email:
        return
    project_html = f'<span style="color:#d4a855;">[{project}]</span> ' if project else ""
    deadline_html = f'<p style="color:#8ab4d4;font-size:13px;">Due: {deadline}</p>' if deadline else ""
    link_html = f'<p style="margin-top:16px;"><a href="{app_url}" style="color:#6a8fc5;text-decoration:none;">Open Pancake &rarr;</a></p>' if app_url else ""

    content = (
        '<p style="color:#e0e0e0;font-size:14px;margin:0 0 12px;">'
        f'<strong>{assigned_by}</strong> assigned you a task:</p>'
        '<div style="background:#1e2d4a;border-radius:8px;padding:12px 16px;margin:8px 0;">'
        f'<p style="color:#e0e0e0;font-size:15px;margin:0;">{project_html}{task_text}</p>'
        f'{deadline_html}</div>{link_html}'
    )
    subject = f"Task assigned: {task_text[:60]}"
    _fire_and_forget(to_email, subject, _base_html(content))


def send_reminder_email(
    to_email: str,
    task_text: str,
    project: str,
    deadline: str,
    reminded_by: str,
    app_url: str = "",
) -> None:
    """Send a task reminder notification email."""
    if not to_email:
        return
    project_html = f'<span style="color:#d4a855;">[{project}]</span> ' if project else ""
    deadline_html = f'<p style="color:#8ab4d4;font-size:13px;">Due: {deadline}</p>' if deadline else ""
    link_html = f'<p style="margin-top:16px;"><a href="{app_url}" style="color:#6a8fc5;text-decoration:none;">Open Pancake &rarr;</a></p>' if app_url else ""

    content = (
        '<p style="color:#e0e0e0;font-size:14px;margin:0 0 12px;">'
        f'<strong>{reminded_by}</strong> sent you a reminder:</p>'
        '<div style="background:#1e2d4a;border-radius:8px;padding:12px 16px;margin:8px 0;">'
        f'<p style="color:#e0e0e0;font-size:15px;margin:0;">{project_html}{task_text}</p>'
        f'{deadline_html}</div>{link_html}'
    )
    subject = f"Reminder: {task_text[:60]}"
    _fire_and_forget(to_email, subject, _base_html(content))
