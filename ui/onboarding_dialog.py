"""
ui/onboarding_dialog.py

First-Run Welcome & Setup Wizard for Nova AI.
Presents a simple, zero-confusion setup screen when Nova is launched for the first time:
- User Name (Optional)
- Groq API Key (with 1-click link to free key)
- Mobile / WhatsApp Number (Optional)
Saves settings to config, updates .env, and seamlessly transitions to the main studio.
"""

from __future__ import annotations

import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from config.settings_schema import AppConfig, save_config


class WelcomeWizardDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Welcome to Nova AI")
        self.setFixedWidth(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #09090b;
                color: #f8fafc;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLineEdit {
                background-color: #12121a;
                border: 1px solid #22222b;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                padding: 8px 16px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        # Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title_lbl = QLabel("Welcome to Nova AI")
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Let's configure your personal assistant in 10 seconds. You can always adjust these later in Settings.")
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; line-height: 1.4;")
        title_box.addWidget(sub_lbl)
        root.addLayout(title_box)

        # Main Setup Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #111116;
                border: 1px solid #22222b;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)

        # 1. User Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your name (e.g. Mohib, Alex - Default: User)")
        if self.config.user_name:
            self.name_input.setText(self.config.user_name)
        form.addRow("Your Name (Optional):", self.name_input)

        # 2. Groq API Key
        key_box = QHBoxLayout()
        key_box.setSpacing(6)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Paste Groq API Key (gsk_...)...")
        if self.config.llm.api_key:
            self.key_input.setText(self.config.llm.api_key)

        self.btn_show_key = QPushButton("Show")
        self.btn_show_key.setFixedWidth(52)
        self.btn_show_key.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.btn_show_key.clicked.connect(self._toggle_key_visibility)
        key_box.addWidget(self.key_input)
        key_box.addWidget(self.btn_show_key)
        form.addRow("Groq API Key:", key_box)

        # 3. Mobile Number (Optional)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("e.g. +923001234567 (Optional)")
        if self.config.whatsapp.owner_number:
            self.phone_input.setText(self.config.whatsapp.owner_number)
        form.addRow("Mobile (Optional):", self.phone_input)

        card_layout.addLayout(form)

        # Get Free Key Hint Row
        hint_box = QHBoxLayout()
        hint_lbl = QLabel("Need an API key? Groq offers fast free keys with zero credit card.")
        hint_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        hint_box.addWidget(hint_lbl)
        hint_box.addStretch()

        btn_get_free = QPushButton("Get Free Key")
        btn_get_free.setFixedHeight(24)
        btn_get_free.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #272735;
                color: #38bdf8;
                font-size: 10px;
                padding: 0 10px;
            }
            QPushButton:hover {
                border-color: #38bdf8;
                background-color: #0c1c2e;
            }
        """)
        btn_get_free.clicked.connect(lambda: webbrowser.open("https://console.groq.com/keys"))
        hint_box.addWidget(btn_get_free)

        card_layout.addLayout(hint_box)
        root.addWidget(card)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_skip = QPushButton("Skip for Now")
        btn_skip.setFixedHeight(34)
        btn_skip.setCursor(Qt.PointingHandCursor)
        btn_skip.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #22222b;
                color: #94a3b8;
                padding: 0 16px;
            }
            QPushButton:hover {
                color: #ffffff;
                border-color: #475569;
            }
        """)
        btn_skip.clicked.connect(self.reject)
        btn_row.addWidget(btn_skip)

        btn_row.addStretch()

        btn_start = QPushButton("Start Nova AI")
        btn_start.setFixedHeight(34)
        btn_start.setCursor(Qt.PointingHandCursor)
        btn_start.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                padding: 0 22px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        btn_start.clicked.connect(self._save_and_start)
        btn_row.addWidget(btn_start)

        root.addLayout(btn_row)

    def _toggle_key_visibility(self):
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
            self.btn_show_key.setText("Hide")
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            self.btn_show_key.setText("Show")

    def _save_and_start(self):
        name = self.name_input.text().strip()
        key = self.key_input.text().strip().strip('"\'')
        phone = self.phone_input.text().strip()

        if name:
            self.config.user_name = name
        if key:
            self.config.llm.api_key = key
            self.config.llm.provider = "groq"
            self.config.llm.model = "qwen/qwen3.8-27b"
        if phone:
            self.config.whatsapp.owner_number = phone

        save_config(self.config)
        self.accept()
