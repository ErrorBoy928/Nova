"""
ui/tasks_dialog.py

Autonomous task management dialog for Nova AI.
Embeds the modern Tasks Hub view.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout
from ui.tasks_view import TasksView


class TasksDialog(QDialog):
    resume_task_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Autonomous Tasks Hub - Nova AI")
        self.resize(780, 580)
        self.setStyleSheet("background-color: #08080c;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = TasksView(self)
        if hasattr(self.view, "resume_task_requested"):
            self.view.resume_task_requested.connect(self.resume_task_requested)
        layout.addWidget(self.view)
