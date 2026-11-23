"""
ui/quick_terminal_dialog.py

Embedded Quick Terminal & PowerShell Runner for Nova AI (Ctrl+T).
Enables instant execution of shell commands, git operations, and
system probes with zero window flickering, command history, and
one-click handoff to Nova for intelligent output analysis.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_BG_MAIN = "#07070c"
_BG_CONSOLE = "#020205"
_BORDER = "#1e293b"
_ACCENT_BLUE = "#0284c7"
_ACCENT_CYAN = "#38bdf8"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"

_NO_WINDOW = (
    subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, "CREATE_NO_WINDOW")
    else (0x08000000 if os.name == "nt" else 0)
)


class _CommandWorker(QThread):
    finished = Signal(int, str, str, float)  # (returncode, stdout, stderr, elapsed_sec)

    def __init__(self, command: str, cwd: str):
        super().__init__()
        self.command = command
        self.cwd = cwd

    def run(self):
        start = time.time()
        try:
            cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", self.command]
            proc = subprocess.run(
                cmd,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                creationflags=_NO_WINDOW,
                timeout=25,
            )
            elapsed = round(time.time() - start, 3)
            self.finished.emit(proc.returncode, proc.stdout or "", proc.stderr or "", elapsed)
        except subprocess.TimeoutExpired:
            self.finished.emit(124, "", "Command timed out after 25 seconds.", round(time.time() - start, 3))
        except Exception as e:
            self.finished.emit(1, "", f"Execution error: {e}", round(time.time() - start, 3))


class QuickTerminalDialog(QDialog):
    analyze_requested = Signal(str, str)  # (command, output)

    def __init__(self, cwd: str = "E:\\Nova_AI", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nova AI - Quick Terminal Runner")
        self.setFixedSize(780, 500)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.cwd = cwd if Path(cwd).exists() else os.getcwd()
        self._history: list[str] = []
        self._history_idx = -1
        self._last_cmd = ""
        self._last_output = ""
        self._worker: _CommandWorker | None = None

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {_BG_MAIN};
                border: 1px solid {_BORDER};
                border-radius: 12px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        # Header
        top_row = QHBoxLayout()
        pill = QLabel("POWERSHELL")
        pill.setStyleSheet("background: #0284c7; color: #ffffff; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace;")
        top_row.addWidget(pill)

        title_lbl = QLabel("EMBEDDED QUICK TERMINAL")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #ffffff; font-family: Consolas, monospace; letter-spacing: 0.8px;")
        top_row.addWidget(title_lbl)

        cwd_lbl = QLabel(f"[{self.cwd}]")
        cwd_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-family: Consolas, monospace;")
        top_row.addWidget(cwd_lbl)
        top_row.addStretch()

        close_btn = QPushButton("X")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #181824;
                color: #94a3b8;
                border: 1px solid #28283a;
                border-radius: 6px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #ef4444;
                color: #ffffff;
                border-color: #ef4444;
            }
        """)
        close_btn.clicked.connect(self.reject)
        top_row.addWidget(close_btn)
        card_layout.addLayout(top_row)

        # Preset Quick Action Chips
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        presets = [
            ("Git Status", "git status"),
            ("Git Log", "git log -n 5 --oneline"),
            ("Top Processes", "Get-Process | Sort-Object CPU -Descending | Select-Object -First 6 Name, CPU, WorkingSet"),
            ("Disk Drives", "Get-PSDrive -PSProvider FileSystem | Select-Object Name, Used, Free"),
            ("IP Config", "Get-NetIPAddress -AddressFamily IPv4 | Select-Object IPAddress, InterfaceAlias"),
            ("Ping Check", "Test-Connection -ComputerName 8.8.8.8 -Count 2"),
        ]
        for label, cmd_text in presets:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(22)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: #12121a;
                    color: {_TEXT_MUTED};
                    border: 1px solid {_BORDER};
                    border-radius: 4px;
                    padding: 0 8px;
                    font-size: 10px;
                    font-weight: 600;
                    font-family: Consolas, monospace;
                }}
                QPushButton:hover {{
                    background-color: #1e293b;
                    color: {_ACCENT_CYAN};
                    border-color: {_ACCENT_CYAN};
                }}
            """)
            b.clicked.connect(lambda _, c=cmd_text: self._run_command(c))
            chips_row.addWidget(b)
        chips_row.addStretch()
        card_layout.addLayout(chips_row)

        # Terminal Monospace Output Area
        self.terminal_out = QTextEdit()
        self.terminal_out.setReadOnly(True)
        self.terminal_out.setStyleSheet(f"""
            QTextEdit {{
                background-color: {_BG_CONSOLE};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                color: #e2e8f0;
                font-family: Consolas, 'Fira Code', monospace;
                font-size: 11px;
                line-height: 1.4;
                padding: 10px;
            }}
        """)
        self.terminal_out.setPlainText(
            f"Nova AI Embedded PowerShell Session [Version 1.0]\n"
            f"Workspace: {self.cwd}\n"
            f"Type any command and press Enter. (Up/Down for history, Esc to close)\n"
            f"--------------------------------------------------------------------\n"
        )
        card_layout.addWidget(self.terminal_out, 1)

        # Input Row
        in_row = QHBoxLayout()
        in_row.setSpacing(8)

        prompt_tag = QLabel("PS >")
        prompt_tag.setStyleSheet("color: #38bdf8; font-weight: 800; font-family: Consolas, monospace; font-size: 12px;")
        in_row.addWidget(prompt_tag)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Enter PowerShell or shell command... (e.g. dir, python --version, git status)")
        self.cmd_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #111118;
                border: 1px solid {_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-family: Consolas, monospace;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {_ACCENT_CYAN};
            }}
        """)
        self.cmd_input.returnPressed.connect(self._on_enter_pressed)
        in_row.addWidget(self.cmd_input, 1)

        self.btn_run = QPushButton("Run")
        self.btn_run.setFixedSize(60, 30)
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_run.clicked.connect(self._on_enter_pressed)
        in_row.addWidget(self.btn_run)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedSize(56, 30)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                background-color: #12121a;
                color: {_TEXT_MUTED};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #222232;
                color: #ffffff;
            }}
        """)
        self.btn_clear.clicked.connect(self._clear_terminal)
        in_row.addWidget(self.btn_clear)

        self.btn_analyze = QPushButton("Analyze in Nova")
        self.btn_analyze.setToolTip("Hand off output to Nova AI for explanation or debugging")
        self.btn_analyze.setFixedHeight(30)
        self.btn_analyze.setCursor(Qt.PointingHandCursor)
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #1e1b4b;
                color: #a5b4fc;
                border: 1px solid #3730a3;
                border-radius: 6px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #312e81;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #12121a;
                color: #475569;
                border-color: #1e293b;
            }
        """)
        self.btn_analyze.clicked.connect(self._analyze_output)
        in_row.addWidget(self.btn_analyze)

        card_layout.addLayout(in_row)
        root.addWidget(card)

    def _on_enter_pressed(self):
        text = self.cmd_input.text().strip()
        if not text:
            return
        self.cmd_input.clear()
        self._run_command(text)

    def _run_command(self, cmd_text: str):
        if self._worker and self._worker.isRunning():
            return

        self._history.append(cmd_text)
        self._history_idx = len(self._history)
        self._last_cmd = cmd_text

        self.btn_run.setEnabled(False)
        self.btn_analyze.setEnabled(False)

        self.terminal_out.append(f"\n<span style='color:#38bdf8;'>PS {self.cwd}&gt;</span> <b>{cmd_text}</b>")
        self.terminal_out.append("<span style='color:#64748b;'>[Executing command...]</span>")
        self.terminal_out.verticalScrollBar().setValue(self.terminal_out.verticalScrollBar().maximum())

        self._worker = _CommandWorker(cmd_text, self.cwd)
        self._worker.finished.connect(self._on_cmd_finished)
        self._worker.start()

    def _on_cmd_finished(self, returncode: int, stdout: str, stderr: str, elapsed: float):
        # Remove "[Executing command...]" line
        cursor = self.terminal_out.textCursor()
        cursor.movePosition(cursor.End)
        self.terminal_out.setTextCursor(cursor)

        full_output = []
        if stdout.strip():
            self.terminal_out.append(f"<pre style='color:#e2e8f0;margin:0;'>{stdout.strip()}</pre>")
            full_output.append(stdout.strip())

        if stderr.strip():
            self.terminal_out.append(f"<pre style='color:#f87171;margin:0;'>{stderr.strip()}</pre>")
            full_output.append(stderr.strip())

        status_color = "#10b981" if returncode == 0 else "#ef4444"
        meta_html = (
            f"<div style='color:{status_color};font-size:10px;margin-top:4px;'>"
            f"[Process exited with code {returncode} in {elapsed}s]</div>"
        )
        self.terminal_out.append(meta_html)
        self.terminal_out.verticalScrollBar().setValue(self.terminal_out.verticalScrollBar().maximum())

        self._last_output = "\n".join(full_output)
        self.btn_run.setEnabled(True)
        self.btn_analyze.setEnabled(bool(self._last_output))
        self.cmd_input.setFocus()

    def _clear_terminal(self):
        self.terminal_out.clear()
        self.terminal_out.setPlainText(
            f"Nova AI Embedded PowerShell Session [Version 1.0]\n"
            f"Workspace: {self.cwd}\n"
            f"--------------------------------------------------------------------\n"
        )
        self.btn_analyze.setEnabled(False)
        self._last_output = ""

    def _analyze_output(self):
        if self._last_output:
            self.analyze_requested.emit(self._last_cmd, self._last_output)
            self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key_Up:
            if self._history and self._history_idx > 0:
                self._history_idx -= 1
                self.cmd_input.setText(self._history[self._history_idx])
            event.accept()
        elif event.key() == Qt.Key_Down:
            if self._history and self._history_idx < len(self._history) - 1:
                self._history_idx += 1
                self.cmd_input.setText(self._history[self._history_idx])
            else:
                self._history_idx = len(self._history)
                self.cmd_input.clear()
            event.accept()
        else:
            super().keyPressEvent(event)
