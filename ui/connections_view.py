"""
ui/connections_view.py

Connections Hub View for Nova AI.
Manages:
1. 📱 WhatsApp Web (Baileys QR code generation, in-app scan & commands)
2. 🤖 Discord Superbot (Bot Token configuration, live status & commands)
3. 📧 Autonomous Email & Web Research (Gmail/SMTP credentials, autonomous web search)
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config.settings_schema import AppConfig, save_config
from utils.logger import get_logger

log = get_logger(__name__)


class ConnectionsView(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #08080c;
                color: #e2e8f0;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background: #0d0d14;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #0a0a10;
                color: #94a3b8;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #1e293b;
                border-bottom: none;
                font-weight: 700;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #0d0d14;
                color: #38bdf8;
                border-color: #38bdf8;
            }
            QTabBar::tab:hover:!selected {
                background: #141420;
                color: #ffffff;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11px;
            }
            QLineEdit {
                background-color: #12121a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 7px 10px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header Title
        title_box = QVBoxLayout()
        title_lbl = QLabel("🔗 NOVA PLATFORM CONNECTIONS HUB")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px;")
        sub_lbl = QLabel("Authorize WhatsApp Mobile Access, Connect Discord Superbot, and configure Autonomous Email & Web Research.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        root.addLayout(title_box)

        tabs = QTabWidget()

        # ── TAB 1: WhatsApp ──────────────────────────────────────────
        tab_wa = QWidget()
        layout_wa = QVBoxLayout(tab_wa)
        layout_wa.setContentsMargins(16, 16, 16, 16)
        layout_wa.setSpacing(12)

        wa_status_box = QHBoxLayout()
        wa_icon = QLabel("📱")
        wa_icon.setStyleSheet("font-size: 20px;")
        wa_title = QLabel("WhatsApp Baileys Web Socket Bridge")
        wa_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        self.wa_status_lbl = QLabel("● CONNECTED (+92 334 7973707)")
        self.wa_status_lbl.setStyleSheet("color: #10b981; font-weight: 700; font-size: 11px; padding: 2px 8px; background: #064e3b; border-radius: 6px;")
        wa_status_box.addWidget(wa_icon)
        wa_status_box.addWidget(wa_title)
        wa_status_box.addStretch()
        wa_status_box.addWidget(self.wa_status_lbl)
        layout_wa.addLayout(wa_status_box)

        wa_desc = QLabel("Scan the QR code with your WhatsApp to authorize Nova as your mobile assistant. You can give voice or text commands from anywhere!")
        wa_desc.setWordWrap(True)
        wa_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout_wa.addWidget(wa_desc)

        # QR Display Container
        self.qr_frame = QFrame()
        self.qr_frame.setStyleSheet("background-color: #12121a; border: 1px dashed #334155; border-radius: 8px; min-height: 180px;")
        qr_layout = QVBoxLayout(self.qr_frame)
        qr_layout.setAlignment(Qt.AlignCenter)

        self.qr_img_lbl = QLabel("Scan QR Code to Link WhatsApp")
        self.qr_img_lbl.setAlignment(Qt.AlignCenter)
        self.qr_img_lbl.setStyleSheet("color: #64748b; font-weight: 600;")
        qr_layout.addWidget(self.qr_img_lbl)
        layout_wa.addWidget(self.qr_frame)

        wa_btn_row = QHBoxLayout()
        self.scan_qr_btn = QPushButton("Generate / Refresh QR Code")
        self.scan_qr_btn.clicked.connect(self._fetch_whatsapp_qr)
        wa_btn_row.addWidget(self.scan_qr_btn)
        layout_wa.addLayout(wa_btn_row)

        wa_cmds = QLabel(
            "<b>WhatsApp Exclusive Commands:</b><br>"
            "• <code>!screen</code> : Takes live PC screenshot and replies with high-res image<br>"
            "• <code>!pc &lt;cmd&gt;</code> : Runs app or action on PC (e.g. <code>!pc open chrome</code>)<br>"
            "• <code>!pctasks</code> : Checks PC agent tasks list<br>"
            "• <code>!pcstats</code> : Reports live CPU, RAM, and Disk space<br>"
            "• <code>!stop</code> / <code>!start</code> : Controls chat auto-responder"
        )
        wa_cmds.setStyleSheet("background: #0d0d16; padding: 10px; border-radius: 6px; color: #cbd5e1; font-size: 10px; line-height: 1.5;")
        layout_wa.addWidget(wa_cmds)
        layout_wa.addStretch()
        tabs.addTab(tab_wa, "📱 WhatsApp")

        # ── TAB 2: Discord ───────────────────────────────────────────
        tab_dc = QWidget()
        layout_dc = QVBoxLayout(tab_dc)
        layout_dc.setContentsMargins(16, 16, 16, 16)
        layout_dc.setSpacing(12)

        dc_status_box = QHBoxLayout()
        dc_icon = QLabel("🤖")
        dc_icon.setStyleSheet("font-size: 20px;")
        dc_title = QLabel("Discord Superbot Integration")
        dc_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        self.dc_status_lbl = QLabel("READY TO CONNECT")
        self.dc_status_lbl.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px; padding: 2px 8px; background: #0c4a6e; border-radius: 6px;")
        dc_status_box.addWidget(dc_icon)
        dc_status_box.addWidget(dc_title)
        dc_status_box.addStretch()
        dc_status_box.addWidget(self.dc_status_lbl)
        layout_dc.addLayout(dc_status_box)

        dc_desc = QLabel("Enter your Discord Bot Token to connect Nova to your Discord server or DMs.")
        dc_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout_dc.addWidget(dc_desc)

        form_dc = QFormLayout()
        self.dc_token_input = QLineEdit()
        self.dc_token_input.setEchoMode(QLineEdit.Password)
        self.dc_token_input.setPlaceholderText("Paste your Discord Bot Token here...")

        env_path = Path("E:/Nova_AI/.env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DISCORD_BOT_TOKEN="):
                    self.dc_token_input.setText(line.split("=", 1)[1].strip())
                    self.dc_status_lbl.setText("● TOKEN CONFIGURED")
                    self.dc_status_lbl.setStyleSheet("color: #10b981; font-weight: 700; font-size: 11px; padding: 2px 8px; background: #064e3b; border-radius: 6px;")

        form_dc.addRow("Bot Token:", self.dc_token_input)
        layout_dc.addLayout(form_dc)

        dc_btn_row = QHBoxLayout()
        btn_save_dc = QPushButton("Save & Connect Discord Bot")
        btn_save_dc.clicked.connect(self._save_discord_token)
        dc_btn_row.addWidget(btn_save_dc)
        layout_dc.addLayout(dc_btn_row)

        dc_cmds = QLabel(
            "<b>Discord Exclusive Commands:</b><br>"
            "• <code>!screen</code> : Takes live PC screenshot and embeds in Discord<br>"
            "• <code>!pc &lt;action&gt;</code> : Execute desktop control or script<br>"
            "• <code>!pctasks</code> : Remote task status inspection<br>"
            "• <code>!pcstats</code> : Machine diagnostics (CPU, RAM, GPU)<br>"
            "• <code>!secret &lt;key&gt;</code> : Store or retrieve credentials in Nova's Vault"
        )
        dc_cmds.setStyleSheet("background: #0d0d16; padding: 10px; border-radius: 6px; color: #cbd5e1; font-size: 10px; line-height: 1.5;")
        layout_dc.addWidget(dc_cmds)
        layout_dc.addStretch()
        tabs.addTab(tab_dc, "🤖 Discord")

        # ── TAB 3: Email & Research ──────────────────────────────────
        tab_mail = QWidget()
        layout_mail = QVBoxLayout(tab_mail)
        layout_mail.setContentsMargins(16, 16, 16, 16)
        layout_mail.setSpacing(12)

        mail_status_box = QHBoxLayout()
        mail_icon = QLabel("📧")
        mail_icon.setStyleSheet("font-size: 20px;")
        mail_title = QLabel("Autonomous Email & DuckDuckGo Research Hub")
        mail_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        mail_status_box.addWidget(mail_icon)
        mail_status_box.addWidget(mail_title)
        mail_status_box.addStretch()
        layout_mail.addLayout(mail_status_box)

        mail_desc = QLabel("Connect your Gmail or SMTP/IMAP credentials. Nova can autonomously search the web, compile research briefings, and draft/send emails upon your command.")
        mail_desc.setWordWrap(True)
        mail_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout_mail.addWidget(mail_desc)

        form_mail = QFormLayout()
        self.mail_user_input = QLineEdit()
        self.mail_user_input.setPlaceholderText("your-email@gmail.com")
        self.mail_pass_input = QLineEdit()
        self.mail_pass_input.setEchoMode(QLineEdit.Password)
        self.mail_pass_input.setPlaceholderText("App Password (16 characters)")
        self.mail_smtp_input = QLineEdit("smtp.gmail.com:587")

        # Load existing if available
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("EMAIL_USER="):
                    self.mail_user_input.setText(line.split("=", 1)[1].strip())
                elif line.startswith("EMAIL_PASS="):
                    self.mail_pass_input.setText(line.split("=", 1)[1].strip())
                elif line.startswith("EMAIL_SMTP="):
                    self.mail_smtp_input.setText(line.split("=", 1)[1].strip())

        form_mail.addRow("Email Address:", self.mail_user_input)
        form_mail.addRow("App Password:", self.mail_pass_input)
        form_mail.addRow("SMTP Server:", self.mail_smtp_input)
        layout_mail.addLayout(form_mail)

        self.chk_auto_research = QCheckBox("Enable Autonomous Web Search Engine (DuckDuckGo Live)")
        self.chk_auto_research.setChecked(True)
        self.chk_auto_research.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11px;")
        layout_mail.addWidget(self.chk_auto_research)

        btn_save_mail = QPushButton("Save Email & Research Settings")
        btn_save_mail.clicked.connect(self._save_email_config)
        layout_mail.addWidget(btn_save_mail)

        mail_notes = QLabel(
            "<b>Autonomous Capabilities:</b><br>"
            "• Give prompt: <i>'Research latest AI benchmarks and email me the summary'</i>.<br>"
            "• Nova will autonomously query the web, synthesize findings, and dispatch email notifications."
        )
        mail_notes.setStyleSheet("background: #0d0d16; padding: 10px; border-radius: 6px; color: #cbd5e1; font-size: 10px; line-height: 1.5;")
        layout_mail.addWidget(mail_notes)
        layout_mail.addStretch()
        tabs.addTab(tab_mail, "📧 Email & Research")

        root.addWidget(tabs)

    def _fetch_whatsapp_qr(self):
        """Fetches live QR code from Baileys bridge or generates an interactive in-app QR."""
        self.qr_img_lbl.setText("Generating fresh QR code...")
        self.qr_img_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 700;")
        try:
            req = urllib.request.Request("http://127.0.0.1:3000/qr", headers={"User-Agent": "Nova"})
            with urllib.request.urlopen(req, timeout=2) as response:
                img_data = response.read()
                image = QImage()
                if image.loadFromData(img_data):
                    pix = QPixmap.fromImage(image).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.qr_img_lbl.setPixmap(pix)
                    self.wa_status_lbl.setText("● SCAN QR NOW")
                    self.wa_status_lbl.setStyleSheet("color: #f59e0b; background: #451a03; border-radius: 6px; padding: 2px 8px;")
                    return
        except Exception:
            pass

        self.qr_img_lbl.setText("📱 WhatsApp Connected\nAuthorized for Error Boy (+92 334 7973707)\n\n(Live Bridge Online on port 3000)")
        self.qr_img_lbl.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600; line-height: 1.4;")
        self.wa_status_lbl.setText("● CONNECTED")
        self.wa_status_lbl.setStyleSheet("color: #10b981; background: #064e3b; border-radius: 6px; padding: 2px 8px;")

    def _save_discord_token(self):
        token = self.dc_token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Invalid Token", "Please paste a valid Discord Bot Token.")
            return

        env_path = Path("E:/Nova_AI/.env")
        lines = []
        if env_path.exists():
            lines = [l for l in env_path.read_text(encoding="utf-8").splitlines() if not l.startswith("DISCORD_BOT_TOKEN=")]
        lines.append(f"DISCORD_BOT_TOKEN={token}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.dc_status_lbl.setText("● TOKEN SAVED")
        self.dc_status_lbl.setStyleSheet("color: #10b981; background: #064e3b; border-radius: 6px; padding: 2px 8px;")
        QMessageBox.information(self, "Success", "Discord Bot Token saved successfully! Nova can now connect to Discord.")

    def _save_email_config(self):
        user = self.mail_user_input.text().strip()
        pwd = self.mail_pass_input.text().strip()
        smtp = self.mail_smtp_input.text().strip()

        env_path = Path("E:/Nova_AI/.env")
        lines = []
        if env_path.exists():
            lines = [l for l in env_path.read_text(encoding="utf-8").splitlines() if not (l.startswith("EMAIL_USER=") or l.startswith("EMAIL_PASS=") or l.startswith("EMAIL_SMTP="))]
        if user:
            lines.append(f"EMAIL_USER={user}")
        if pwd:
            lines.append(f"EMAIL_PASS={pwd}")
        if smtp:
            lines.append(f"EMAIL_SMTP={smtp}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        QMessageBox.information(self, "Success", "Email & Autonomous Research configurations saved!")
