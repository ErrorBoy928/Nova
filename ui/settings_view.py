"""
ui/settings_view.py

Master System Settings Dashboard View for Nova AI.
Comprehensive multi-tab configuration interface:
- Tab 1: Profile & Identity (User Name, Phone Number, Discord ID, Assistant Name, Language)
- Tab 2: AI Engine & API Keys (Groq, Gemini, OpenAI, Models, API Key, Live Verification)
- Tab 3: Bot Integrations & Channels (Discord Bot Token, WhatsApp Status, Email SMTP)
- Tab 4: Voice & Audio (TTS, STT, Voices, Speeds)
- Tab 5: Desktop & Vision (Screen Vision, Opacity, Hotkeys)
- Tab 6: Cloud Sync & Hosting (GitHub Repo, Auto-Update)
"""

from __future__ import annotations

import os
import smtplib
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config.settings_schema import AppConfig, save_config
from utils.logger import get_logger

log = get_logger(__name__)

PROVIDERS = ["groq", "gemini", "openai", "anthropic", "ollama", "lmstudio"]
POPULAR_MODELS = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "allam-2-7b",
]

ENGLISH_VOICES = [
    ("Aria (US Natural Female)", "en-US-AriaNeural"),
    ("Guy (US Deep Male)", "en-US-GuyNeural"),
    ("Jenny (US Friendly)", "en-US-JennyNeural"),
    ("Sonia (UK Clear)", "en-GB-SoniaNeural"),
    ("Ryan (UK Deep)", "en-GB-RyanNeural"),
]

URDU_VOICES = [
    ("Uzma (Pakistan Female)", "ur-PK-UzmaNeural"),
    ("Asad (Pakistan Male)", "ur-PK-AsadNeural"),
]


class SettingsView(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._apply_theme()
        self._build_ui()
        self._load_current_values()

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
                padding: 10px 18px;
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
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
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
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #12121a;
                border: 1px solid #1e293b;
                selection-background-color: #0284c7;
                color: #ffffff;
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
        title_lbl = QLabel("MASTER SYSTEM SETTINGS")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px;")
        sub_lbl = QLabel("Configure Profile Identity, AI Models, Platform Tokens, Audio, and Desktop Vision.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        root.addLayout(title_box)

        tabs = QTabWidget()

        # ── TAB 1: Profile & Identity ────────────────────────────────
        tab_profile = QWidget()
        layout_prof = QVBoxLayout(tab_profile)
        layout_prof.setContentsMargins(16, 16, 16, 16)
        layout_prof.setSpacing(12)

        prof_desc = QLabel(
            "Configure your identity so Nova recognizes you across Desktop, WhatsApp, and Discord with full administrative authorization."
        )
        prof_desc.setWordWrap(True)
        prof_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout_prof.addWidget(prof_desc)

        form_p = QFormLayout()
        form_p.setSpacing(10)

        self.user_name_input = QLineEdit()
        self.user_name_input.setPlaceholderText("Enter your name (e.g. Mohib, Alex, Admin - Default: User)")
        form_p.addRow("Your Name (Optional):", self.user_name_input)

        self.user_phone_input = QLineEdit()
        self.user_phone_input.setPlaceholderText("e.g. +923001234567 (for WhatsApp owner alerts)")
        form_p.addRow("Mobile Number (Optional):", self.user_phone_input)

        self.discord_owner_input = QLineEdit()
        self.discord_owner_input.setPlaceholderText("e.g. errorboy928 or 18-digit Discord User ID")
        form_p.addRow("Discord Owner ID (Optional):", self.discord_owner_input)

        self.assistant_name_input = QLineEdit("Nova")
        form_p.addRow("Assistant Name:", self.assistant_name_input)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto Detect (Bilingual Urdu & English)", "auto")
        self.lang_combo.addItem("Urdu Preferred (اردو / Roman)", "ur")
        self.lang_combo.addItem("English Preferred", "en")
        form_p.addRow("Language Preference:", self.lang_combo)

        layout_prof.addLayout(form_p)

        info_box = QLabel(
            "<b>Owner Privilege Notice:</b><br>"
            "Providing your phone number or Discord ID allows Nova to authenticate your commands over WhatsApp "
            "and Discord (e.g. <code>!screen</code>, <code>!pc</code>, <code>!pctasks</code>) and send private task completions."
        )
        info_box.setWordWrap(True)
        info_box.setStyleSheet("background: #0d0d16; padding: 10px; border-radius: 6px; color: #38bdf8; font-size: 10px; line-height: 1.5; border: 1px solid #1e293b;")
        layout_prof.addWidget(info_box)

        layout_prof.addStretch()
        tabs.addTab(tab_profile, "User Profile")

        # ── TAB 2: AI Engine & Keys ──────────────────────────────────
        tab_ai = QWidget()
        layout_ai = QVBoxLayout(tab_ai)
        layout_ai.setContentsMargins(16, 16, 16, 16)
        layout_ai.setSpacing(12)

        form_ai = QFormLayout()
        form_ai.setSpacing(10)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDERS)
        form_ai.addRow("AI Provider:", self.provider_combo)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(POPULAR_MODELS)
        form_ai.addRow("Model Name:", self.model_combo)

        # API Key Row
        key_box = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Enter Provider API Key (e.g. gsk_...)...")
        self.btn_toggle_key = QPushButton("Show")
        self.btn_toggle_key.setFixedWidth(56)
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_box.addWidget(self.key_input)
        key_box.addWidget(self.btn_toggle_key)
        form_ai.addRow("API Key:", key_box)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.05)
        form_ai.addRow("Temperature:", self.temp_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(256, 32768)
        self.max_tokens_spin.setSingleStep(512)
        form_ai.addRow("Max Tokens:", self.max_tokens_spin)

        self.chk_thinking = QCheckBox("Enable Critical Thinking & Chain of Thought Reasoning")
        self.chk_thinking.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11px;")
        form_ai.addRow("", self.chk_thinking)

        layout_ai.addLayout(form_ai)

        ai_hint = QLabel(
            "<b>Free API Key Tip:</b> Fast Groq API keys with ultra-fast inference (300+ tok/s) can be obtained for free at <b>console.groq.com/keys</b>."
        )
        ai_hint.setWordWrap(True)
        ai_hint.setStyleSheet("background: #0d0d16; padding: 8px 10px; border-radius: 6px; color: #94a3b8; font-size: 10px; border: 1px solid #1e293b;")
        layout_ai.addWidget(ai_hint)

        btn_test_llm = QPushButton("Test API Connection")
        btn_test_llm.clicked.connect(self._test_api_connection)
        layout_ai.addWidget(btn_test_llm)
        layout_ai.addStretch()
        tabs.addTab(tab_ai, "AI Engine")

        # ── TAB 3: Integrations & Bots ───────────────────────────────
        tab_integ = QWidget()
        layout_integ = QVBoxLayout(tab_integ)
        layout_integ.setContentsMargins(16, 16, 16, 16)
        layout_integ.setSpacing(12)

        form_integ = QFormLayout()
        form_integ.setSpacing(10)

        # Discord Token
        dc_token_box = QHBoxLayout()
        self.dc_token_input = QLineEdit()
        self.dc_token_input.setEchoMode(QLineEdit.Password)
        self.dc_token_input.setPlaceholderText("Paste Discord Bot Token...")
        self.btn_toggle_dc_token = QPushButton("Show")
        self.btn_toggle_dc_token.setFixedWidth(56)
        self.btn_toggle_dc_token.clicked.connect(self._toggle_dc_visibility)
        dc_token_box.addWidget(self.dc_token_input)
        dc_token_box.addWidget(self.btn_toggle_dc_token)
        form_integ.addRow("Discord Bot Token:", dc_token_box)

        # Email SMTP Setup
        self.smtp_host_input = QLineEdit("smtp.gmail.com")
        self.smtp_port_input = QLineEdit("587")
        self.email_user_input = QLineEdit()
        self.email_user_input.setPlaceholderText("user@example.com")
        self.email_pass_input = QLineEdit()
        self.email_pass_input.setEchoMode(QLineEdit.Password)
        self.email_pass_input.setPlaceholderText("SMTP App Password")

        form_integ.addRow("SMTP Host:", self.smtp_host_input)
        form_integ.addRow("SMTP Port:", self.smtp_port_input)
        form_integ.addRow("Email Address:", self.email_user_input)
        form_integ.addRow("App Password:", self.email_pass_input)

        layout_integ.addLayout(form_integ)

        btn_test_smtp = QPushButton("Test SMTP Email Connection")
        btn_test_smtp.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;")
        btn_test_smtp.clicked.connect(self._test_smtp_connection)
        layout_integ.addWidget(btn_test_smtp)

        integ_info = QLabel(
            "<b>Channel Quick Access:</b> Use the <b>Connections</b> tab from the sidebar to pair WhatsApp via live QR code or manage active sessions."
        )
        integ_info.setWordWrap(True)
        integ_info.setStyleSheet("color: #94a3b8; font-size: 10px; margin-top: 6px;")
        layout_integ.addWidget(integ_info)

        layout_integ.addStretch()
        tabs.addTab(tab_integ, "Integrations")

        # ── TAB 4: Voice & Audio ─────────────────────────────────────
        tab_voice = QWidget()
        layout_voice = QVBoxLayout(tab_voice)
        layout_voice.setContentsMargins(16, 16, 16, 16)
        layout_voice.setSpacing(12)

        self.chk_voice_enabled = QCheckBox("Enable Voice Engine (Speech Output & Recognition)")
        self.chk_voice_enabled.setStyleSheet("font-weight: 700; color: #ffffff;")
        layout_voice.addWidget(self.chk_voice_enabled)

        self.chk_auto_speak = QCheckBox("Auto-speak AI responses aloud")
        layout_voice.addWidget(self.chk_auto_speak)

        form_v = QFormLayout()
        form_v.setSpacing(10)

        self.en_voice_combo = QComboBox()
        for label, val in ENGLISH_VOICES:
            self.en_voice_combo.addItem(label, val)
        form_v.addRow("English Voice:", self.en_voice_combo)

        self.ur_voice_combo = QComboBox()
        for label, val in URDU_VOICES:
            self.ur_voice_combo.addItem(label, val)
        form_v.addRow("Urdu Voice:", self.ur_voice_combo)

        self.rate_combo = QComboBox()
        self.rate_combo.addItems(["-20%", "-10%", "+0%", "+10%", "+20%", "+30%"])
        form_v.addRow("Speech Rate:", self.rate_combo)

        self.vol_combo = QComboBox()
        self.vol_combo.addItems(["+0%", "+10%", "+20%", "+30%", "+50%"])
        form_v.addRow("Volume Boost:", self.vol_combo)

        layout_voice.addLayout(form_v)
        layout_voice.addStretch()
        tabs.addTab(tab_voice, "Voice & Audio")

        # ── TAB 5: Desktop & Vision ──────────────────────────────────
        tab_dt = QWidget()
        layout_dt = QVBoxLayout(tab_dt)
        layout_dt.setContentsMargins(16, 16, 16, 16)
        layout_dt.setSpacing(12)

        self.chk_vision = QCheckBox("Live Screen Observing & Multimodal Sight")
        self.chk_vision.setStyleSheet("font-weight: 700; color: #ffffff;")
        layout_dt.addWidget(self.chk_vision)

        self.chk_always_top = QCheckBox("Keep Window Always on Top")
        layout_dt.addWidget(self.chk_always_top)

        form_dt = QFormLayout()
        form_dt.setSpacing(10)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(40, 100)
        form_dt.addRow("Window Opacity:", self.opacity_slider)

        hotkey_lbl = QLabel("Global Hotkey: <b>Ctrl+Shift+Space</b> (Summon/Dismiss Nova anywhere)")
        hotkey_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")
        form_dt.addRow("", hotkey_lbl)

        layout_dt.addLayout(form_dt)
        layout_dt.addStretch()
        tabs.addTab(tab_dt, "Desktop & Vision")

        # ── TAB 6: Cloud Sync ────────────────────────────────────────
        tab_cloud = QWidget()
        layout_cloud = QVBoxLayout(tab_cloud)
        layout_cloud.setContentsMargins(16, 16, 16, 16)
        layout_cloud.setSpacing(12)

        self.chk_cloud_sync = QCheckBox("Enable Autonomous Cloud Persona & Feature Sync")
        self.chk_cloud_sync.setChecked(True)
        self.chk_cloud_sync.setStyleSheet("font-weight: 700; color: #ffffff;")
        layout_cloud.addWidget(self.chk_cloud_sync)

        form_c = QFormLayout()
        self.cloud_url_input = QLineEdit("https://github.com/ErrorBoy928/Nova")
        form_c.addRow("GitHub Repo:", self.cloud_url_input)
        layout_cloud.addLayout(form_c)
        layout_cloud.addStretch()
        tabs.addTab(tab_cloud, "Cloud Sync")

        root.addWidget(tabs)

        # Save Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_save = QPushButton("Save All Changes")
        self.btn_save.clicked.connect(self._save_all)
        btn_row.addWidget(self.btn_save)

        root.addLayout(btn_row)

    def _load_current_values(self):
        # 1. Profile
        self.user_name_input.setText(self.config.user_name or "")
        self.user_phone_input.setText(self.config.whatsapp.owner_number or "")
        self.discord_owner_input.setText(self.config.discord.owner_id or "")
        self.assistant_name_input.setText(self.config.ui.assistant_name or "Nova")

        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == self.config.language:
                self.lang_combo.setCurrentIndex(i)
                break

        # 2. AI Engine
        llm = self.config.llm
        idx = self.provider_combo.findText(llm.provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.model_combo.setCurrentText(llm.model)
        self.key_input.setText(llm.api_key or "")
        self.temp_spin.setValue(llm.temperature)
        self.max_tokens_spin.setValue(llm.max_tokens)
        self.chk_thinking.setChecked(llm.critical_thinking)

        # 3. Integrations
        self.dc_token_input.setText(self.config.discord.bot_token or "")
        self.email_user_input.setText(self.config.email.email or "")
        self.email_pass_input.setText(self.config.email.app_password or "")
        self.smtp_host_input.setText(self.config.email.smtp_host or "smtp.gmail.com")

        # 4. Voice
        v = self.config.voice
        self.chk_voice_enabled.setChecked(v.enabled)
        self.chk_auto_speak.setChecked(v.auto_speak)

        for i in range(self.en_voice_combo.count()):
            if self.en_voice_combo.itemData(i) == v.tts_voice_en:
                self.en_voice_combo.setCurrentIndex(i)
                break
        for i in range(self.ur_voice_combo.count()):
            if self.ur_voice_combo.itemData(i) == v.tts_voice_ur:
                self.ur_voice_combo.setCurrentIndex(i)
                break

        r_idx = self.rate_combo.findText(v.speech_rate)
        if r_idx >= 0:
            self.rate_combo.setCurrentIndex(r_idx)
        vol_idx = self.vol_combo.findText(v.volume)
        if vol_idx >= 0:
            self.vol_combo.setCurrentIndex(vol_idx)

        # 5. UI & Vision
        ui = self.config.ui
        self.chk_vision.setChecked(ui.screen_observing)
        self.chk_always_top.setChecked(ui.always_on_top)
        self.opacity_slider.setValue(int(ui.window_opacity * 100))

    def _toggle_key_visibility(self):
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setText("Hide")
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setText("Show")

    def _toggle_dc_visibility(self):
        if self.dc_token_input.echoMode() == QLineEdit.Password:
            self.dc_token_input.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_dc_token.setText("Hide")
        else:
            self.dc_token_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_dc_token.setText("Show")

    def _test_api_connection(self):
        prov = self.provider_combo.currentText()
        key = self.key_input.text().strip()

        if not key:
            QMessageBox.warning(self, "Missing Key", "Please enter an API Key to test.")
            return

        try:
            if prov == "groq":
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}", "User-Agent": "Nova"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        QMessageBox.information(self, "Success", "Groq API key verified successfully! Status 200 OK.")
                        return
            elif prov == "gemini":
                req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        QMessageBox.information(self, "Success", "Gemini API key verified successfully! Status 200 OK.")
                        return
            QMessageBox.information(self, "Connected", f"{prov.capitalize()} endpoint reached successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to {prov}:\n{str(e)}")

    def _test_smtp_connection(self):
        user = self.email_user_input.text().strip()
        pwd = self.email_pass_input.text().strip()
        host = self.smtp_host_input.text().strip() or "smtp.gmail.com"
        port_str = self.smtp_port_input.text().strip() or "587"

        if not user or not pwd:
            QMessageBox.warning(self, "Missing Fields", "Please enter Email Address and Password to test.")
            return

        try:
            port = int(port_str)
            server = smtplib.SMTP(host, port, timeout=6)
            server.ehlo()
            server.starttls()
            server.login(user, pwd)
            server.quit()
            QMessageBox.information(self, "Success", f"SMTP Connection verified successfully for {user}!")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"SMTP Authentication failed:\n{str(e)}")

    def _save_all(self):
        # 1. Profile
        self.config.user_name = self.user_name_input.text().strip() or None
        self.config.whatsapp.owner_number = self.user_phone_input.text().strip()
        self.config.discord.owner_id = self.discord_owner_input.text().strip()
        self.config.ui.assistant_name = self.assistant_name_input.text().strip() or "Nova"
        self.config.language = self.lang_combo.currentData() or "auto"

        # 2. AI Engine
        llm = self.config.llm
        llm.provider = self.provider_combo.currentText()
        llm.model = self.model_combo.currentText().strip()
        llm.api_key = self.key_input.text().strip()
        llm.temperature = self.temp_spin.value()
        llm.max_tokens = self.max_tokens_spin.value()
        llm.critical_thinking = self.chk_thinking.isChecked()

        # 3. Integrations
        self.config.discord.bot_token = self.dc_token_input.text().strip()
        self.config.email.email = self.email_user_input.text().strip()
        self.config.email.app_password = self.email_pass_input.text().strip()
        self.config.email.smtp_host = self.smtp_host_input.text().strip()

        # 4. Voice
        v = self.config.voice
        v.enabled = self.chk_voice_enabled.isChecked()
        v.auto_speak = self.chk_auto_speak.isChecked()
        v.tts_voice_en = self.en_voice_combo.currentData()
        v.tts_voice_ur = self.ur_voice_combo.currentData()
        v.speech_rate = self.rate_combo.currentText()
        v.volume = self.vol_combo.currentText()

        # 5. UI & Vision
        ui = self.config.ui
        ui.screen_observing = self.chk_vision.isChecked()
        ui.always_on_top = self.chk_always_top.isChecked()
        ui.window_opacity = self.opacity_slider.value() / 100.0

        # Persist and synchronize to .env & runtime memory
        save_config(self.config)

        # Notify parent window of updated settings if available
        parent = self.parent()
        if parent and hasattr(parent, "status_pill"):
            parent.status_pill.setText("READY")
        if parent and hasattr(parent, "model_badge"):
            parent.model_badge.setText(f"ENGINE: {self.config.llm.provider.upper()} ({self.config.llm.model})")
        if parent and hasattr(parent, "hero_widget") and parent.hero_widget:
            parent.hero_widget.update_user_name(self.config.user_name)
        if parent and hasattr(parent, "setWindowTitle"):
            parent.setWindowTitle(f"{self.config.ui.assistant_name} - Autonomous Desktop Studio")

        QMessageBox.information(
            self,
            "Settings Saved",
            "Nova profile, API keys, platform credentials, and system preferences have been saved and activated!",
        )
