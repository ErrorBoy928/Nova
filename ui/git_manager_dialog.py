"""
ui/git_manager_dialog.py

Executive Git Workspace & Repository Manager for Nova AI (Ctrl+G).
Provides real-time branch inspection, changed files overview, git diffs,
commit history, 1-click commit & push to GitHub, and AI analysis handoff.
Runs all git operations with zero flashing console windows via CREATE_NO_WINDOW.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_BG_MAIN = "#07070c"
_BG_CARD = "#0b0b12"
_BG_CONSOLE = "#020205"
_BORDER = "#1e293b"
_ACCENT_BLUE = "#0284c7"
_ACCENT_CYAN = "#38bdf8"
_ACCENT_GREEN = "#10b981"
_ACCENT_RED = "#ef4444"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"

_NO_WINDOW = (
    subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, "CREATE_NO_WINDOW")
    else (0x08000000 if os.name == "nt" else 0)
)


class _GitRefreshWorker(QThread):
    finished = Signal(dict)  # {"branch": str, "status": str, "diff": str, "log": str}

    def __init__(self, cwd: str):
        super().__init__()
        self.cwd = cwd

    def run(self):
        result = {}
        commands = [
            ("branch", ["git", "branch", "--show-current"]),
            ("status", ["git", "status", "--short"]),
            ("diff", ["git", "diff"]),
            ("log", ["git", "log", "-n", "12", "--oneline", "--decorate"]),
        ]
        for key, cmd in commands:
            try:
                p = subprocess.run(
                    cmd,
                    cwd=self.cwd,
                    capture_output=True,
                    text=True,
                    shell=False,
                    creationflags=_NO_WINDOW,
                    timeout=15,
                )
                result[key] = p.stdout or ""
            except Exception as e:
                result[key] = f"Error: {e}"
        self.finished.emit(result)


class _GitActionWorker(QThread):
    finished = Signal(int, str, str)  # (returncode, stdout, stderr)

    def __init__(self, commands: list[list[str]], cwd: str):
        super().__init__()
        self.commands = commands
        self.cwd = cwd

    def run(self):
        last_code = 0
        all_stdout = []
        all_stderr = []
        for cmd in self.commands:
            try:
                p = subprocess.run(
                    cmd,
                    cwd=self.cwd,
                    capture_output=True,
                    text=True,
                    shell=False,
                    creationflags=_NO_WINDOW,
                    timeout=45,
                )
                if p.stdout:
                    all_stdout.append(p.stdout)
                if p.stderr:
                    all_stderr.append(p.stderr)
                last_code = p.returncode
                if last_code != 0 and "nothing to commit" not in (p.stderr or ""):
                    break
            except Exception as e:
                all_stderr.append(str(e))
                last_code = 1
                break
        self.finished.emit(last_code, "\n".join(all_stdout), "\n".join(all_stderr))


class GitManagerDialog(QDialog):
    analyze_requested = Signal(str, str)  # (prompt_type, content)

    def __init__(self, repo_dir: str = "E:\\Nova_AI", parent=None):
        super().__init__(parent)
        self.repo_dir = repo_dir
        self.setWindowTitle("Nova AI - Git Workspace Manager")
        self.setFixedSize(700, 530)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {_BG_MAIN};
                color: {_TEXT_MAIN};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid {_BORDER};
                background: {_BG_CARD};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: #0f172a;
                color: {_TEXT_MUTED};
                border: 1px solid {_BORDER};
                border-bottom: none;
                padding: 6px 14px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: #1e293b;
                color: {_ACCENT_CYAN};
                border-color: #38bdf8;
            }}
        """)

        self._refresh_worker: _GitRefreshWorker | None = None
        self._action_worker: _GitActionWorker | None = None

        self._build_ui()
        self._refresh_git_status()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Header card
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(10)

        icon_lbl = QLabel("GIT")
        icon_lbl.setStyleSheet(f"background: {_ACCENT_BLUE}; color: white; font-weight: 800; font-size: 9px; padding: 2px 7px; border-radius: 4px; font-family: Consolas, monospace;")
        h_layout.addWidget(icon_lbl)

        title_lbl = QLabel("GIT WORKSPACE MANAGER")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #ffffff; letter-spacing: 0.6px; font-family: Consolas, monospace;")
        h_layout.addWidget(title_lbl)

        self.branch_pill = QLabel("branch: detecting...")
        self.branch_pill.setStyleSheet(f"background: #064e3b; color: {_ACCENT_GREEN}; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; border: 1px solid #059669; font-family: Consolas, monospace;")
        h_layout.addWidget(self.branch_pill)

        h_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setFixedHeight(24)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #171720;
                color: {_TEXT_MUTED};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 0 10px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {_ACCENT_CYAN};
            }}
        """)
        self.refresh_btn.clicked.connect(self._refresh_git_status)
        h_layout.addWidget(self.refresh_btn)

        root.addWidget(header)

        # Tabs: Status, Diff, Log
        self.tabs = QTabWidget()

        # TAB 1: Status & Changed Files
        status_tab = QWidget()
        s_layout = QVBoxLayout(status_tab)
        s_layout.setContentsMargins(10, 10, 10, 10)
        s_layout.setSpacing(8)

        self.files_list = QListWidget()
        self.files_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {_BG_CONSOLE};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                color: {_TEXT_MAIN};
                font-family: Consolas, monospace;
                font-size: 11px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 4px 6px;
                border-radius: 4px;
            }}
            QListWidget::item:hover {{
                background-color: #161b26;
            }}
            QListWidget::item:selected {{
                background-color: #1e3a5f;
                color: #ffffff;
            }}
        """)
        s_layout.addWidget(self.files_list)

        # Commit & Push box
        commit_box = QHBoxLayout()
        commit_box.setSpacing(8)

        self.commit_msg_input = QLineEdit()
        self.commit_msg_input.setPlaceholderText("Enter commit message (e.g., feat: optimize database caching)...")
        self.commit_msg_input.setFixedHeight(28)
        self.commit_msg_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0d1117;
                border: 1px solid {_BORDER};
                border-radius: 5px;
                color: #ffffff;
                padding: 0 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {_ACCENT_CYAN};
            }}
        """)
        commit_box.addWidget(self.commit_msg_input, 1)

        self.commit_push_btn = QPushButton("Commit & Push")
        self.commit_push_btn.setCursor(Qt.PointingHandCursor)
        self.commit_push_btn.setFixedHeight(28)
        self.commit_push_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_ACCENT_BLUE};
                color: #ffffff;
                border: 1px solid #0369a1;
                border-radius: 5px;
                padding: 0 14px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #0369a1;
            }}
        """)
        self.commit_push_btn.clicked.connect(self._on_commit_push)
        commit_box.addWidget(self.commit_push_btn)

        self.pull_btn = QPushButton("Pull Remote")
        self.pull_btn.setCursor(Qt.PointingHandCursor)
        self.pull_btn.setFixedHeight(28)
        self.pull_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid {_BORDER};
                border-radius: 5px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT_CYAN};
                color: #ffffff;
            }}
        """)
        self.pull_btn.clicked.connect(self._on_pull)
        commit_box.addWidget(self.pull_btn)

        s_layout.addLayout(commit_box)
        self.tabs.addTab(status_tab, "Changed Files")

        # TAB 2: Uncommitted Diff
        diff_tab = QWidget()
        d_layout = QVBoxLayout(diff_tab)
        d_layout.setContentsMargins(10, 10, 10, 10)
        d_layout.setSpacing(8)

        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {_BG_CONSOLE};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                color: #cbd5e1;
                font-family: Consolas, monospace;
                font-size: 11px;
                line-height: 1.4;
            }}
        """)
        d_layout.addWidget(self.diff_view)

        diff_act_row = QHBoxLayout()
        diff_act_row.addStretch()

        analyze_diff_btn = QPushButton("Analyze Diff in Nova")
        analyze_diff_btn.setCursor(Qt.PointingHandCursor)
        analyze_diff_btn.setFixedHeight(26)
        analyze_diff_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #16243d;
                color: {_ACCENT_CYAN};
                border: 1px solid #1e3a5f;
                border-radius: 5px;
                padding: 0 12px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT_CYAN};
                background-color: #1e3a5f;
            }}
        """)
        analyze_diff_btn.clicked.connect(self._on_analyze_diff)
        diff_act_row.addWidget(analyze_diff_btn)
        d_layout.addLayout(diff_act_row)

        self.tabs.addTab(diff_tab, "Uncommitted Diff")

        # TAB 3: Git Log
        log_tab = QWidget()
        l_layout = QVBoxLayout(log_tab)
        l_layout.setContentsMargins(10, 10, 10, 10)
        l_layout.setSpacing(8)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {_BG_CONSOLE};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                color: #94a3b8;
                font-family: Consolas, monospace;
                font-size: 11px;
                line-height: 1.4;
            }}
        """)
        l_layout.addWidget(self.log_view)
        self.tabs.addTab(log_tab, "Commit History")

        root.addWidget(self.tabs)

        # Status footer bar
        footer = QHBoxLayout()
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-family: Consolas, monospace;")
        footer.addWidget(self.status_lbl)
        footer.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(24)
        close_btn.setStyleSheet(self.refresh_btn.styleSheet())
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _refresh_git_status(self):
        if self._refresh_worker and self._refresh_worker.isRunning():
            return
        self.status_lbl.setText("Inspecting repository status...")
        self._refresh_worker = _GitRefreshWorker(self.repo_dir)

        def _on_refreshed(data: dict):
            # 1. Branch
            branch = data.get("branch", "").strip() or "main"
            self.branch_pill.setText(f"branch: {branch}")

            # 2. Status
            self.files_list.clear()
            raw_status = data.get("status", "")
            lines = [l for l in raw_status.splitlines() if l.strip()]
            if not lines:
                item = QListWidgetItem("Working tree clean — no uncommitted changes.")
                item.setForeground(Qt.darkGreen)
                self.files_list.addItem(item)
            else:
                for line in lines:
                    tag = line[:2].strip()
                    file_name = line[3:].strip()
                    display_text = f"[{tag or '?'}]  {file_name}"
                    item = QListWidgetItem(display_text)
                    if tag in ("M", "MM"):
                        item.setForeground(Qt.cyan)
                    elif tag in ("A", "AM"):
                        item.setForeground(Qt.green)
                    elif tag == "D":
                        item.setForeground(Qt.red)
                    else:
                        item.setForeground(Qt.gray)
                    self.files_list.addItem(item)

            # 3. Diff
            raw_diff = data.get("diff", "").strip()
            self.diff_view.setPlainText(raw_diff if raw_diff else "(No unstaged changes)")

            # 4. Log
            raw_log = data.get("log", "").strip()
            self.log_view.setPlainText(raw_log if raw_log else "(No commits found)")

            self.status_lbl.setText(f"Status refreshed ({len(lines)} uncommitted files)")

        self._refresh_worker.finished.connect(_on_refreshed)
        self._refresh_worker.start()

    def _on_commit_push(self):
        msg = self.commit_msg_input.text().strip()
        if not msg:
            QMessageBox.warning(self, "Commit Message Required", "Please provide a descriptive commit message before committing.")
            self.commit_msg_input.setFocus()
            return

        if self._action_worker and self._action_worker.isRunning():
            return

        self.commit_push_btn.setEnabled(False)
        self.status_lbl.setText("Staging, committing, and pushing to remote origin...")

        commands = [
            ["git", "add", "."],
            ["git", "commit", "-m", msg],
            ["git", "push", "origin", "main"],
        ]
        self._action_worker = _GitActionWorker(commands, self.repo_dir)

        def _on_done(code: int, stdout: str, stderr: str):
            self.commit_push_btn.setEnabled(True)
            if code == 0:
                self.status_lbl.setText("Successfully committed and pushed to remote GitHub!")
                self.commit_msg_input.clear()
                QMessageBox.information(self, "Git Push Successful", "Changes committed and pushed to remote GitHub repository successfully.")
            else:
                self.status_lbl.setText("Git push notice/warning encountered.")
                QMessageBox.warning(self, "Git Notice", f"Execution report:\n{stderr or stdout}")
            self._refresh_git_status()

        self._action_worker.finished.connect(_on_done)
        self._action_worker.start()

    def _on_pull(self):
        if self._action_worker and self._action_worker.isRunning():
            return
        self.pull_btn.setEnabled(False)
        self.status_lbl.setText("Pulling latest code from remote...")

        commands = [["git", "pull", "origin", "main"]]
        self._action_worker = _GitActionWorker(commands, self.repo_dir)

        def _on_done(code: int, stdout: str, stderr: str):
            self.pull_btn.setEnabled(True)
            res = (stdout or stderr).strip()
            self.status_lbl.setText("Pull operation completed.")
            QMessageBox.information(self, "Git Pull", f"Result:\n{res}")
            self._refresh_git_status()

        self._action_worker.finished.connect(_on_done)
        self._action_worker.start()

    def _on_analyze_diff(self):
        diff_text = self.diff_view.toPlainText().strip()
        if not diff_text or diff_text == "(No unstaged changes)":
            QMessageBox.information(self, "No Diff", "There are no unstaged diffs to analyze.")
            return

        prompt = (
            f"Review this git diff and provide an executive summary of changes, potential bugs or edge cases, "
            f"and propose 3 conventional commit message options:\n\n"
            f"```diff\n{diff_text[:3500]}\n```"
        )
        self.analyze_requested.emit("git_diff", prompt)
        self.accept()
