"""
ui/code_artifacts_dialog.py

Code Artifacts & Scripts Drawer for Nova AI (Ctrl+B).
Provides an executive IDE-like inspector for all code snippets,
scripts, and queries generated across the session with one-click
copy, export, and inline execution.
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QClipboard
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from automation import actions as auto_actions

_BG_MAIN = "#0a0a10"
_BG_CARD = "#111118"
_BORDER = "#1e293b"
_ACCENT_BLUE = "#0284c7"
_ACCENT_CYAN = "#38bdf8"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"


class CodeArtifactsDialog(QDialog):
    def __init__(self, artifacts: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nova AI - Code Artifacts & Scripts Drawer")
        self.setFixedSize(860, 560)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.artifacts = list(artifacts)
        self.current_idx = -1
        self._filter_query = ""

        self._build_ui()
        self._populate_list()

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
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(10)

        # Header
        top_row = QHBoxLayout()
        title_box = QVBoxLayout()
        t_lbl = QLabel("CODE ARTIFACTS & SCRIPTS DRAWER")
        t_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #38bdf8; letter-spacing: 0.8px; font-family: Consolas, monospace;")
        s_lbl = QLabel(f"Catalog of {len(self.artifacts)} generated scripts and code blocks in this session.")
        s_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(t_lbl)
        title_box.addWidget(s_lbl)
        top_row.addLayout(title_box)
        top_row.addStretch()

        close_btn = QPushButton("✕")
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

        # Splitter Layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #1e293b;
                width: 1px;
            }
        """)

        # ── Left Pane: Snippet List ──
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter scripts by title or lang...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #12121a;
                border: 1px solid {_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-size: 11px;
            }}
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: #0c0c14;
                border: 1px solid {_BORDER};
                border-radius: 8px;
                outline: none;
                padding: 4px;
            }}
            QListWidget::item {{
                background: transparent;
                border-radius: 6px;
                padding: 6px 8px;
                margin-bottom: 3px;
                color: #cbd5e1;
            }}
            QListWidget::item:selected {{
                background-color: #16243d;
                color: #ffffff;
                border: 1px solid #38bdf8;
            }}
            QListWidget::item:hover:!selected {{
                background-color: #141420;
            }}
        """)
        self.list_widget.currentRowChanged.connect(self._on_item_selected)
        left_layout.addWidget(self.list_widget)
        splitter.addWidget(left_pane)

        # ── Right Pane: Code Viewer & Controls ──
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(8)

        # Action Bar
        act_bar = QHBoxLayout()
        self.snippet_title_lbl = QLabel("No snippet selected")
        self.snippet_title_lbl.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 700;")
        act_bar.addWidget(self.snippet_title_lbl)

        self.snippet_lang_badge = QLabel("")
        self.snippet_lang_badge.setStyleSheet("background: #0284c7; color: #ffffff; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace;")
        act_bar.addWidget(self.snippet_lang_badge)
        act_bar.addStretch()

        self.run_btn = QPushButton("Run Script")
        self.run_btn.setFixedSize(80, 24)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                color: #6ee7b7;
                border: 1px solid #059669;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #047857;
                color: #ffffff;
            }
        """)
        self.run_btn.clicked.connect(self._run_current_script)
        act_bar.addWidget(self.run_btn)

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setFixedSize(56, 24)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #151520;
                color: #94a3b8;
                border: 1px solid {_BORDER};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #222232;
                color: #ffffff;
            }}
        """)
        self.copy_btn.clicked.connect(self._copy_current_code)
        act_bar.addWidget(self.copy_btn)

        self.save_btn = QPushButton("Save As...")
        self.save_btn.setFixedSize(70, 24)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(self.copy_btn.styleSheet())
        self.save_btn.clicked.connect(self._save_current_code)
        act_bar.addWidget(self.save_btn)

        right_layout.addLayout(act_bar)

        # Code Editor
        self.code_viewer = QTextEdit()
        self.code_viewer.setReadOnly(True)
        self.code_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #08080e;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #e2e8f0;
                font-family: Consolas, 'Fira Code', monospace;
                font-size: 12px;
                line-height: 1.45;
                padding: 10px;
            }
        """)
        right_layout.addWidget(self.code_viewer, 1)

        # Output console frame (hidden until Run is clicked)
        self.console_frame = QFrame()
        self.console_frame.setVisible(False)
        self.console_frame.setStyleSheet("""
            QFrame {
                background-color: #030306;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        cons_vbox = QVBoxLayout(self.console_frame)
        cons_vbox.setContentsMargins(4, 4, 4, 4)
        cons_vbox.setSpacing(4)
        c_hdr = QLabel("EXECUTION OUTPUT:")
        c_hdr.setStyleSheet("color: #64748b; font-size: 9px; font-weight: 800; font-family: Consolas, monospace;")
        cons_vbox.addWidget(c_hdr)
        self.console_lbl = QLabel("")
        self.console_lbl.setWordWrap(True)
        self.console_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.console_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas, monospace;")
        cons_vbox.addWidget(self.console_lbl)
        right_layout.addWidget(self.console_frame)

        splitter.addWidget(right_pane)
        splitter.setSizes([260, 560])

        card_layout.addWidget(splitter, 1)
        root.addWidget(card)

    def _on_search_changed(self, text: str):
        self._filter_query = text.strip().lower()
        self._populate_list()

    def _populate_list(self):
        self.list_widget.clear()
        self._filtered_indices = []

        for idx, art in enumerate(self.artifacts):
            if self._filter_query:
                combined = f"{art.get('title', '')} {art.get('lang', '')} {art.get('code', '')}".lower()
                if self._filter_query not in combined:
                    continue

            self._filtered_indices.append(idx)
            title = art.get("title", f"Script #{art.get('id', idx+1)}")
            lang = art.get("lang", "txt").upper()
            lines = art.get("lines", 1)
            time_str = art.get("time", "")

            item = QListWidgetItem(f"[{lang}] {title} ({lines}L) • {time_str}")
            self.list_widget.addItem(item)

        if self._filtered_indices:
            self.list_widget.setCurrentRow(0)
        else:
            self.snippet_title_lbl.setText("No code artifacts match")
            self.snippet_lang_badge.setText("")
            self.code_viewer.clear()
            self.run_btn.setEnabled(False)

    def _on_item_selected(self, row: int):
        if row < 0 or row >= len(self._filtered_indices):
            return
        orig_idx = self._filtered_indices[row]
        self.current_idx = orig_idx
        art = self.artifacts[orig_idx]

        title = art.get("title", f"Script #{art.get('id', orig_idx+1)}")
        lang = art.get("lang", "txt")
        code = art.get("code", "")

        self.snippet_title_lbl.setText(title)
        self.snippet_lang_badge.setText(lang.upper())
        self.code_viewer.setPlainText(code)

        can_run = lang.lower() in ("python", "py", "powershell", "ps", "ps1", "cmd", "bat", "batch", "node", "js", "javascript")
        self.run_btn.setEnabled(can_run)
        self.console_frame.setVisible(False)

    def _copy_current_code(self):
        code = self.code_viewer.toPlainText()
        if code:
            QApplication.clipboard().setText(code, QClipboard.Clipboard)
            self.copy_btn.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy"))

    def _save_current_code(self):
        if self.current_idx < 0 or self.current_idx >= len(self.artifacts):
            return
        art = self.artifacts[self.current_idx]
        lang = art.get("lang", "txt").lower()
        code = self.code_viewer.toPlainText()

        ext_map = {"python": "py", "py": "py", "javascript": "js", "js": "js", "html": "html", "powershell": "ps1", "ps1": "ps1", "sql": "sql", "json": "json"}
        ext = ext_map.get(lang, "txt")
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Script As", f"script.{ext}", f"Source File (*.{ext});;All Files (*.*)")
        if file_path:
            try:
                Path(file_path).write_text(code, encoding="utf-8")
                self.console_frame.setVisible(True)
                self.console_lbl.setText(f"[OK] Saved to: {file_path}")
                self.console_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas, monospace;")
            except Exception as e:
                self.console_frame.setVisible(True)
                self.console_lbl.setText(f"[ERROR] Save failed: {e}")
                self.console_lbl.setStyleSheet("color: #ef4444; font-size: 11px; font-family: Consolas, monospace;")

    def _run_current_script(self):
        if self.current_idx < 0 or self.current_idx >= len(self.artifacts):
            return
        art = self.artifacts[self.current_idx]
        lang = art.get("lang", "txt").lower()
        code = self.code_viewer.toPlainText()

        self.run_btn.setEnabled(False)
        self.console_frame.setVisible(True)
        self.console_lbl.setText("Running script in background subprocess...")
        self.console_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-family: Consolas, monospace;")

        QTimer.singleShot(80, lambda: self._execute_code(lang, code))

    def _execute_code(self, lang: str, code: str):
        try:
            if lang in ("python", "py"):
                success, out = auto_actions.run_python_code(code)
            elif lang in ("powershell", "ps", "ps1", "cmd", "bat", "batch"):
                success, out = auto_actions.run_powershell(code)
            else:
                success, out = False, f"Unsupported runner runtime for language: {lang}"

            clean_out = out.strip() or "(Process finished with return code 0 and no output)"
            self.console_lbl.setText(clean_out[:400])
            self.console_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas, monospace;" if success else "color: #ef4444; font-size: 11px; font-family: Consolas, monospace;")
        except Exception as e:
            self.console_lbl.setText(f"[Execution Error] {e}")
            self.console_lbl.setStyleSheet("color: #ef4444; font-size: 11px; font-family: Consolas, monospace;")
        finally:
            self.run_btn.setEnabled(True)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
