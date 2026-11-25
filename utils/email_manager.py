"""
utils/email_manager.py

Autonomous Email Dispatcher, Inbox Inspector & Web Account Manager for Nova AI.
Features:
- Zero-config auto-detection for Gmail, Outlook, Yahoo, iCloud, Zoho, and custom domains.
- Dual verification for SMTP and IMAP connections.
- 2FA / OTP Verification code extraction from inbox for web account logins.
- Connected web account scanner to detect services registered to this email.
- Email searching and autonomous dispatching.
"""

from __future__ import annotations

import email
from email.header import decode_header
import imaplib
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

# Known Provider Server Configurations
_KNOWN_PROVIDERS: dict[str, dict[str, Any]] = {
    "gmail.com": {
        "name": "Google Gmail / Workspace",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
    },
    "googlemail.com": {
        "name": "Google Gmail",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
    },
    "outlook.com": {
        "name": "Microsoft Outlook",
        "smtp_host": "smtp-mail.outlook.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
    },
    "hotmail.com": {
        "name": "Microsoft Hotmail",
        "smtp_host": "smtp-mail.outlook.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
    },
    "live.com": {
        "name": "Microsoft Live",
        "smtp_host": "smtp-mail.outlook.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
    },
    "msn.com": {
        "name": "Microsoft MSN",
        "smtp_host": "smtp-mail.outlook.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
    },
    "office365.com": {
        "name": "Microsoft 365",
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
    },
    "yahoo.com": {
        "name": "Yahoo Mail",
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
    },
    "ymail.com": {
        "name": "Yahoo Mail",
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
    },
    "icloud.com": {
        "name": "Apple iCloud",
        "smtp_host": "smtp.mail.me.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "imap.mail.me.com",
        "imap_port": 993,
    },
    "me.com": {
        "name": "Apple iCloud",
        "smtp_host": "smtp.mail.me.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "imap.mail.me.com",
        "imap_port": 993,
    },
    "zoho.com": {
        "name": "Zoho Mail",
        "smtp_host": "smtppro.zoho.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": "imappro.zoho.com",
        "imap_port": 993,
    },
}

# Major Online Web Services for Account Detection
_WEB_SERVICE_PATTERNS: list[dict[str, Any]] = [
    {"name": "Google / YouTube", "category": "Tech & Search", "pattern": r"(google|youtube|accounts\.google)"},
    {"name": "Microsoft / Windows", "category": "Operating System & Cloud", "pattern": r"(microsoft|live|xbox|azure)"},
    {"name": "GitHub", "category": "Development", "pattern": r"github"},
    {"name": "OpenAI / ChatGPT", "category": "Artificial Intelligence", "pattern": r"(openai|chatgpt)"},
    {"name": "Anthropic / Claude", "category": "Artificial Intelligence", "pattern": r"(anthropic|claude)"},
    {"name": "Discord", "category": "Social & Gaming", "pattern": r"discord"},
    {"name": "Steam", "category": "Gaming", "pattern": r"(steam|valvesoftware)"},
    {"name": "Epic Games", "category": "Gaming", "pattern": r"epicgames"},
    {"name": "Netflix", "category": "Streaming & Entertainment", "pattern": r"netflix"},
    {"name": "Spotify", "category": "Music & Audio", "pattern": r"spotify"},
    {"name": "Amazon", "category": "E-Commerce & AWS", "pattern": r"(amazon|aws)"},
    {"name": "Twitter / X", "category": "Social Media", "pattern": r"(twitter|x\.com)"},
    {"name": "LinkedIn", "category": "Professional Network", "pattern": r"linkedin"},
    {"name": "Facebook / Meta", "category": "Social Media", "pattern": r"(facebook|meta\.com|instagram)"},
    {"name": "Instagram", "category": "Social Media", "pattern": r"instagram"},
    {"name": "Reddit", "category": "Social Community", "pattern": r"reddit"},
    {"name": "PayPal", "category": "Finance & Payments", "pattern": r"paypal"},
    {"name": "Stripe", "category": "Finance & Payments", "pattern": r"stripe"},
    {"name": "Binance", "category": "Crypto & Trading", "pattern": r"binance"},
    {"name": "Adobe", "category": "Creative & Design", "pattern": r"adobe"},
    {"name": "Canva", "category": "Design & Publishing", "pattern": r"canva"},
    {"name": "Figma", "category": "Design & UI/UX", "pattern": r"figma"},
    {"name": "Dropbox", "category": "Cloud Storage", "pattern": r"dropbox"},
    {"name": "Notion", "category": "Productivity", "pattern": r"notion"},
    {"name": "Slack", "category": "Workplace Communication", "pattern": r"slack"},
    {"name": "Zoom", "category": "Video Conferencing", "pattern": r"zoom"},
    {"name": "Twitch", "category": "Live Streaming", "pattern": r"twitch"},
    {"name": "Apple", "category": "Tech & Ecosystem", "pattern": r"(apple|itunes|icloud)"},
]


def auto_detect_servers(email_address: str) -> dict[str, Any]:
    """Auto-detects SMTP and IMAP host/port based on email domain."""
    email_clean = (email_address or "").strip().lower()
    domain = email_clean.split("@")[-1] if "@" in email_clean else "gmail.com"

    if domain in _KNOWN_PROVIDERS:
        cfg = dict(_KNOWN_PROVIDERS[domain])
        cfg["domain"] = domain
        return cfg

    # Fallback to standard conventions for custom/business domains
    return {
        "name": f"Custom Domain ({domain})",
        "domain": domain,
        "smtp_host": f"smtp.{domain}",
        "smtp_port": 587,
        "smtp_ssl": False,
        "imap_host": f"imap.{domain}",
        "imap_port": 993,
    }


def _decode_mime_header(header_value: str | None) -> str:
    """Safely decodes RFC 2047 MIME headers into readable string."""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result = []
        for text, encoding in decoded_parts:
            if isinstance(text, bytes):
                encoding = encoding or "utf-8"
                try:
                    result.append(text.decode(encoding, errors="replace"))
                except Exception:
                    result.append(text.decode("latin1", errors="replace"))
            else:
                result.append(str(text))
        return " ".join(result)
    except Exception:
        return str(header_value)


def verify_email_credentials(email_address: str, app_password: str) -> tuple[bool, str, dict[str, Any]]:
    """
    Connects to both IMAP and SMTP servers using auto-detected settings.
    Returns (success, message, detected_config).
    """
    user = (email_address or "").strip()
    pwd = (app_password or "").strip()

    if not user or not pwd:
        return False, "Please enter both Email Address and App Password.", {}

    servers = auto_detect_servers(user)
    diagnostics = []

    # 1. Test IMAP (Inbox Reading & OTP Extraction)
    imap_ok = False
    try:
        mail = imaplib.IMAP4_SSL(servers["imap_host"], servers["imap_port"], timeout=8)
        mail.login(user, pwd)
        mail.select("INBOX", readonly=True)
        mail.logout()
        imap_ok = True
        diagnostics.append(f"IMAP Connected ({servers['imap_host']}:993)")
    except Exception as exc:
        diagnostics.append(f"IMAP Error: {exc}")

    # 2. Test SMTP (Email Dispatching)
    smtp_ok = False
    try:
        smtp = smtplib.SMTP(servers["smtp_host"], servers["smtp_port"], timeout=8)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(user, pwd)
        smtp.quit()
        smtp_ok = True
        diagnostics.append(f"SMTP Connected ({servers['smtp_host']}:587)")
    except Exception as exc:
        diagnostics.append(f"SMTP Error: {exc}")

    if imap_ok and smtp_ok:
        msg = f"Full Connection Verified! Active on {servers['name']}.\nInbox reading (IMAP) and dispatching (SMTP) are fully functional."
        return True, msg, servers
    elif imap_ok:
        msg = f"Inbox reading (IMAP) verified for {user}. SMTP send had an error: {diagnostics[1]}"
        return True, msg, servers
    elif smtp_ok:
        msg = f"Email sending (SMTP) verified for {user}. IMAP reading had an error: {diagnostics[0]}"
        return True, msg, servers
    else:
        msg = f"Authentication Failed:\n" + "\n".join(diagnostics)
        return False, msg, servers


def send_email(
    to_email: str,
    subject: str,
    body: str,
    sender_email: str,
    app_password: str,
    smtp_host: str = "",
    smtp_port: int = 587
) -> tuple[bool, str]:
    """Sends an email via SMTP with TLS encryption."""
    if not sender_email or not app_password:
        return False, "Email sender credentials not configured. Please open Connections -> Email Settings."

    servers = auto_detect_servers(sender_email)
    host = smtp_host or servers["smtp_host"]
    port = smtp_port or servers["smtp_port"]

    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email.strip()
        msg["To"] = to_email.strip()
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP(host, port, timeout=12)
        server.ehlo()
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
    imap_host: str = "",
    limit: int = 5
) -> tuple[bool, str]:
    """Connects to IMAP server and fetches recent inbox messages."""
    if not user_email or not app_password:
        return False, "Email credentials not configured. Please open Connections -> Email Settings."

    servers = auto_detect_servers(user_email)
    host = imap_host or servers["imap_host"]

    try:
        mail = imaplib.IMAP4_SSL(host, timeout=12)
        mail.login(user_email.strip(), app_password.strip())
        mail.select("INBOX", readonly=True)

        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            mail.logout()
            return True, "Inbox is currently empty."

        msg_ids = messages[0].split()
        recent_ids = msg_ids[-limit:]

        lines = [f"**Recent Inbox Emails for {user_email}:**\n"]
        for mid in reversed(recent_ids):
            res, data = mail.fetch(mid, "(RFC822)")
            if res != "OK":
                continue
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_mime_header(msg.get("Subject", "(No Subject)"))
            from_hdr = _decode_mime_header(msg.get("From", "(Unknown Sender)"))
            date_hdr = msg.get("Date", "")

            lines.append(f"• **From:** {from_hdr}")
            lines.append(f"  **Subject:** {subject}")
            lines.append(f"  **Date:** {date_hdr}\n")

        mail.logout()
        return True, "\n".join(lines)
    except Exception as exc:
        log.exception("Failed to fetch emails: {}", exc)
        return False, f"Failed to connect to email inbox: {exc}"


def get_latest_otp(
    user_email: str,
    app_password: str,
    service_name: str = "",
    scan_limit: int = 25
) -> tuple[bool, str, dict[str, Any]]:
    """
    Scans the user's recent inbox emails to extract 2FA / OTP verification codes
    or security PINs sent by web services (Google, GitHub, Discord, Steam, etc.).
    """
    if not user_email or not app_password:
        return False, "Email credentials not configured. Please open Connections -> Email Settings.", {}

    servers = auto_detect_servers(user_email)
    host = servers["imap_host"]

    try:
        mail = imaplib.IMAP4_SSL(host, timeout=12)
        mail.login(user_email.strip(), app_password.strip())
        mail.select("INBOX", readonly=True)

        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            mail.logout()
            return False, "Inbox is currently empty.", {}

        msg_ids = messages[0].split()
        recent_ids = msg_ids[-scan_limit:]

        otp_found = None
        service_target = (service_name or "").strip().lower()

        # Regex patterns for OTP / Verification codes
        code_patterns = [
            r"(?:code|pin|otp|passcode|verification\s+code|security\s+code)[^0-9\n]{1,30}([0-9]{4,8})\b",
            r"\b([0-9]{4,8})\b(?=[^0-9\n]{0,30}(?:is your|code|verification))",
            r"(?:enter|use)\s+([0-9]{4,8})\s+to\s+verify",
        ]

        for mid in reversed(recent_ids):
            res, data = mail.fetch(mid, "(RFC822)")
            if res != "OK":
                continue
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_mime_header(msg.get("Subject", ""))
            from_hdr = _decode_mime_header(msg.get("From", ""))
            date_hdr = msg.get("Date", "")

            # Filter by service name if requested
            if service_target and (service_target not in subject.lower() and service_target not in from_hdr.lower()):
                continue

            # Check if this email looks like a verification email
            indicator_words = ["verification", "code", "security", "verify", "otp", "login", "authenticate", "confirm"]
            if not any(w in subject.lower() for w in indicator_words) and not any(w in from_hdr.lower() for w in indicator_words):
                continue

            # Extract body
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type in ("text/plain", "text/html"):
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                body_text += payload.decode("utf-8", errors="replace") + "\n"
                        except Exception:
                            pass
            else:
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode("utf-8", errors="replace")
                except Exception:
                    body_text = str(msg.get_payload())

            # Search for code in subject first, then body
            extracted_code = ""
            for pat in code_patterns:
                m_sub = re.search(pat, subject, re.IGNORECASE)
                if m_sub:
                    extracted_code = m_sub.group(1)
                    break
                m_body = re.search(pat, body_text, re.IGNORECASE)
                if m_body:
                    extracted_code = m_body.group(1)
                    break

            if extracted_code:
                # Clean up extracted code
                otp_found = {
                    "code": extracted_code,
                    "service": from_hdr,
                    "subject": subject,
                    "date": date_hdr,
                    "preview": body_text[:200].strip(),
                }
                break

        mail.logout()

        if otp_found:
            msg_str = (
                f"**Verification Code Found:** `{otp_found['code']}`\n"
                f"• **From:** {otp_found['service']}\n"
                f"• **Subject:** {otp_found['subject']}\n"
                f"• **Date:** {otp_found['date']}"
            )
            return True, msg_str, otp_found
        else:
            filter_note = f" for '{service_name}'" if service_name else ""
            return False, f"No recent OTP or verification code found in inbox{filter_note}.", {}

    except Exception as exc:
        log.exception("Error checking OTP: {}", exc)
        return False, f"Error scanning inbox for OTP: {exc}", {}


def scan_connected_web_accounts(
    user_email: str,
    app_password: str,
    scan_limit: int = 100
) -> tuple[bool, list[dict[str, Any]], str]:
    """
    Scans the email inbox to identify online web accounts and platforms registered
    to this email address (GitHub, Steam, Discord, Google, Netflix, Amazon, etc.).
    """
    if not user_email or not app_password:
        return False, [], "Email credentials not configured. Please open Connections -> Email Settings."

    servers = auto_detect_servers(user_email)
    host = servers["imap_host"]

    try:
        mail = imaplib.IMAP4_SSL(host, timeout=15)
        mail.login(user_email.strip(), app_password.strip())
        mail.select("INBOX", readonly=True)

        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            mail.logout()
            return True, [], "Inbox is empty. No web accounts detected."

        msg_ids = messages[0].split()
        scan_ids = msg_ids[-scan_limit:]

        detected_services: dict[str, dict[str, Any]] = {}

        for mid in reversed(scan_ids):
            res, data = mail.fetch(mid, "(RFC822)")
            if res != "OK":
                continue
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            from_hdr = _decode_mime_header(msg.get("From", ""))
            subject = _decode_mime_header(msg.get("Subject", ""))
            date_hdr = msg.get("Date", "")
            combined_header = f"{from_hdr} {subject}".lower()

            for spec in _WEB_SERVICE_PATTERNS:
                s_name = spec["name"]
                if s_name in detected_services:
                    continue  # already recorded latest activity
                if re.search(spec["pattern"], combined_header):
                    detected_services[s_name] = {
                        "name": s_name,
                        "category": spec["category"],
                        "sender": from_hdr,
                        "latest_subject": subject,
                        "latest_date": date_hdr,
                        "status": "Active / Verified",
                    }

        mail.logout()
        accounts_list = list(detected_services.values())

        summary = f"Discovered **{len(accounts_list)}** connected online web accounts on `{user_email}`."
        return True, accounts_list, summary

    except Exception as exc:
        log.exception("Error scanning web accounts: {}", exc)
        return False, [], f"Failed to scan web accounts from inbox: {exc}"


def search_service_emails(
    user_email: str,
    app_password: str,
    query: str,
    limit: int = 5
) -> tuple[bool, str]:
    """Searches emails for a specific service or keyword."""
    if not user_email or not app_password:
        return False, "Email credentials not configured."

    servers = auto_detect_servers(user_email)
    host = servers["imap_host"]

    try:
        mail = imaplib.IMAP4_SSL(host, timeout=12)
        mail.login(user_email.strip(), app_password.strip())
        mail.select("INBOX", readonly=True)

        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            mail.logout()
            return True, "Inbox is currently empty."

        msg_ids = messages[0].split()
        recent_ids = msg_ids[-50:]

        q_lower = query.lower().strip()
        matches = []

        for mid in reversed(recent_ids):
            res, data = mail.fetch(mid, "(RFC822)")
            if res != "OK":
                continue
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            from_hdr = _decode_mime_header(msg.get("From", ""))
            subject = _decode_mime_header(msg.get("Subject", ""))
            date_hdr = msg.get("Date", "")

            if q_lower in subject.lower() or q_lower in from_hdr.lower():
                matches.append(f"• **From:** {from_hdr}\n  **Subject:** {subject}\n  **Date:** {date_hdr}")
                if len(matches) >= limit:
                    break

        mail.logout()

        if matches:
            res_str = f"**Emails matching '{query}' for {user_email}:**\n\n" + "\n\n".join(matches)
            return True, res_str
        else:
            return True, f"No recent emails found matching '{query}'."
    except Exception as exc:
        log.exception("Error searching emails: {}", exc)
        return False, f"Failed to search emails: {exc}"
