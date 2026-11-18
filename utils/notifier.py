"""
utils/notifier.py

Universal Cross-Platform Notification Dispatcher for Nova AI.
Sends notifications across:
1. Desktop Windows Toast / System Tray
2. WhatsApp (via local Baileys bridge)
3. Discord (via local Discord bot)
"""

from __future__ import annotations

import json
import threading
import urllib.request
from utils.logger import get_logger

log = get_logger(__name__)


def _send_desktop_notification(title: str, message: str):
    """Triggers a native Windows Notification / Tray balloon."""
    try:
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon
        app = QApplication.instance()
        if app:
            for widget in app.allWidgets():
                if isinstance(widget, QSystemTrayIcon) or hasattr(widget, "tray"):
                    tray = getattr(widget, "tray", widget)
                    tray.showMessage(title, message, QSystemTrayIcon.Information, 4000)
                    return
    except Exception:
        pass

    # Windows PowerShell Toast fallback
    try:
        import subprocess
        ps_cmd = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Nova AI")
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($notification)
        '''
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=4)
    except Exception as exc:
        log.warning("PowerShell toast notification failed: {}", exc)


def _send_whatsapp_notification(title: str, message: str):
    """Sends notification to user's WhatsApp."""
    try:
        import os
        owner_num = os.environ.get("OWNER_NUMBERS", "").split(",")[0].strip()
        text = f"*NOVA AI NOTIFICATION*\n\n*{title}*\n{message}"
        req = urllib.request.Request(
            "http://127.0.0.1:3000/notify",
            data=json.dumps({"number": owner_num, "message": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        # Bridge may not be actively listening for /notify; silent fallback
        pass


def _send_discord_notification(title: str, message: str):
    """Sends notification to Discord bot channel/DM."""
    try:
        text = f"**Nova AI Notification**\n**{title}**\n{message}"
        req = urllib.request.Request(
            "http://127.0.0.1:5051/notify",
            data=json.dumps({"message": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


def send_universal_notification(title: str, message: str):
    """Dispatches notifications across all active platforms asynchronously."""
    def _dispatch():
        _send_desktop_notification(title, message)
        _send_whatsapp_notification(title, message)
        _send_discord_notification(title, message)

    threading.Thread(target=_dispatch, daemon=True, name="UniversalNotifier").start()
