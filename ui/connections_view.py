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

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QImage, QPixmap, QClipboard
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.settings_schema import AppConfig, save_config
from utils.logger import get_logger

log = get_logger(__name__)

_ENV_PATH = Path("E:/Nova_AI/.env")
_AUTH_DIR = Path("E:/Nova_AI/auth_info_baileys")


class _QRFetcherWorker(QThread):
    qr_loaded = Signal(bytes)
    qr_failed = Signal()

    def run(self):
        try:
            req = urllib.request.Request("http://127.0.0.1:3000/qr", headers={"User-Agent": "NovaUI"})
            with urllib.request.urlopen(req, timeout=1.5) as response:
                img_data = response.read()
                self.qr_loaded.emit(img_data)
        except Exception:
            self.qr_failed.emit()


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

        # ── TAB 3: Email & Web Accounts Hub ──────────────────────────
        tab_mail = QWidget()
        layout_mail = QVBoxLayout(tab_mail)
        layout_mail.setContentsMargins(16, 16, 16, 16)
        layout_mail.setSpacing(12)

        mail_status_box = QHBoxLayout()
        mail_title = QLabel("Email & Connected Web Accounts Manager")
        mail_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        self.mail_status_lbl = QLabel("Not Configured")
        self.mail_status_lbl.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #1e293b; border-radius: 6px;")
        mail_status_box.addWidget(mail_title)
        mail_status_box.addStretch()
        mail_status_box.addWidget(self.mail_status_lbl)
        layout_mail.addLayout(mail_status_box)

        mail_desc = QLabel(
            "Connect your email with just your Email and Password. Nova automatically detects your provider, "
            "configures secure IMAP & SMTP, extracts 2FA/OTP login codes, and manages web accounts."
        )
        mail_desc.setWordWrap(True)
        mail_desc.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.4;")
        layout_mail.addWidget(mail_desc)

        # Connect Credentials Box
        cred_card = QFrame()
        cred_card.setStyleSheet("background-color: #0b0b14; border: 1px solid #1e1e2f; border-radius: 8px; padding: 12px;")
        cred_layout = QVBoxLayout(cred_card)
        cred_layout.setContentsMargins(12, 10, 12, 10)
        cred_layout.setSpacing(8)

        form_mail = QFormLayout()
        form_mail.setSpacing(8)

        self.mail_user_input = QLineEdit()
        self.mail_user_input.setPlaceholderText("yourname@gmail.com (or outlook, yahoo, icloud, custom)")
        self.mail_user_input.setStyleSheet("background-color: #12121c; color: #ffffff; border: 1px solid #28283d; border-radius: 6px; padding: 6px 10px; font-size: 12px;")
        self.mail_user_input.textChanged.connect(self._on_email_text_changed)

        pass_row = QHBoxLayout()
        pass_row.setSpacing(6)
        self.mail_pass_input = QLineEdit()
        self.mail_pass_input.setEchoMode(QLineEdit.Password)
        self.mail_pass_input.setPlaceholderText("Password or App Password")
        self.mail_pass_input.setStyleSheet("background-color: #12121c; color: #ffffff; border: 1px solid #28283d; border-radius: 6px; padding: 6px 10px; font-size: 12px;")
        pass_row.addWidget(self.mail_pass_input, 1)

        self.btn_toggle_pass = QPushButton("Show")
        self.btn_toggle_pass.setFixedSize(50, 30)
        self.btn_toggle_pass.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_pass.setStyleSheet("background-color: #1e1e2f; color: #94a3b8; border: 1px solid #2d2d44; border-radius: 5px; font-size: 10px;")
        self.btn_toggle_pass.clicked.connect(self._toggle_password_visibility)
        pass_row.addWidget(self.btn_toggle_pass)

        form_mail.addRow("Email Address:", self.mail_user_input)
        form_mail.addRow("App Password:", pass_row)
        cred_layout.addLayout(form_mail)

        # Provider Auto-Detection Indicator
        self.mail_detect_lbl = QLabel("Provider: Auto-detection ready (Type your email)")
        self.mail_detect_lbl.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: 600; font-family: Consolas, monospace;")
        cred_layout.addWidget(self.mail_detect_lbl)

        # Button Row
        mail_btn_row = QHBoxLayout()
        mail_btn_row.setSpacing(8)

        self.btn_save_mail = QPushButton("Connect & Verify Email")
        self.btn_save_mail.setCursor(Qt.PointingHandCursor)
        self.btn_save_mail.setFixedHeight(30)
        self.btn_save_mail.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #059669; border-radius: 6px; font-weight: 700; padding: 0 14px;")
        self.btn_save_mail.clicked.connect(self._save_email_config)
        mail_btn_row.addWidget(self.btn_save_mail)

        self.btn_disconnect_mail = QPushButton("Disconnect Email")
        self.btn_disconnect_mail.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect_mail.setFixedHeight(30)
        self.btn_disconnect_mail.setStyleSheet("background-color: #450a0a; color: #fca5a5; border: 1px solid #991b1b; border-radius: 6px; padding: 0 12px;")
        self.btn_disconnect_mail.clicked.connect(self._disconnect_email)
        mail_btn_row.addWidget(self.btn_disconnect_mail)

        mail_btn_row.addStretch()
        cred_layout.addLayout(mail_btn_row)
        layout_mail.addWidget(cred_card)

        # ── Web Accounts & 2FA Security Shield Section ────────────────
        sec_card = QFrame()
        sec_card.setStyleSheet("background-color: #0b0b14; border: 1px solid #1e1e2f; border-radius: 8px; padding: 12px;")
        sec_layout = QVBoxLayout(sec_card)
        sec_layout.setContentsMargins(12, 10, 12, 10)
        sec_layout.setSpacing(8)

        sec_hdr_row = QHBoxLayout()
        sec_title = QLabel("Connected Online Web Accounts & 2FA Shield")
        sec_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #e2e8f0;")
        sec_hdr_row.addWidget(sec_title)
        sec_hdr_row.addStretch()

        self.btn_get_otp = QPushButton("Extract Latest 2FA / OTP Code")
        self.btn_get_otp.setCursor(Qt.PointingHandCursor)
        self.btn_get_otp.setFixedHeight(26)
        self.btn_get_otp.setStyleSheet("background-color: #1e1b4b; color: #a5b4fc; border: 1px solid #4338ca; border-radius: 5px; font-size: 11px; font-weight: 600; padding: 0 10px;")
        self.btn_get_otp.clicked.connect(self._extract_latest_otp)
        sec_hdr_row.addWidget(self.btn_get_otp)

        self.btn_scan_accounts = QPushButton("Scan Connected Accounts")
        self.btn_scan_accounts.setCursor(Qt.PointingHandCursor)
        self.btn_scan_accounts.setFixedHeight(26)
        self.btn_scan_accounts.setStyleSheet("background-color: #0f172a; color: #38bdf8; border: 1px solid #0284c7; border-radius: 5px; font-size: 11px; font-weight: 600; padding: 0 10px;")
        self.btn_scan_accounts.clicked.connect(self._scan_web_accounts)
        sec_hdr_row.addWidget(self.btn_scan_accounts)
        sec_layout.addLayout(sec_hdr_row)

        # OTP Code Display Banner (initially hidden)
        self.otp_banner = QFrame()
        self.otp_banner.setVisible(False)
        self.otp_banner.setStyleSheet("background-color: #062b1b; border: 1px solid #10b981; border-radius: 6px; padding: 6px 10px;")
        otp_box = QHBoxLayout(self.otp_banner)
        otp_box.setContentsMargins(8, 4, 8, 4)
        self.otp_lbl = QLabel("")
        self.otp_lbl.setTextFormat(Qt.RichText)
        self.otp_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        otp_box.addWidget(self.otp_lbl, 1)

        self.btn_copy_otp = QPushButton("Copy Code")
        self.btn_copy_otp.setCursor(Qt.PointingHandCursor)
        self.btn_copy_otp.setFixedHeight(24)
        self.btn_copy_otp.setStyleSheet("background-color: #10b981; color: #022c22; font-weight: 700; border-radius: 4px; padding: 0 10px;")
        self.btn_copy_otp.clicked.connect(self._copy_extracted_otp)
        otp_box.addWidget(self.btn_copy_otp)
        sec_layout.addWidget(self.otp_banner)

        # Accounts Table
        self.accounts_table = QTableWidget(0, 4)
        self.accounts_table.setHorizontalHeaderLabels(["Platform / Service", "Category", "Sender Address", "Status"])
        self.accounts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.accounts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.accounts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.accounts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.accounts_table.setFixedHeight(120)
        self.accounts_table.setStyleSheet("""
            QTableWidget {
                background-color: #07070c;
                color: #e2e8f0;
                border: 1px solid #1e1e2e;
                border-radius: 6px;
                gridline-color: #1a1a28;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #0e0e18;
                color: #94a3b8;
                border: 1px solid #1e1e2e;
                padding: 4px;
                font-weight: 700;
                font-size: 10px;
            }
        """)
        sec_layout.addWidget(self.accounts_table)
        layout_mail.addWidget(sec_card)

        # Helpful Google / Outlook App Password tip
        tip_box = QLabel(
            "<b>Tip:</b> For Gmail, use an <b>App Password</b> (Google Account &gt; Security &gt; 2-Step Verification &gt; App Passwords). "
            "Nova will handle the rest automatically with zero manual port or server settings."
        )
        tip_box.setTextFormat(Qt.RichText)
        tip_box.setWordWrap(True)
        tip_box.setStyleSheet("color: #64748b; font-size: 10px; padding: 4px 6px;")
        layout_mail.addWidget(tip_box)

        layout_mail.addStretch()
        tabs.addTab(tab_mail, "Email & Web Accounts")

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
        token = getattr(self.config.discord, "bot_token", "") or os.environ.get("DISCORD_BOT_TOKEN", "")
        owner_id = getattr(self.config.discord, "owner_id", "") or os.environ.get("OWNER_DISCORD_IDS", "")

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

        if mail_user and mail_pass:
            self.mail_user_input.setText(mail_user)
            self.mail_pass_input.setText(mail_pass)
            self.mail_status_lbl.setText(f"Connected: {mail_user}")
            self.mail_status_lbl.setStyleSheet("color: #10b981; font-weight: 700; font-size: 10px; padding: 3px 10px; background: #064e3b; border-radius: 6px; border: 1px solid #059669;")
            self.btn_disconnect_mail.setEnabled(True)
            self._update_detect_label(mail_user)
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
        if hasattr(self, "_qr_worker") and self._qr_worker and self._qr_worker.isRunning():
            return
        if not silent:
            self.qr_img_lbl.setText("Requesting pairing code from local bridge...")
            self.qr_img_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        self._qr_silent = silent
        self._qr_worker = _QRFetcherWorker()
        self._qr_worker.qr_loaded.connect(self._on_qr_loaded)
        self._qr_worker.qr_failed.connect(self._on_qr_failed)
        self._qr_worker.start()

    def _on_qr_loaded(self, img_data: bytes):
        image = QImage()
        if image.loadFromData(img_data):
            pix = QPixmap.fromImage(image).scaled(190, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.qr_img_lbl.setPixmap(pix)
            self.wa_status_lbl.setText("Scan QR Code")
            self.wa_status_lbl.setStyleSheet("color: #f59e0b; background: #451a03; border-radius: 6px; padding: 3px 10px;")

    def _on_qr_failed(self):
        if not getattr(self, "_qr_silent", False):
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

    def _toggle_password_visibility(self):
        if self.mail_pass_input.echoMode() == QLineEdit.Password:
            self.mail_pass_input.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_pass.setText("Hide")
        else:
            self.mail_pass_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_pass.setText("Show")

    def _on_email_text_changed(self, text: str):
        self._update_detect_label(text)

    def _update_detect_label(self, email_str: str):
        from utils.email_manager import auto_detect_servers
        servers = auto_detect_servers(email_str)
        self.mail_detect_lbl.setText(
            f"Provider: {servers['name']} • IMAP: {servers['imap_host']}:{servers['imap_port']} • SMTP: {servers['smtp_host']}:{servers['smtp_port']}"
        )

    def _save_email_config(self):
        user = self.mail_user_input.text().strip()
        pwd = self.mail_pass_input.text().strip()

        if not user or not pwd:
            QMessageBox.warning(self, "Missing Credentials", "Please enter both Email Address and Password / App Password.")
            return

        self.btn_save_mail.setEnabled(False)
        self.btn_save_mail.setText("Verifying & Connecting...")
        QApplication.processEvents()

        try:
            from utils.email_manager import verify_email_credentials
            ok, msg, servers = verify_email_credentials(user, pwd)

            if ok:
                self.config.email.email = user
                self.config.email.app_password = pwd
                self.config.email.smtp_host = servers.get("smtp_host", "smtp.gmail.com")
                self.config.email.imap_host = servers.get("imap_host", "imap.gmail.com")
                self.config.email.enabled = True
                save_config(self.config)

                self._refresh_connection_states()
                QMessageBox.information(self, "Email Connected", f"Successfully connected to {user}!\n\n{msg}")
            else:
                QMessageBox.critical(self, "Connection Failed", f"Could not authenticate with email servers:\n\n{msg}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed during verification: {e}")
        finally:
            self.btn_save_mail.setEnabled(True)
            self.btn_save_mail.setText("Connect & Verify Email")

    def _disconnect_email(self):
        reply = QMessageBox.question(
            self,
            "Disconnect Email",
            "Are you sure you want to remove your email credentials and stop web account synchronization?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.config.email.email = ""
        self.config.email.app_password = ""
        self.config.email.enabled = False
        save_config(self.config)

        self.mail_user_input.clear()
        self.mail_pass_input.clear()
        self.otp_banner.setVisible(False)
        self.accounts_table.setRowCount(0)
        self._refresh_connection_states()
        QMessageBox.information(self, "Disconnected", "Email credentials cleared.")

    def _extract_latest_otp(self):
        user = self.config.email.email
        pwd = self.config.email.app_password

        if not user or not pwd:
            QMessageBox.warning(self, "Not Connected", "Please connect your email address first.")
            return

        self.btn_get_otp.setEnabled(False)
        self.btn_get_otp.setText("Scanning...")
        QApplication.processEvents()

        try:
            from utils.email_manager import get_latest_otp
            ok, msg, data = get_latest_otp(user, pwd, scan_limit=30)
            if ok and data:
                self._current_otp_code = data["code"]
                self.otp_lbl.setText(
                    f"<b>Latest Verification Code:</b> <span style='font-size:14px; color:#10b981; font-weight:800; font-family:Consolas;'>{data['code']}</span> "
                    f"&nbsp;•&nbsp; <b>From:</b> {data['service']} &nbsp;•&nbsp; <span style='color:#94a3b8;'>{data['date']}</span>"
                )
                self.otp_banner.setVisible(True)
                QMessageBox.information(self, "OTP Found", f"Latest Verification Code: {data['code']}\n\nFrom: {data['service']}\nSubject: {data['subject']}")
            else:
                self.otp_banner.setVisible(False)
                QMessageBox.information(self, "No Code Found", msg)
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Failed to check inbox for OTP: {e}")
        finally:
            self.btn_get_otp.setEnabled(True)
            self.btn_get_otp.setText("Extract Latest 2FA / OTP Code")

    def _copy_extracted_otp(self):
        code = getattr(self, "_current_otp_code", "")
        if code:
            QApplication.clipboard().setText(code, QClipboard.Clipboard)
            self.btn_copy_otp.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.btn_copy_otp.setText("Copy Code"))

    def _scan_web_accounts(self):
        user = self.config.email.email
        pwd = self.config.email.app_password

        if not user or not pwd:
            QMessageBox.warning(self, "Not Connected", "Please connect your email address first.")
            return

        self.btn_scan_accounts.setEnabled(False)
        self.btn_scan_accounts.setText("Scanning Accounts...")
        QApplication.processEvents()

        try:
            from utils.email_manager import scan_connected_web_accounts
            ok, accounts, summary = scan_connected_web_accounts(user, pwd, scan_limit=100)

            if not ok:
                QMessageBox.warning(self, "Scan Failed", summary)
                return

            self.accounts_table.setRowCount(0)
            for acc in accounts:
                row = self.accounts_table.rowCount()
                self.accounts_table.insertRow(row)

                item_name = QTableWidgetItem(acc["name"])
                item_name.setForeground(Qt.white)
                item_cat = QTableWidgetItem(acc["category"])
                item_cat.setForeground(Qt.cyan)
                item_sender = QTableWidgetItem(acc["sender"])
                item_sender.setForeground(Qt.lightGray)
                item_status = QTableWidgetItem("Active")
                item_status.setForeground(Qt.green)

                self.accounts_table.setItem(row, 0, item_name)
                self.accounts_table.setItem(row, 1, item_cat)
                self.accounts_table.setItem(row, 2, item_sender)
                self.accounts_table.setItem(row, 3, item_status)

            QMessageBox.information(self, "Accounts Discovered", f"{summary}\n\nAll accounts populated in the table below.")
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Error scanning accounts: {e}")
        finally:
            self.btn_scan_accounts.setEnabled(True)
            self.btn_scan_accounts.setText("Scan Connected Accounts")

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
