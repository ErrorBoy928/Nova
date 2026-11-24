"""
ui/api_key_dialog.py

Dedicated, sleek Obsidian Dark API Key Setup Dialog for Groq.
Allows users to enter, paste, test, and activate their Groq API key with 1 click.
Automatically verifies the key against Groq's high-speed LPU models (Llama 3.3 70B & Llama 3.1 8B).
"""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ai.llm_manager import verify_groq_key
from config.settings_schema import AppConfig, get_api_key, save_config

# Obsidian Palette
_BG_BLACK = "#09090b"
_BG_PANEL = "#111116"
_BG_CARD = "#14141b"
_BORDER = "#22222b"
_ACCENT_BLUE = "#2563eb"
_ACCENT_CYAN = "#38bdf8"
_ACCENT_GREEN = "#10b981"
_ACCENT_RED = "#ef4444"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"


class _KeyVerificationWorker(QThread):
    finished_verify = Signal(bool, str, str)  # (is_valid, message, model)

    def __init__(self, key: str):
        super().__init__()
        self.key = key

    def run(self):
        k = (self.key or "").strip()
        if k.startswith("AIzaSy"):
            from ai.llm_manager import verify_gemini_key
            ok, msg, mod = verify_gemini_key(k)
        elif k.startswith("sk-ant-"):
            from ai.llm_manager import verify_anthropic_key
            ok, msg, mod = verify_anthropic_key(k)
        elif k.startswith("sk-proj-") or (k.startswith("sk-") and not k.startswith("sk-ant-")):
            from ai.llm_manager import verify_openai_key
            ok, msg, mod = verify_openai_key(k)
        else:
            ok, msg, mod = verify_groq_key(k)
        self.finished_verify.emit(ok, msg, mod)


class ApiKeyDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._verify_worker: _KeyVerificationWorker | None = None
        self._tested_working_model: str = ""

        self.setWindowTitle("Groq API Key Setup - Nova AI")
        self.setFixedWidth(520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {_BG_BLACK};
                color: {_TEXT_MAIN};
            }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Title Card
        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        title_lbl = QLabel("Groq API Key (High-Speed Engine)")
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {_TEXT_MAIN}; letter-spacing: 0.5px;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel(
            "Powered by Groq LPUs for extreme speed (300-500 tokens/sec).\n"
            "Runs Qwen 3.8 and Llama 3.3 with near-instant streaming and zero lag."
        )
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {_TEXT_MUTED}; line-height: 1.4;")
        title_box.addWidget(sub_lbl)
        layout.addLayout(title_box)

        # Input Card
        input_card = QFrame()
        input_card.setStyleSheet(f"""
            QFrame {{
                background-color: {_BG_PANEL};
                border: 1px solid {_BORDER};
                border-radius: 8px;
            }}
        """)
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(14, 12, 14, 12)
        input_layout.setSpacing(8)

        lbl_input = QLabel("GROQ API KEY (starts with gsk_):")
        lbl_input.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {_ACCENT_CYAN}; letter-spacing: 0.8px;")
        input_layout.addWidget(lbl_input)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.key_edit = QLineEdit()
        current_key = get_api_key(self.config) or ""
        self.key_edit.setText(current_key)
        self.key_edit.setPlaceholderText("Paste Groq API key here (gsk_...)")
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                color: {_TEXT_MAIN};
                font-family: Consolas, monospace;
                font-size: 12px;
                padding: 6px 10px;
            }}
            QLineEdit:focus {{
                border-color: {_ACCENT_CYAN};
            }}
        """)
        row.addWidget(self.key_edit, 1)

        # Toggle Show / Hide Password
        self.show_btn = QPushButton("Show")
        self.show_btn.setFixedHeight(32)
        self.show_btn.setFixedWidth(52)
        self.show_btn.setCursor(Qt.PointingHandCursor)
        self.show_btn.setToolTip("Show / Hide Key")
        self.show_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                color: {_TEXT_MUTED};
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {_BORDER};
            }}
        """)
        self.show_btn.clicked.connect(self._toggle_echo_mode)
        row.addWidget(self.show_btn)

        # Paste button
        paste_btn = QPushButton("Paste")
        paste_btn.setFixedHeight(32)
        paste_btn.setCursor(Qt.PointingHandCursor)
        paste_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a1a26;
                border: 1px solid #2b2b3d;
                border-radius: 6px;
                color: {_TEXT_MAIN};
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT_CYAN};
                color: #ffffff;
            }}
        """)
        paste_btn.clicked.connect(self._paste_clipboard)
        row.addWidget(paste_btn)

        input_layout.addLayout(row)
        layout.addWidget(input_card)

        # Status / Feedback label
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(f"font-size: 11px; color: {_TEXT_MUTED};")
        layout.addWidget(self.status_lbl)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        get_key_btn = QPushButton("Get Free Groq Key")
        get_key_btn.setFixedHeight(32)
        get_key_btn.setCursor(Qt.PointingHandCursor)
        get_key_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {_BORDER};
                border-radius: 6px;
                color: {_ACCENT_CYAN};
                font-size: 11px;
                font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT_CYAN};
                background-color: #0c1c2e;
            }}
        """)
        get_key_btn.clicked.connect(lambda: webbrowser.open("https://console.groq.com/keys"))
        actions_row.addWidget(get_key_btn)

        self.test_btn = QPushButton("Test Key")
        self.test_btn.setFixedHeight(32)
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #171722;
                border: 1px solid #2e2e42;
                border-radius: 6px;
                color: {_TEXT_MAIN};
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT_CYAN};
                color: #ffffff;
                background-color: #202030;
            }}
        """)
        self.test_btn.clicked.connect(self._test_key)
        actions_row.addWidget(self.test_btn)

        actions_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {_BORDER};
                border-radius: 6px;
                color: {_TEXT_MUTED};
                font-size: 11px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: #404052;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        actions_row.addWidget(cancel_btn)

        self.save_btn = QPushButton("Save & Activate")
        self.save_btn.setFixedHeight(32)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_ACCENT_BLUE};
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-size: 11px;
                font-weight: 700;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: #1d4ed8;
            }}
        """)
        self.save_btn.clicked.connect(self._save_and_activate)
        actions_row.addWidget(self.save_btn)

        layout.addLayout(actions_row)

    def _toggle_echo_mode(self):
        if self.key_edit.echoMode() == QLineEdit.Password:
            self.key_edit.setEchoMode(QLineEdit.Normal)
            self.show_btn.setText("Hide")
        else:
            self.key_edit.setEchoMode(QLineEdit.Password)
            self.show_btn.setText("Show")

    def _paste_clipboard(self):
        clip = QApplication.clipboard().text().strip()
        if clip:
            self.key_edit.setText(clip)
            self._set_status("Pasted key from clipboard. Click 'Test Key' to verify.", _TEXT_MUTED)

    def _set_status(self, text: str, color: str):
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"font-size: 11px; color: {color};")

    def _test_key(self):
        key = self.key_edit.text().strip().strip('"\'')
        if not key:
            self._set_status("Please enter a Groq API key first.", _ACCENT_RED)
            return

        self.test_btn.setEnabled(False)
        self._set_status("Connecting to Groq API...", _ACCENT_CYAN)

        self._verify_worker = _KeyVerificationWorker(key)
        self._verify_worker.finished_verify.connect(self._on_verification_result)
        self._verify_worker.start()

    def _on_verification_result(self, is_valid: bool, message: str, model: str):
        self.test_btn.setEnabled(True)
        if is_valid:
            self._tested_working_model = model
            self._set_status(f"[OK] {message}", _ACCENT_GREEN)
        else:
            self._set_status(f"[ERROR] {message}", _ACCENT_RED)

    def _save_and_activate(self):
        key = self.key_edit.text().strip().strip('"\'')
        if not key:
            self._set_status("Cannot save empty API key.", _ACCENT_RED)
            return

        is_gemini = key.startswith("AIzaSy")
        is_anthropic = key.startswith("sk-ant-")
        is_openai = key.startswith("sk-proj-") or (key.startswith("sk-") and not is_anthropic and not is_gemini)

        if is_gemini:
            self.config.llm.api_key = key
            self.config.llm.provider = "gemini"
            self.config.llm.api_key_env_var = "GEMINI_API_KEY"
            self.config.llm.model = self._tested_working_model or "gemini-2.0-flash"
            env_var = "GEMINI_API_KEY"
        elif is_anthropic:
            self.config.llm.api_key = key
            self.config.llm.provider = "anthropic"
            self.config.llm.api_key_env_var = "ANTHROPIC_API_KEY"
            self.config.llm.model = self._tested_working_model or "claude-3-7-sonnet-20250219"
            env_var = "ANTHROPIC_API_KEY"
        elif is_openai:
            self.config.llm.api_key = key
            self.config.llm.provider = "openai"
            self.config.llm.api_key_env_var = "OPENAI_API_KEY"
            self.config.llm.model = self._tested_working_model or "gpt-4o"
            env_var = "OPENAI_API_KEY"
        else:
            self.config.llm.api_key = key
            self.config.llm.provider = "groq"
            self.config.llm.api_key_env_var = "GROQ_API_KEY"
            if self._tested_working_model:
                self.config.llm.model = self._tested_working_model
            else:
                self.config.llm.model = "qwen/qwen3.8-27b"
            env_var = "GROQ_API_KEY"

        save_config(self.config)

        # 2. Update .env file
        from utils.app_paths import project_root
        env_path = project_root() / ".env"
        try:
            lines = []
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()

            found = False
            new_lines = []
            for line in lines:
                if line.startswith(f"{env_var}="):
                    new_lines.append(f"{env_var}={key}")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"{env_var}={key}")

            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            os.environ[env_var] = key
        except Exception:
            pass

        self.accept()
