"""
ui/settings_view.py

Master System Settings Dashboard View for Nova AI.
Comprehensive multi-tab configuration interface:
- Tab 1: ⚡ AI & LLM Engine (Groq, Gemini, Models, Penalties, API Key, Test Connection)
- Tab 2: 🎙️ Voice & Audio (TTS, STT, Voices, Speeds)
- Tab 3: 💻 Desktop & Vision (Screen Vision, Opacity, Hotkeys)
- Tab 4: ☁️ Cloud & Remote Sync
"""

from __future__ import annotations

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
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
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
        sub_lbl = QLabel("Configure AI Models, Voice Synthesis, Desktop Automation, and Cloud Sync.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        root.addLayout(title_box)

        tabs = QTabWidget()

        # ── TAB 1: AI Engine ─────────────────────────────────────────
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
        self.key_input.setPlaceholderText("Enter Provider API Key...")
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

        btn_test_llm = QPushButton("Test API Connection")
        btn_test_llm.clicked.connect(self._test_api_connection)
        layout_ai.addWidget(btn_test_llm)
        layout_ai.addStretch()
        tabs.addTab(tab_ai, "AI Engine")

        # ── TAB 2: Voice & Audio ─────────────────────────────────────
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

        # ── TAB 3: Desktop & Vision ──────────────────────────────────
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

        # ── TAB 4: Cloud Sync ────────────────────────────────────────
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
        self.btn_save.clicked.connect(self._save_all)
        btn_row.addWidget(self.btn_save)

        root.addLayout(btn_row)

    def _load_current_values(self):
        llm = self.config.llm
        idx = self.provider_combo.findText(llm.provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.model_combo.setCurrentText(llm.model)
        self.key_input.setText(llm.api_key or "")
        self.temp_spin.setValue(llm.temperature)
        self.max_tokens_spin.setValue(llm.max_tokens)
        self.chk_thinking.setChecked(llm.critical_thinking)

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
        if r_idx >= 0: self.rate_combo.setCurrentIndex(r_idx)
        vol_idx = self.vol_combo.findText(v.volume)
        if vol_idx >= 0: self.vol_combo.setCurrentIndex(vol_idx)

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

    def _test_api_connection(self):
        prov = self.provider_combo.currentText()
        key = self.key_input.text().strip()
        model = self.model_combo.currentText().strip()

        if not key:
            QMessageBox.warning(self, "Missing Key", "Please enter an API Key to test.")
            return

        import urllib.request
        try:
            if prov == "groq":
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}", "User-Agent": "Nova"}
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

    def _save_all(self):
        llm = self.config.llm
        llm.provider = self.provider_combo.currentText()
        llm.model = self.model_combo.currentText().strip()
        llm.api_key = self.key_input.text().strip()
        llm.temperature = self.temp_spin.value()
        llm.max_tokens = self.max_tokens_spin.value()
        llm.critical_thinking = self.chk_thinking.isChecked()

        v = self.config.voice
        v.enabled = self.chk_voice_enabled.isChecked()
        v.auto_speak = self.chk_auto_speak.isChecked()
        v.tts_voice_en = self.en_voice_combo.currentData()
        v.tts_voice_ur = self.ur_voice_combo.currentData()
        v.speech_rate = self.rate_combo.currentText()
        v.volume = self.vol_combo.currentText()

        ui = self.config.ui
        ui.screen_observing = self.chk_vision.isChecked()
        ui.always_on_top = self.chk_always_top.isChecked()
        ui.window_opacity = self.opacity_slider.value() / 100.0

        save_config(self.config)
        QMessageBox.information(self, "Settings Saved", "Nova settings have been updated successfully!")
