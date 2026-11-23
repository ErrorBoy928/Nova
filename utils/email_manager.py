"""
utils/email_manager.py

Autonomous Email Dispatcher & Inbox Inspector for Nova AI.
Supports standard SMTP/IMAP with TLS (Gmail, Outlook, Yahoo, Custom).
"""

from __future__ import annotations

import email
import imaplib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)


def send_email(
    to_email: str,
    subject: str,
    body: str,
    sender_email: str,
    app_password: str,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587
) -> tuple[bool, str]:
    """Sends an email via SMTP with TLS encryption."""
    if not sender_email or not app_password:
        return False, "Email sender credentials not configured. Please open Connections -> Email Settings."

    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
        server.starttls()
        server.login(sender_email.strip(), app_password.strip())
        server.send_message(msg)
        server.quit()

        log.info("Email successfully sent to {}", to_email)
        return True, f"Email successfully sent to {to_email} with subject: '{subject}'"
    except Exception as exc:
        log.exception("Failed to send email: {}", exc)
        return False, f"Failed to send email: {exc}"


def check_recent_emails(
    user_email: str,
    app_password: str,
    imap_host: str = "imap.gmail.com",
    limit: int = 5
) -> tuple[bool, str]:
    """Connects to IMAP server and fetches recent inbox messages."""
    if not user_email or not app_password:
        return False, "Email credentials not configured. Please open Connections -> Email Settings."

    try:
        mail = imaplib.IMAP4_SSL(imap_host, timeout=12)
        mail.login(user_email.strip(), app_password.strip())
        mail.select("INBOX")

        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            mail.logout()
            return True, "Inbox is currently empty."

        msg_ids = messages[0].split()
        recent_ids = msg_ids[-limit:]

        lines = [f"📧 **Recent Emails for {user_email}:**\n"]
        for mid in reversed(recent_ids):
            res, data = mail.fetch(mid, "(RFC822)")
            if res != "OK":
                continue
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = msg.get("Subject", "(No Subject)")
            from_hdr = msg.get("From", "(Unknown Sender)")
            date_hdr = msg.get("Date", "")

            lines.append(f"• **From:** {from_hdr}")
            lines.append(f"  **Subject:** {subject}")
            lines.append(f"  **Date:** {date_hdr}\n")

        mail.logout()
        return True, "\n".join(lines)
    except Exception as exc:
        log.exception("Failed to fetch emails: {}", exc)
        return False, f"Failed to connect to email inbox: {exc}"
