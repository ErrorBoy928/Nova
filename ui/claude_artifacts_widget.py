"""
ui/claude_artifacts_widget.py

Claude Artifacts Interactive Live Preview Engine for Nova AI.
Features:
- Dual-view interface: [Live Preview] using Chromium QWebEngineView and [Source Code].
- Instantly renders interactive web apps, Canvas games, dashboards, SVGs, and calculators.
- One-click 'Open in Browser', 'Save to Desktop', and 'Copy Code'.
- Graceful fallback to QTextBrowser if QWebEngineView is unavailable.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_BG_MAIN = "#09090e"
_BG_HEADER = "#111118"
_BORDER = "#1f2430"
_ACCENT_CYAN = "#38bdf8"
_ACCENT_BLUE = "#2563eb"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"


class ClaudeArtifactViewer(QFrame):
    """
    Sleek Claude 3.7-style interactive Artifacts panel.
    Can be docked in sidebar, embedded in chat, or displayed full-height.
    """
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("claude_artifact_viewer")
        self.setStyleSheet(f"""
            QFrame#claude_artifact_viewer {{
                background-color: {_BG_MAIN};
                border: 1px solid {_BORDER};
                border-radius: 10px;
            }}
        """)
        self._current_html = ""
        self._current_code = ""
        self._current_title = "Artifact Preview"
        self._temp_file = None

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── Header Bar ───────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(8)

        # Artifact Badge & Title
        title_box = QHBoxLayout()
        title_box.setSpacing(8)

        badge = QLabel("ARTIFACT")
        badge.setStyleSheet("""
            background-color: #1e1b4b;
            color: #818cf8;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 0.6px;
            padding: 3px 8px;
            border-radius: 5px;
            border: 1px solid #4338ca;
        """)
        title_box.addWidget(badge)

        self.title_lbl = QLabel(self._current_title)
        self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        title_box.addWidget(self.title_lbl)
        header.addLayout(title_box)

        header.addStretch()

        # View Switcher Tabs: [Preview] | [Code]
        tab_box = QHBoxLayout()
        tab_box.setSpacing(2)
        tab_box.setStyleSheet("background: #13131c; border-radius: 6px; padding: 2px;")

        self.btn_tab_preview = QPushButton("Live Preview")
        self.btn_tab_preview.setFixedHeight(26)
        self.btn_tab_preview.setCursor(Qt.PointingHandCursor)
        self.btn_tab_preview.setStyleSheet(self._tab_btn_style(active=True))
        self.btn_tab_preview.clicked.connect(lambda: self._set_active_tab(0))
        tab_box.addWidget(self.btn_tab_preview)

        self.btn_tab_code = QPushButton("Code")
        self.btn_tab_code.setFixedHeight(26)
        self.btn_tab_code.setCursor(Qt.PointingHandCursor)
        self.btn_tab_code.setStyleSheet(self._tab_btn_style(active=False))
        self.btn_tab_code.clicked.connect(lambda: self._set_active_tab(1))
        tab_box.addWidget(self.btn_tab_code)

        header.addLayout(tab_box)

        # Action Buttons
        self.btn_browser = QPushButton("Open in Browser")
        self.btn_browser.setFixedHeight(26)
        self.btn_browser.setCursor(Qt.PointingHandCursor)
        self.btn_browser.setStyleSheet(self._action_btn_style())
        self.btn_browser.clicked.connect(self._open_in_browser)
        header.addWidget(self.btn_browser)

        self.btn_save = QPushButton("Save to Desktop")
        self.btn_save.setFixedHeight(26)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(self._action_btn_style())
        self.btn_save.clicked.connect(self._save_to_desktop)
        header.addWidget(self.btn_save)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setFixedHeight(26)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet(self._action_btn_style())
        self.btn_copy.clicked.connect(self._copy_code)
        header.addWidget(self.btn_copy)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(26, 26)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: #181822;
                color: #94a3b8;
                border: 1px solid #28283a;
                border-radius: 5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #ef4444;
                color: #ffffff;
                border-color: #ef4444;
            }
        """)
        self.btn_close.clicked.connect(self._on_close)
        header.addWidget(self.btn_close)

        root.addLayout(header)

        # ── Stacked View Area ────────────────────────────────────
        self.stack = QStackedWidget()

        # Tab 0: Live WebEngine Preview
        self.preview_container = QWidget()
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self._has_webengine = False
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            self.web_view = QWebEngineView()
            preview_layout.addWidget(self.web_view)
            self._has_webengine = True
        except Exception:
            # Fallback to rich QTextBrowser
            self.web_view = QTextBrowser()
            self.web_view.setOpenExternalLinks(True)
            self.web_view.setStyleSheet(f"background: #0f172a; color: #f8fafc; border: 1px solid {_BORDER}; border-radius: 6px;")
            preview_layout.addWidget(self.web_view)

        self.stack.addWidget(self.preview_container)

        # Tab 1: Source Code Editor
        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setFont(QFont("Consolas", 11))
        self.code_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0b0f19;
                color: #38bdf8;
                border: 1px solid {_BORDER};
                border-radius: 6px;
                padding: 10px;
                selection-background-color: #1e3a8a;
            }}
        """)
        self.stack.addWidget(self.code_edit)

        root.addWidget(self.stack, 1)

    def load_artifact(self, title: str, html_or_code: str, lang: str = "html"):
        """Loads and displays an artifact (HTML, SVG, JS, Python, etc.)."""
        self._current_title = title or "Interactive Artifact"
        self.title_lbl.setText(self._current_title)
        self._current_code = html_or_code
        self.code_edit.setPlainText(html_or_code)

        # Prepare HTML for preview
        is_html = lang.lower() in ("html", "htm", "svg") or ("<html" in html_or_code.lower() or "<!doctype" in html_or_code.lower() or "<svg" in html_or_code.lower())
        if is_html:
            self._current_html = html_or_code
            if "<svg" in html_or_code.lower() and not ("<html" in html_or_code.lower()):
                self._current_html = f"""<!DOCTYPE html><html><body style="background:#09090e;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">{html_or_code}</body></html>"""
        else:
            # Markdown / Text / Code preview wrapper
            self._current_html = f"""<!DOCTYPE html><html><head><style>
                body {{ background: #0b0f19; color: #f8fafc; font-family: -apple-system, sans-serif; padding: 20px; }}
                pre {{ background: #060911; padding: 16px; border-radius: 8px; border: 1px solid #1e293b; color: #38bdf8; font-family: Consolas, monospace; overflow-x: auto; }}
            </style></head><body><h3>{title}</h3><pre><code>{html_or_code}</code></pre></body></html>"""

        if self._has_webengine:
            self.web_view.setHtml(self._current_html)
        else:
            self.web_view.setHtml(self._current_html)

        # Switch to Preview tab
        self._set_active_tab(0 if is_html else 1)
        self.setVisible(True)

    def _set_active_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        self.btn_tab_preview.setStyleSheet(self._tab_btn_style(active=(index == 0)))
        self.btn_tab_code.setStyleSheet(self._tab_btn_style(active=(index == 1)))

    def _open_in_browser(self):
        if not self._current_html:
            return
        tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
        tmp.write(self._current_html)
        tmp.close()
        os.startfile(tmp.name)

    def _save_to_desktop(self):
        desktop = Path.home() / "Desktop"
        clean_title = "".join(c for c in self._current_title if c.isalnum() or c in ("-", "_", " ")).strip() or "Artifact"
        fname = f"{clean_title}.html"
        out_path = desktop / fname
        out_path.write_text(self._current_html or self._current_code, encoding="utf-8")
        self.btn_save.setText("Saved to Desktop!")
        QApplication.processEvents()

    def _copy_code(self):
        QApplication.clipboard().setText(self._current_code)
        self.btn_copy.setText("Copied!")
        QApplication.processEvents()

    def _on_close(self):
        self.setVisible(False)
        self.closed.emit()

    def _tab_btn_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background-color: {_ACCENT_BLUE};
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0 12px;
                }}
            """
        return """
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
                padding: 0 12px;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #1a1a26;
            }
        """

    def _action_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: #181824;
                color: #cbd5e1;
                border: 1px solid {_BORDER};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                background-color: #242436;
                border-color: {_ACCENT_CYAN};
            }}
        """


class ClaudeArtifactCard(QFrame):
    """
    Inline message card displayed in the chat stream when an interactive
    artifact (HTML app, game, dashboard, SVG) is created.
    """
    open_requested = Signal(str, str, str)  # (title, content, lang)

    def __init__(self, title: str, content: str, lang: str = "html", parent=None):
        super().__init__(parent)
        self.title = title or "Interactive Web Artifact"
        self.content = content
        self.lang = lang

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #101018;
                border: 1px solid {_BORDER};
                border-left: 3px solid {_ACCENT_CYAN};
                border-radius: 8px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)
        t_lbl = QLabel(f"Claude Artifact: {self.title}")
        t_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        s_lbl = QLabel(f"Interactive {self.lang.upper()} Application • Ready for live preview")
        s_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        info.addWidget(t_lbl)
        info.addWidget(s_lbl)
        layout.addLayout(info, 1)

        btn_run = QPushButton("▶ Open Live Preview")
        btn_run.setFixedHeight(30)
        btn_run.setCursor(Qt.PointingHandCursor)
        btn_run.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_run.clicked.connect(lambda: self.open_requested.emit(self.title, self.content, self.lang))
        layout.addWidget(btn_run)
