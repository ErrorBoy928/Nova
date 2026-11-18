"""
ui/connections_dialog.py

Executive platform connections dialog for Nova AI.
Embeds the modern Platform Connections Hub view.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout
from config.settings_schema import AppConfig
from ui.connections_view import ConnectionsView


class ConnectionsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Platform Connections Hub - Nova AI")
        self.resize(760, 560)
        self.setStyleSheet("background-color: #08080c;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = ConnectionsView(config, self)
        layout.addWidget(self.view)
