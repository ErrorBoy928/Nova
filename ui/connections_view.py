"""
ui/connections_view.py

Platform Connections View for Nova AI.
Professional executive management interface for:
- WhatsApp Web Bridge (Owner Number setup, Baileys QR pairing, session status, live disconnect)
- Discord Bot (Bot Token setup, Owner ID configuration, status verification, disconnect)
- Email & Autonomous Web Research (SMTP credentials, connection test, disconnect)
"""

from __future__ import annotations

import json
import os
import shutil
import smtplib
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

_ENV_PATH = Path("E:/Nova_AI/.env")
_AUTH_DIR = Path("E:/Nova_AI/auth_info_baileys")


class ConnectionsView(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._apply_theme()
        self._build_ui()
        self._refresh_connection_states()

        # Seamless auto-polling timer for pairing and status transitions
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(4500)
        self._poll_timer.timeout.connect(self._auto_check_status)
        self._poll_timer.start()

    def _auto_check_status(self):
        """Silently verifies if WhatsApp was paired or credentials changed."""
        has_auth = _AUTH_DIR.exists() and any(_AUTH_DIR.glob("*.json"))
        is_ui_connected = (self.wa_status_lbl.text() == "Connected")

        if has_auth and not is_ui_connected:
            self._refresh_connection_states()
        elif not has_auth and is_ui_connected:
            self._refresh_connection_states()
        elif self.wa_status_lbl.text() == "Scan QR Code" and self.isVisible():
            self._fetch_whatsapp_qr(silent=True)

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
                padding: 10px 22px;
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
            QLineEdit, QComboBox {
                background-color: #12121a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 7px 10px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: 700;
                font-size: 11px;
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
        title_lbl = QLabel("PLATFORM CONNECTIONS HUB")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px;")
        sub_lbl = QLabel("Manage integrations, authorization states, and connection sessions for external channels.")
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
        wa_title = QLabel("WhatsApp Web Socket Bridge")
        wa_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        self.wa_status_lbl = QLabel("Disconnected")
        self.wa_status_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #1e293b; border-radius: 6px;")
        wa_status_box.addWidget(wa_title)
        wa_status_box.addStretch()
        wa_status_box.addWidget(self.wa_status_lbl)
        layout_wa.addLayout(wa_status_box)

        # Owner Phone Setup on WhatsApp Tab
        wa_owner_form = QFormLayout()
        wa_owner_row = QHBoxLayout()
        self.wa_owner_input = QLineEdit()
        self.wa_owner_input.setPlaceholderText("Enter your WhatsApp number (e.g. +923001234567)...")
        self.btn_save_wa_owner = QPushButton("Save Number")
        self.btn_save_wa_owner.setFixedWidth(110)
        self.btn_save_wa_owner.clicked.connect(self._save_wa_owner_number)
        wa_owner_row.addWidget(self.wa_owner_input)
        wa_owner_row.addWidget(self.btn_save_wa_owner)
        wa_owner_form.addRow("Owner Mobile (Optional):", wa_owner_row)
        layout_wa.addLayout(wa_owner_form)

        self.wa_info_lbl = QLabel("Scan the QR code below with your WhatsApp mobile client to link this instance as your assistant.")
        self.wa_info_lbl.setWordWrap(True)
        self.wa_info_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout_wa.addWidget(self.wa_info_lbl)

        # QR Display Container
        self.qr_frame = QFrame()
        self.qr_frame.setStyleSheet("background-color: #12121a; border: 1px dashed #334155; border-radius: 8px; min-height: 180px;")
        qr_layout = QVBoxLayout(self.qr_frame)
        qr_layout.setAlignment(Qt.AlignCenter)

        self.qr_img_lbl = QLabel("Click 'Generate QR Code' to start pairing.")
        self.qr_img_lbl.setAlignment(Qt.AlignCenter)
        self.qr_img_lbl.setStyleSheet("color: #64748b; font-weight: 600; font-size: 11px;")
        qr_layout.addWidget(self.qr_img_lbl)
        layout_wa.addWidget(self.qr_frame)

        wa_btn_row = QHBoxLayout()
        self.btn_gen_qr = QPushButton("Generate / Refresh QR Code")
        self.btn_gen_qr.clicked.connect(self._fetch_whatsapp_qr)
        wa_btn_row.addWidget(self.btn_gen_qr)

        self.btn_disconnect_wa = QPushButton("Disconnect WhatsApp")
        self.btn_disconnect_wa.setStyleSheet("background-color: #450a0a; color: #fca5a5; border: 1px solid #991b1b;")
        self.btn_disconnect_wa.clicked.connect(self._disconnect_whatsapp)
        wa_btn_row.addWidget(self.btn_disconnect_wa)
        layout_wa.addLayout(wa_btn_row)

        wa_cmds = QLabel(
            "<b>Supported WhatsApp Commands:</b><br>"
            "• <code>!screen</code> : Captures desktop screen and returns high-resolution image<br>"
            "• <code>!pc &lt;cmd&gt;</code> : Executes remote system command (e.g. <code>!pc open notepad</code>)<br>"
            "• <code>!pctasks</code> : Lists current autonomous agent tasks<br>"
            "• <code>!pcstats</code> : Reports live CPU, Memory, and Disk diagnostics<br>"
            "• <code>!stop</code> / <code>!start</code> : Pauses or resumes auto-responder for this chat"
        )
        wa_cmds.setStyleSheet("background: #0d0d16; padding: 10px; border-radius: 6px; color: #cbd5e1; font-size: 10px; line-height: 1.5; border: 1px solid #1e293b;")
        layout_wa.addWidget(wa_cmds)
        layout_wa.addStretch()
        tabs.addTab(tab_wa, "WhatsApp")

        # ── TAB 2: Discord ───────────────────────────────────────────
        tab_dc = QWidget()
        layout_dc = QVBoxLayout(tab_dc)
        layout_dc.setContentsMargins(16, 16, 16, 16)
        layout_dc.setSpacing(12)

        dc_status_box = QHBoxLayout()
        dc_title = QLabel("Discord Superbot Gateway")
        dc_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        self.dc_status_lbl = QLabel("Disconnected")
        self.dc_status_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #1e293b; border-radius: 6px;")
        dc_status_box.addWidget(dc_title)
        dc_status_box.addStretch()
        dc_status_box.addWidget(self.dc_status_lbl)
        layout_dc.addLayout(dc_status_box)

        dc_desc = QLabel("Configure your Discord Bot Token to run Nova inside your Discord server or private direct messages.")
        dc_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout_dc.addWidget(dc_desc)

        form_dc = QFormLayout()
        form_dc.setSpacing(10)

        dc_token_box = QHBoxLayout()
        self.dc_token_input = QLineEdit()
        self.dc_token_input.setEchoMode(QLineEdit.Password)
        self.dc_token_input.setPlaceholderText("Paste Discord Bot Token here...")
        self.btn_toggle_dc = QPushButton("Show")
        self.btn_toggle_dc.setFixedWidth(56)
        self.btn_toggle_dc.clicked.connect(self._toggle_dc_visibility)
        dc_token_box.addWidget(self.dc_token_input)
        dc_token_box.addWidget(self.btn_toggle_dc)
        form_dc.addRow("Bot Token:", dc_token_box)

        self.dc_owner_input = QLineEdit()
        self.dc_owner_input.setPlaceholderText("Enter owner Discord ID or Username (Optional)...")
        form_dc.addRow("Owner ID (Optional):", self.dc_owner_input)

        layout_dc.addLayout(form_dc)

        dc_btn_row = QHBoxLayout()
        btn_save_dc = QPushButton("Save & Connect Discord")
        btn_save_dc.clicked.connect(self._save_discord_token)
        dc_btn_row.addWidget(btn_save_dc)

        self.btn_disconnect_dc = QPushButton("Disconnect Discord")
        self.btn_disconnect_dc.setStyleSheet("background-color: #450a0a; color: #fca5a5; border: 1px solid #991b1b;")
        self.btn_disconnect_dc.clicked.connect(self._disconnect_discord)
        dc_btn_row.addWidget(self.btn_disconnect_dc)
        layout_dc.addLayout(dc_btn_row)

        dc_cmds = QLabel(
            "<b>Supported Discord Commands:</b><br>"
            "• <code>!screen</code> : Takes live PC screenshot and embeds in Discord<br>"
            "• <code>!pc &lt;action&gt;</code> : Executes remote system action<br>"
            "• <code>!pctasks</code> : Displays status of scheduled agent tasks<br>"
            "• <code>!pcstats</code> : Reports machine resource usage<br>"
            "• <code>!secret &lt;key&gt;</code> : Reads or stores encrypted credentials in vault"
        )
        dc_cmds.setStyleSheet("background: #0d0d16; padding: 10px; border-radius: 6px; color: #cbd5e1; font-size: 10px; line-height: 1.5; border: 1px solid #1e293b;")
        layout_dc.addWidget(dc_cmds)
        layout_dc.addStretch()
        tabs.addTab(tab_dc, "Discord")

        # ── TAB 3: Email & Research ──────────────────────────────────
        tab_mail = QWidget()
        layout_mail = QVBoxLayout(tab_mail)
        layout_mail.setContentsMargins(16, 16, 16, 16)
        layout_mail.setSpacing(12)

        mail_status_box = QHBoxLayout()
        mail_title = QLabel("Email Service & Autonomous Web Research")
        mail_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        self.mail_status_lbl = QLabel("Not Configured")
        self.mail_status_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #1e293b; border-radius: 6px;")
        mail_status_box.addWidget(mail_title)
        mail_status_box.addStretch()
        mail_status_box.addWidget(self.mail_status_lbl)
        layout_mail.addLayout(mail_status_box)

        mail_desc = QLabel("Connect SMTP credentials for automated briefing dispatches, task notifications, and email forwarding.")
        mail_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout_mail.addWidget(mail_desc)

        form_mail = QFormLayout()
        form_mail.setSpacing(10)

        self.mail_smtp_input = QLineEdit("smtp.gmail.com")
        self.mail_port_input = QLineEdit("587")
        self.mail_sec_combo = QComboBox()
        self.mail_sec_combo.addItems(["STARTTLS (Port 587)", "SSL (Port 465)", "Plain (Port 25)"])

        self.mail_user_input = QLineEdit()
        self.mail_user_input.setPlaceholderText("user@example.com")
        self.mail_pass_input = QLineEdit()
        self.mail_pass_input.setEchoMode(QLineEdit.Password)
        self.mail_pass_input.setPlaceholderText("SMTP App Password")

        form_mail.addRow("SMTP Host:", self.mail_smtp_input)
        form_mail.addRow("SMTP Port:", self.mail_port_input)
        form_mail.addRow("Encryption:", self.mail_sec_combo)
        form_mail.addRow("Email Address:", self.mail_user_input)
        form_mail.addRow("Password / Key:", self.mail_pass_input)
        layout_mail.addLayout(form_mail)

        self.chk_auto_research = QCheckBox("Enable Autonomous DuckDuckGo Research Engine")
        self.chk_auto_research.setChecked(True)
        self.chk_auto_research.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11px;")
        layout_mail.addWidget(self.chk_auto_research)

        mail_btn_row = QHBoxLayout()
        btn_save_mail = QPushButton("Save Email Configuration")
        btn_save_mail.clicked.connect(self._save_email_config)
        mail_btn_row.addWidget(btn_save_mail)

        btn_test_mail = QPushButton("Test SMTP Connection")
        btn_test_mail.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;")
        btn_test_mail.clicked.connect(self._test_smtp_connection)
        mail_btn_row.addWidget(btn_test_mail)

        self.btn_disconnect_mail = QPushButton("Clear Email")
        self.btn_disconnect_mail.setStyleSheet("background-color: #450a0a; color: #fca5a5; border: 1px solid #991b1b;")
        self.btn_disconnect_mail.clicked.connect(self._disconnect_email)
        mail_btn_row.addWidget(self.btn_disconnect_mail)

        layout_mail.addLayout(mail_btn_row)
        layout_mail.addStretch()
        tabs.addTab(tab_mail, "Email & Research")

        root.addWidget(tabs)

        # Bottom Bar: Factory Reset
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_reset_all = QPushButton("Reset All Connections")
        btn_reset_all.setStyleSheet("background-color: #272735; color: #ef4444; border: 1px solid #450a0a; font-size: 10px; padding: 5px 12px;")
        btn_reset_all.clicked.connect(self._reset_all_connections)
        bottom_row.addWidget(btn_reset_all)
        root.addLayout(bottom_row)

    def _toggle_dc_visibility(self):
        if self.dc_token_input.echoMode() == QLineEdit.Password:
            self.dc_token_input.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_dc.setText("Hide")
        else:
            self.dc_token_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_dc.setText("Show")

    def _refresh_connection_states(self):
        """Inspects disk/environment and updates badges and fields dynamically."""
        # 1. WhatsApp
        has_auth = _AUTH_DIR.exists() and any(_AUTH_DIR.glob("*.json"))
        if has_auth:
            self.wa_status_lbl.setText("Connected")
            self.wa_status_lbl.setStyleSheet("color: #10b981; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #064e3b; border-radius: 6px; border: 1px solid #059669;")
            self.qr_img_lbl.setText("Device session is active and linked.\nWhatsApp bridge is listening for commands.")
            self.qr_img_lbl.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600; line-height: 1.5;")
            self.btn_disconnect_wa.setEnabled(True)
        else:
            self.wa_status_lbl.setText("Disconnected")
            self.wa_status_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #1e293b; border-radius: 6px;")
            self.qr_img_lbl.setText("Click 'Generate QR Code' to pair your device.")
            self.qr_img_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
            self.btn_disconnect_wa.setEnabled(False)

        saved_wa_num = self.config.whatsapp.owner_number or os.environ.get("OWNER_NUMBERS", "")
        self.wa_owner_input.setText(saved_wa_num)

        # 2. Discord
        token = self.config.discord.bot_token or os.environ.get("DISCORD_BOT_TOKEN", "")
        owner_id = self.config.discord.owner_id or os.environ.get("OWNER_DISCORD_IDS", "")

        if token:
            self.dc_token_input.setText(token)
            self.dc_status_lbl.setText("Connected")
            self.dc_status_lbl.setStyleSheet("color: #10b981; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #064e3b; border-radius: 6px; border: 1px solid #059669;")
            self.btn_disconnect_dc.setEnabled(True)
        else:
            self.dc_token_input.clear()
            self.dc_status_lbl.setText("Disconnected")
            self.dc_status_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #1e293b; border-radius: 6px;")
            self.btn_disconnect_dc.setEnabled(False)

        self.dc_owner_input.setText(owner_id)

        # 3. Email
        mail_user = self.config.email.email or os.environ.get("EMAIL_USER", "")
        mail_pass = self.config.email.app_password or os.environ.get("EMAIL_PASS", "")
        mail_smtp = self.config.email.smtp_host or os.environ.get("EMAIL_SMTP", "smtp.gmail.com")

        if mail_user and mail_pass:
            self.mail_user_input.setText(mail_user)
            self.mail_pass_input.setText(mail_pass)
            self.mail_smtp_input.setText(mail_smtp)
            self.mail_status_lbl.setText("Configured")
            self.mail_status_lbl.setStyleSheet("color: #10b981; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #064e3b; border-radius: 6px; border: 1px solid #059669;")
            self.btn_disconnect_mail.setEnabled(True)
        else:
            self.mail_status_lbl.setText("Not Configured")
            self.mail_status_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #1e293b; border-radius: 6px;")
            self.btn_disconnect_mail.setEnabled(False)

    def _save_wa_owner_number(self):
        num = self.wa_owner_input.text().strip()
        self.config.whatsapp.owner_number = num
        save_config(self.config)
        self._refresh_connection_states()
        QMessageBox.information(self, "Saved", f"WhatsApp owner mobile number saved successfully:\n{num or '(Cleared)'}")

    def _fetch_whatsapp_qr(self, silent: bool = False):
        if not silent:
            self.qr_img_lbl.setText("Requesting pairing code from local bridge...")
            self.qr_img_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        try:
            req = urllib.request.Request("http://127.0.0.1:3000/qr", headers={"User-Agent": "NovaUI"})
            with urllib.request.urlopen(req, timeout=2) as response:
                img_data = response.read()
                image = QImage()
                if image.loadFromData(img_data):
                    pix = QPixmap.fromImage(image).scaled(190, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.qr_img_lbl.setPixmap(pix)
                    self.wa_status_lbl.setText("Scan QR Code")
                    self.wa_status_lbl.setStyleSheet("color: #f59e0b; background: #451a03; border-radius: 6px; padding: 3px 10px;")
                    return
        except Exception:
            pass

        if not silent:
            self.qr_img_lbl.setText("WhatsApp Bridge Offline (Port 3000).\nRun 'node index.js' to start the local bridge.")
            self.qr_img_lbl.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 600; line-height: 1.4;")

    def _disconnect_whatsapp(self):
        reply = QMessageBox.question(
            self,
            "Disconnect WhatsApp",
            "Are you sure you want to log out and clear the WhatsApp session?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            req = urllib.request.Request(
                "http://127.0.0.1:3000/whatsapp/disconnect",
                data=b"{}",
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass

        if _AUTH_DIR.exists():
            shutil.rmtree(_AUTH_DIR, ignore_errors=True)

        self._refresh_connection_states()
        QMessageBox.information(self, "Disconnected", "WhatsApp session has been terminated and cleared.")

    def _save_discord_token(self):
        token = self.dc_token_input.text().strip()
        owner_id = self.dc_owner_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Invalid Token", "Please paste a valid Discord Bot Token.")
            return

        self.config.discord.bot_token = token
        self.config.discord.owner_id = owner_id
        save_config(self.config)

        self._refresh_connection_states()
        QMessageBox.information(self, "Saved", "Discord Bot Token and Owner ID saved successfully.")

    def _disconnect_discord(self):
        reply = QMessageBox.question(
            self,
            "Disconnect Discord",
            "Clear the saved Discord Bot Token?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.config.discord.bot_token = ""
        self.config.discord.owner_id = ""
        save_config(self.config)

        self.dc_token_input.clear()
        self.dc_owner_input.clear()
        self._refresh_connection_states()
        QMessageBox.information(self, "Disconnected", "Discord token cleared.")

    def _save_email_config(self):
        user = self.mail_user_input.text().strip()
        pwd = self.mail_pass_input.text().strip()
        smtp = self.mail_smtp_input.text().strip()

        if not user or not pwd:
            QMessageBox.warning(self, "Missing Credentials", "Please enter both Email Address and App Password.")
            return

        self.config.email.email = user
        self.config.email.app_password = pwd
        self.config.email.smtp_host = smtp
        save_config(self.config)

        self._refresh_connection_states()
        QMessageBox.information(self, "Saved", "Email configuration saved successfully.")

    def _test_smtp_connection(self):
        user = self.mail_user_input.text().strip()
        pwd = self.mail_pass_input.text().strip()
        smtp_host = self.mail_smtp_input.text().strip() or "smtp.gmail.com"
        port_str = self.mail_port_input.text().strip() or "587"

        if not user or not pwd:
            QMessageBox.warning(self, "Missing Fields", "Please enter Email Address and Password to test.")
            return

        try:
            port = int(port_str)
            server = smtplib.SMTP(smtp_host, port, timeout=6)
            server.ehlo()
            server.starttls()
            server.login(user, pwd)
            server.quit()
            QMessageBox.information(self, "Success", f"SMTP Connection verified successfully for {user}!")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"SMTP Authentication failed:\n{str(e)}")

    def _disconnect_email(self):
        reply = QMessageBox.question(
            self,
            "Clear Email",
            "Clear saved email credentials?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.config.email.email = ""
        self.config.email.app_password = ""
        save_config(self.config)

        self.mail_user_input.clear()
        self.mail_pass_input.clear()
        self._refresh_connection_states()
        QMessageBox.information(self, "Cleared", "Email credentials cleared.")

    def _reset_all_connections(self):
        reply = QMessageBox.critical(
            self,
            "Reset All Connections",
            "This will disconnect WhatsApp, remove Discord bot credentials, and wipe saved email configurations. Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        if _AUTH_DIR.exists():
            shutil.rmtree(_AUTH_DIR, ignore_errors=True)

        self.config.discord.bot_token = ""
        self.config.discord.owner_id = ""
        self.config.whatsapp.owner_number = ""
        self.config.email.email = ""
        self.config.email.app_password = ""
        save_config(self.config)

        self.dc_token_input.clear()
        self.dc_owner_input.clear()
        self.wa_owner_input.clear()
        self.mail_user_input.clear()
        self.mail_pass_input.clear()

        self._refresh_connection_states()
        QMessageBox.information(self, "Reset Complete", "All platform connections have been reset.")
