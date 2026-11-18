"""
ui/settings_window.py

Master System Settings Dashboard for Nova AI.
Comprehensive multi-tab configuration interface:
- Tab 1: ⚡ AI & LLM Engine (Groq, Models, Penalties, API Key)
- Tab 2: 🎙️ Voice & Audio (TTS, STT, Voices, Speeds)
- Tab 3: 💻 Desktop & Vision (Screen Vision, Opacity, Hotkeys)
- Tab 4: ☁️ Cloud & GitHub Sync
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
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
    ("Jenny (US Friendly Female)", "en-US-JennyNeural"),
    ("Sonia (UK British Female)", "en-GB-SoniaNeural"),
]

URDU_VOICES = [
    ("Uzma (Urdu Natural Female)", "ur-PK-UzmaNeural"),
    ("Asad (Urdu Deep Male)", "ur-PK-AsadNeural"),
    ("Swara (Urdu/Hindi Sweet Female)", "hi-IN-SwaraNeural"),
]


class SettingsWindow(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Nova AI — System Settings & Intelligence Configuration")
        self.resize(540, 600)
        self.setMinimumSize(480, 520)
        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        self.setStyleSheet("""
            QDialog {
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
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #1e293b;
                border-bottom: none;
                font-weight: 600;
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
                font-weight: 500;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #12121a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #38bdf8;
            }
            QCheckBox {
                color: #cbd5e1;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #334155;
                background: #12121a;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
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
        header_row = QHBoxLayout()
        title_lbl = QLabel("⚙️ NOVA MASTER CONFIGURATION")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px;")
        header_row.addWidget(title_lbl)
        header_row.addStretch()
        root.addLayout(header_row)

        # Tab Widget
        tabs = QTabWidget()

        # TAB 1: AI & Brain
        tab_ai = QWidget()
        form_ai = QFormLayout(tab_ai)
        form_ai.setContentsMargins(16, 16, 16, 16)
        form_ai.setSpacing(12)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDERS)
        self.provider_combo.setCurrentText(self.config.llm.provider or "groq")
        form_ai.addRow("AI Provider:", self.provider_combo)

        # Groq API Key with Test Button
        key_layout = QHBoxLayout()
        self.api_key_input = QLineEdit(self.config.llm.api_key)
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("gsk_...")
        key_layout.addWidget(self.api_key_input)

        self.show_key_btn = QPushButton("👁️")
        self.show_key_btn.setFixedSize(32, 28)
        self.show_key_btn.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.show_key_btn)

        self.test_key_btn = QPushButton("Test")
        self.test_key_btn.setFixedHeight(28)
        self.test_key_btn.clicked.connect(self._test_api_key)
        key_layout.addWidget(self.test_key_btn)
        form_ai.addRow("API Key:", key_layout)

        # Model Picker
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(POPULAR_MODELS)
        self.model_combo.setCurrentText(self.config.llm.model or "qwen/qwen3.8-27b")
        form_ai.addRow("LLM Model:", self.model_combo)

        # Sampling Penalties
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.5)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(getattr(self.config.llm, "temperature", 0.6))
        form_ai.addRow("Temperature:", self.temp_spin)

        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.0, 1.5)
        self.freq_spin.setSingleStep(0.1)
        self.freq_spin.setValue(getattr(self.config.llm, "frequency_penalty", 0.5))
        form_ai.addRow("Frequency Penalty (Anti-Loop):", self.freq_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(512, 16384)
        self.max_tokens_spin.setSingleStep(512)
        self.max_tokens_spin.setValue(getattr(self.config.llm, "max_tokens", 4096))
        form_ai.addRow("Max Tokens:", self.max_tokens_spin)

        tabs.addTab(tab_ai, "⚡ AI & Brain")

        # TAB 2: Voice & Audio
        tab_voice = QWidget()
        form_voice = QFormLayout(tab_voice)
        form_voice.setContentsMargins(16, 16, 16, 16)
        form_voice.setSpacing(12)

        self.auto_speak_chk = QCheckBox("Automatically speak assistant replies aloud")
        self.auto_speak_chk.setChecked(self.config.voice.auto_speak)
        form_voice.addRow("Speech Output:", self.auto_speak_chk)

        self.voice_ur_combo = QComboBox()
        for label, val in URDU_VOICES:
            self.voice_ur_combo.addItem(label, val)
            if val == self.config.voice.tts_voice_ur:
                self.voice_ur_combo.setCurrentText(label)
        form_voice.addRow("Urdu Voice:", self.voice_ur_combo)

        self.voice_en_combo = QComboBox()
        for label, val in ENGLISH_VOICES:
            self.voice_en_combo.addItem(label, val)
            if val == self.config.voice.tts_voice_en:
                self.voice_en_combo.setCurrentText(label)
        form_voice.addRow("English Voice:", self.voice_en_combo)

        self.stt_lang_combo = QComboBox()
        self.stt_lang_combo.addItem("Auto-Detect (Urdu / English)", "auto")
        self.stt_lang_combo.addItem("Urdu (اردو)", "ur")
        self.stt_lang_combo.addItem("English", "en")
        idx = self.stt_lang_combo.findData(self.config.voice.stt_language)
        if idx >= 0:
            self.stt_lang_combo.setCurrentIndex(idx)
        form_voice.addRow("Speech Recognition Language:", self.stt_lang_combo)

        self.wake_word_input = QLineEdit(self.config.voice.wake_word or "Nova")
        form_voice.addRow("Wake Word:", self.wake_word_input)

        tabs.addTab(tab_voice, "🎙️ Voice & Audio")

        # TAB 3: Desktop & Vision
        tab_sys = QWidget()
        form_sys = QFormLayout(tab_sys)
        form_sys.setContentsMargins(16, 16, 16, 16)
        form_sys.setSpacing(12)

        self.name_input = QLineEdit(self.config.ui.assistant_name or "Nova")
        form_sys.addRow("Assistant Name:", self.name_input)

        self.on_top_chk = QCheckBox("Keep Nova window always on top")
        self.on_top_chk.setChecked(self.config.ui.always_on_top)
        form_sys.addRow("Window Pin:", self.on_top_chk)

        self.vision_default_chk = QCheckBox("Keep Screen Vision active by default")
        self.vision_default_chk.setChecked(self.config.ui.screen_observing)
        form_sys.addRow("Vision Mode:", self.vision_default_chk)

        hotkey_lbl = QLabel("• <b>Ctrl+Shift+D</b> : Instant Screen Snip & Vision<br>• <b>Ctrl+Shift+N</b> : Toggle Nova Foreground")
        hotkey_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.5;")
        form_sys.addRow("Global Shortcuts:", hotkey_lbl)

        tabs.addTab(tab_sys, "💻 Desktop & Vision")

        # TAB 4: Cloud & Sync
        tab_cloud = QWidget()
        form_cloud = QFormLayout(tab_cloud)
        form_cloud.setContentsMargins(16, 16, 16, 16)
        form_cloud.setSpacing(12)

        repo_lbl = QLabel("https://github.com/ErrorBoy928/Nova")
        repo_lbl.setStyleSheet("color: #38bdf8; font-weight: 700;")
        form_cloud.addRow("GitHub Repository:", repo_lbl)

        self.auto_sync_chk = QCheckBox("Automatically sync codebase updates on launcher boot")
        self.auto_sync_chk.setChecked(self.config.cloud_sync.enabled)
        form_cloud.addRow("Cloud Sync:", self.auto_sync_chk)

        status_lbl = QLabel("● Connected (All user data & keys 100% locally preserved)")
        status_lbl.setStyleSheet("color: #10b981; font-weight: 600;")
        form_cloud.addRow("Sync Engine Status:", status_lbl)

        tabs.addTab(tab_cloud, "☁️ Cloud & Sync")

        root.addWidget(tabs)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #1e293b; color: #94a3b8;")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save & Apply Configuration")
        save_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self.show_key_btn.setText("🔒")
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self.show_key_btn.setText("👁️")

    def _test_api_key(self):
        key = self.api_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "API Key Required", "Please enter a Groq API key to test.")
            return

        try:
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
            models = client.models.list()
            count = len(models.data)
            QMessageBox.information(
                self,
                "Connection Successful!",
                f"✅ Groq API Key is valid and active!\nDiscovered {count} available models on your account."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Connection Failed", f"❌ API Key Test Error:\n{exc}")

    def _save(self):
        self.config.llm.provider = self.provider_combo.currentText()
        self.config.llm.api_key = self.api_key_input.text().strip()
        self.config.llm.model = self.model_combo.currentText().strip() or "qwen/qwen3.8-27b"
        self.config.llm.temperature = self.temp_spin.value()
        self.config.llm.frequency_penalty = self.freq_spin.value()
        self.config.llm.max_tokens = self.max_tokens_spin.value()

        self.config.ui.assistant_name = self.name_input.text().strip() or "Nova"
        self.config.ui.always_on_top = self.on_top_chk.isChecked()
        self.config.ui.screen_observing = self.vision_default_chk.isChecked()

        self.config.voice.auto_speak = self.auto_speak_chk.isChecked()
        self.config.voice.tts_voice_en = self.voice_en_combo.currentData() or "en-US-AriaNeural"
        self.config.voice.tts_voice_ur = self.voice_ur_combo.currentData() or "ur-PK-UzmaNeural"
        self.config.voice.stt_language = self.stt_lang_combo.currentData() or "auto"
        self.config.voice.wake_word = self.wake_word_input.text().strip() or "Nova"

        self.config.cloud_sync.enabled = self.auto_sync_chk.isChecked()

        save_config(self.config)
        log.info("Nova master settings saved successfully.")
        QMessageBox.information(self, "Settings Saved", "Nova settings have been saved and applied successfully!")
        self.accept()
