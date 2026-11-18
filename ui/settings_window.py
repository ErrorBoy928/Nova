"""
ui/settings_window.py

Executive master settings dialog for Nova AI.
Embeds the modern Master Settings View.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout
from config.settings_schema import AppConfig
from ui.settings_view import SettingsView


class SettingsWindow(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Master System Settings - Nova AI")
        self.resize(780, 580)
        self.setStyleSheet("background-color: #08080c;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = SettingsView(config, self)
        layout.addWidget(self.view)
