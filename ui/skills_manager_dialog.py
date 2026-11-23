"""
ui/skills_manager_dialog.py

Antigravity Skills & Customizations Manager Dialog.
Allows users to discover, inspect, test, edit, and create Antigravity skills.
Built with dark obsidian aesthetics (#07070c) and zero emojis.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai.skills_manager import skills_manager
from utils.logger import get_logger

log = get_logger(__name__)


class SkillsManagerDialog(QDialog):
    """Antigravity Skills Manager Dialog."""

    skill_triggered = Signal(str)  # Emits prompt or slash command to inject

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Antigravity Skills & Customizations Manager")
        self.resize(880, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #07070c;
                color: #e2e8f0;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #cbd5e1;
            }
            QLineEdit, QTextEdit {
                background-color: #0d0d16;
                color: #f8fafc;
                border: 1px solid #1e1e2e;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #6366f1;
            }
            QListWidget {
                background-color: #0d0d16;
                color: #cbd5e1;
                border: 1px solid #1e1e2e;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background-color: #1e1e38;
                color: #a5b4fc;
                font-weight: 600;
                border-left: 3px solid #6366f1;
            }
            QListWidget::item:hover:!selected {
                background-color: #121220;
            }
            QPushButton {
                background-color: #1e1e2e;
                color: #e2e8f0;
                border: 1px solid #2d2d3f;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #27273a;
                border-color: #4f46e5;
            }
            QPushButton#primaryBtn {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
            }
            QPushButton#primaryBtn:hover {
                background-color: #4338ca;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: #1e1e2e;
                border-radius: 3px;
            }
        """)

        self._active_skill: dict | None = None
        self._setup_ui()
        self._populate_skills()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Header Bar
        hdr = QHBoxLayout()
        title_lbl = QLabel("ANTIGRAVITY SKILLS & EXTENSIONS")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 800; letter-spacing: 1.5px; color: #a5b4fc;")
        hdr.addWidget(title_lbl)

        hdr.addStretch()

        self.count_badge = QLabel("0 SKILLS")
        self.count_badge.setStyleSheet("background: #1e1e38; color: #818cf8; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; border: 1px solid #312e81;")
        hdr.addWidget(self.count_badge)

        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self._reload_skills)
        hdr.addWidget(reload_btn)

        root_layout.addLayout(hdr)

        # Main Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #1e1e2e; }")

        # Left Column: Search, List, Add
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter skills...")
        self.search_input.textChanged.connect(self._filter_skills)
        left_layout.addWidget(self.search_input)

        self.skills_list = QListWidget()
        self.skills_list.currentRowChanged.connect(self._on_skill_selected)
        left_layout.addWidget(self.skills_list)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("New Skill (+)")
        new_btn.clicked.connect(self._create_new_skill)
        btn_row.addWidget(new_btn)

        open_folder_btn = QPushButton("Open Skills Folder")
        open_folder_btn.clicked.connect(self._open_skills_folder)
        btn_row.addWidget(open_folder_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_widget)

        # Right Column: Detail / Editor View
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

        # Detail Header
        self.detail_name = QLabel("Select a skill to inspect")
        self.detail_name.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        right_layout.addWidget(self.detail_name)

        self.detail_desc = QLineEdit()
        self.detail_desc.setPlaceholderText("Skill description...")
        right_layout.addWidget(self.detail_desc)

        meta_row = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Slash command (e.g. /code)...")
        meta_row.addWidget(self.cmd_input)

        self.keywords_input = QLineEdit()
        self.keywords_input.setPlaceholderText("Keywords (comma-separated)...")
        meta_row.addWidget(self.keywords_input)
        right_layout.addLayout(meta_row)

        instr_lbl = QLabel("INSTRUCTIONS & DIRECTIVES (SKILL.MD)")
        instr_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; letter-spacing: 1px;")
        right_layout.addWidget(instr_lbl)

        self.instructions_edit = QTextEdit()
        self.instructions_edit.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self.instructions_edit)

        # Bottom Action Bar
        act_row = QHBoxLayout()
        self.path_lbl = QLabel("")
        self.path_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-family: Consolas;")
        act_row.addWidget(self.path_lbl)

        act_row.addStretch()

        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save_active_skill)
        act_row.addWidget(save_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        act_row.addWidget(close_btn)

        right_layout.addLayout(act_row)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        root_layout.addWidget(splitter)

    def _populate_skills(self):
        self.skills_list.clear()
        skills = skills_manager.list_skills()
        self.count_badge.setText(f"{len(skills)} SKILLS")

        for s in skills:
            item = QListWidgetItem(f"{s['name']}\n{s['description'][:48]}...")
            item.setData(Qt.UserRole, s["name"])
            self.skills_list.addItem(item)

        if self.skills_list.count() > 0:
            self.skills_list.setCurrentRow(0)

    def _filter_skills(self, text: str):
        text = text.lower().strip()
        for i in range(self.skills_list.count()):
            item = self.skills_list.item(i)
            name = item.data(Qt.UserRole).lower()
            item.setHidden(text != "" and text not in name and text not in item.text().lower())

    def _on_skill_selected(self, row: int):
        if row < 0:
            return
        item = self.skills_list.item(row)
        if not item:
            return
        name = item.data(Qt.UserRole)
        skill = skills_manager.get_skill(name)
        if not skill:
            return

        self._active_skill = skill
        self.detail_name.setText(skill["name"].upper())
        self.detail_desc.setText(skill["description"])
        self.cmd_input.setText(skill["slash_command"])
        self.keywords_input.setText(", ".join(skill["keywords"]))
        self.instructions_edit.setPlainText(skill["instructions"])
        self.path_lbl.setText(skill["path"])

    def _reload_skills(self):
        skills_manager.reload_skills()
        self._populate_skills()

    def _save_active_skill(self):
        if not self._active_skill:
            return
        name = self._active_skill["name"]
        desc = self.detail_desc.text().strip()
        cmd = self.cmd_input.text().strip()
        kws = [k.strip() for k in self.keywords_input.text().split(",") if k.strip()]
        instr = self.instructions_edit.toPlainText().strip()

        skills_manager.create_or_update_skill(
            name=name,
            description=desc,
            instructions=instr,
            slash_command=cmd,
            keywords=kws,
        )
        self._reload_skills()
        QMessageBox.information(self, "Skill Saved", f"Skill '{name}' updated successfully.")

    def _create_new_skill(self):
        default_name = "new-custom-skill"
        counter = 1
        while skills_manager.get_skill(f"{default_name}-{counter}"):
            counter += 1
        name = f"{default_name}-{counter}"

        skills_manager.create_or_update_skill(
            name=name,
            description="Custom user-defined Antigravity skill.",
            instructions="## Directives\n- Define step-by-step instructions for the model.\n",
            slash_command=f"/{name}",
            keywords=["custom", name],
        )
        self._reload_skills()
        # Find and select the new skill
        for i in range(self.skills_list.count()):
            if self.skills_list.item(i).data(Qt.UserRole) == name:
                self.skills_list.setCurrentRow(i)
                break

    def _open_skills_folder(self):
        p = skills_manager.root_dir
        if p.exists():
            subprocess.Popen(["explorer", str(p)])
