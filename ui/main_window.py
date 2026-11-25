"""
ui/main_window.py

Full OLED Dark Obsidian AI Desktop Assistant UI & Interactive Coding Suite.
Features:
- Pure Pitch Black Obsidian Theme (#09090b / #111116) with sleek borders.
- Interactive Code Blocks with Language Badges, 1-Click Run Code (Python/Shell/JS),
  1-Click Copy Code, 1-Click Save to File, and Embedded Console Output.
- Real-time Token Streaming (<300ms latency) for lightning-fast responsiveness.
- 1-Click Gemini API Key Dialog with Live Verification & Multi-Model Auto-Fallback.
- Autonomous Computer Control & Coding Engine.
- Live Screen Observing and Multimodal Vision.
- Bilingual natural Urdu and English speech output and recognition.
"""

from __future__ import annotations

import html as html_lib
import re
import ctypes
from datetime import datetime
from pathlib import Path
import time

from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QClipboard,
    QColor,
    QFont,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.tasks_view import TasksView
from ui.connections_view import ConnectionsView
from ui.admin_feed_view import AdminFeedView
from ui.settings_view import SettingsView
from ui.command_palette import CommandPaletteDialog

from ai.image_gen import generate_image
from ai.llm_manager import ChatMessage, LLMError, LLMManager, clean_repetitive_patterns
from automation import executor as automation_executor
from automation.screen_observer import screen_observer, get_open_windows
from config.settings_schema import AppConfig, get_api_key, save_config
import memory.database as db
from ui.api_key_dialog import ApiKeyDialog
from ui.tasks_dialog import TasksDialog
from ui.settings_window import SettingsWindow
from ui.connections_dialog import ConnectionsDialog
from utils import remote_sync
from ui.icons import (
    create_attach_icon,
    create_clean_icon,
    create_copy_icon,
    create_gear_icon,
    create_health_icon,
    create_mic_icon,
    create_moon_icon,
    create_music_icon,
    create_screen_icon,
    create_send_icon,
    create_snip_icon,
    create_speaker_icon,
    create_work_icon,
)
from ui.settings_window import SettingsWindow
from ui.snipping_widget import SnippingWidget
from utils.global_hotkey import GlobalHotkeyThread
from utils.logger import get_logger
from voice.stt import ContinuousVoiceWorker, SingleShotVoiceWorker
from voice.tts import clean_text_for_speech, is_urdu_text, tts

log = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

IMAGE_TAG_RE = re.compile(r"\[Image:\s*(.*?)\]")
_CODE_FENCE_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)

# Elite Modern Dark Obsidian Palette
_BG_BLACK = "#09090b"       # Deep modern obsidian slate (Zinc 950)
_BG_PANEL = "#111116"       # Header & input bar surface
_BG_CARD = "#14141b"        # Elevated assistant card
_BG_USER = "#1a1a24"        # User message card
_BORDER = "#22222b"         # Hairline crisp border
_BORDER_LIGHT = "#2f2f3c"   # Border hover
_BORDER_FOCUS = "#38bdf8"   # Electric cyan border highlight
_ACCENT_BLUE = "#2563eb"    # Primary blue
_ACCENT_CYAN = "#38bdf8"    # Accent cyan
_ACCENT_GREEN = "#10b981"   # Emerald status
_ACCENT_RED = "#ef4444"     # Ruby alert
_TEXT_MAIN = "#f8fafc"      # Primary text
_TEXT_MUTED = "#94a3b8"     # Secondary text
_TEXT_SUBTLE = "#64748b"    # Tertiary text


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


_prev_idle = 0
_prev_kernel = 0
_prev_user = 0


def _get_live_telemetry() -> tuple[int, int, float, float]:
    """Returns (cpu_pct, ram_pct, used_ram_gb, total_ram_gb) in 0.1ms using Win32 API."""
    global _prev_idle, _prev_kernel, _prev_user
    stat = _MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    ram_pct = int(stat.dwMemoryLoad)
    total_ram_gb = round(stat.ullTotalPhys / (1024**3), 1)
    used_ram_gb = round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3), 1)

    idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
    i = (idle.dwHighDateTime << 32) | idle.dwLowDateTime
    k = (kernel.dwHighDateTime << 32) | kernel.dwLowDateTime
    u = (user.dwHighDateTime << 32) | user.dwLowDateTime

    cpu_pct = 0
    if _prev_kernel > 0:
        di = i - _prev_idle
        dk = k - _prev_kernel
        du = u - _prev_user
        total = dk + du
        if total > 0:
            cpu_pct = int(((total - di) * 100) / total)
            cpu_pct = max(min(cpu_pct, 100), 0)

    _prev_idle, _prev_kernel, _prev_user = i, k, u
    return cpu_pct, ram_pct, used_ram_gb, total_ram_gb


class NovaToast(QFrame):
    """
    Sleek executive HUD floating notification overlay.
    Appears smoothly at top-right of MainWindow and auto-dismisses.
    """
    def __init__(self, parent: QWidget, text: str, tag: str = "INFO", duration_ms: int = 2600):
        super().__init__(parent)
        self.setObjectName("novaToast")

        tag_colors = {
            "SUCCESS": ("#10b981", "#059669"),
            "MODEL": ("#0ea5e9", "#0284c7"),
            "SYSTEM": ("#8b5cf6", "#7c3aed"),
            "EXPORT": ("#38bdf8", "#0284c7"),
            "COPIED": ("#10b981", "#059669"),
            "WARNING": ("#f59e0b", "#d97706"),
            "ERROR": ("#f43f5e", "#e11d48"),
            "INFO": ("#94a3b8", "#64748b"),
        }
        accent, border_c = tag_colors.get(tag.upper(), tag_colors["INFO"])

        self.setStyleSheet(f"""
            QFrame#novaToast {{
                background-color: #111118;
                border: 1px solid {border_c};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 14, 7)
        layout.setSpacing(9)

        tag_lbl = QLabel(tag.upper())
        tag_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(255, 255, 255, 0.06);
                color: {accent};
                font-size: 9px;
                font-weight: 800;
                font-family: Consolas, monospace;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid {accent}40;
            }}
        """)
        layout.addWidget(tag_lbl)

        msg_lbl = QLabel(text)
        msg_lbl.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: 500;")
        layout.addWidget(msg_lbl)

        self.adjustSize()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self._timer.start(duration_ms)

    def _dismiss(self):
        self.deleteLater()


class ChatSearchBar(QFrame):
    """
    Sleek in-chat search bar overlay (Ctrl+F).
    Finds keywords in chat bubbles and scrolls smoothly to matches.
    """
    closed = Signal()
    search_changed = Signal(str)
    navigate_next = Signal()
    navigate_prev = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatSearchBar")
        self.setStyleSheet("""
            QFrame#chatSearchBar {
                background-color: #0d0d16;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QLineEdit {
                background: transparent;
                border: none;
                color: #f1f5f9;
                font-size: 11px;
                padding: 3px 6px;
            }
            QPushButton {
                background-color: #161622;
                color: #94a3b8;
                border: 1px solid #222230;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 7px;
            }
            QPushButton:hover {
                background-color: #262638;
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(6)

        search_icon = QLabel("FIND:")
        search_icon.setStyleSheet("color: #38bdf8; font-size: 9px; font-weight: 800; font-family: Consolas, monospace;")
        layout.addWidget(search_icon)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Search conversation... (Enter: next, Esc: close)")
        self.input.textChanged.connect(self._on_text_changed)
        self.input.returnPressed.connect(self.navigate_next.emit)
        layout.addWidget(self.input, 1)

        self.match_lbl = QLabel("")
        self.match_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600;")
        layout.addWidget(self.match_lbl)

        btn_prev = QPushButton("▲")
        btn_prev.setFixedSize(22, 20)
        btn_prev.setToolTip("Previous match")
        btn_prev.clicked.connect(self.navigate_prev.emit)
        layout.addWidget(btn_prev)

        btn_next = QPushButton("▼")
        btn_next.setFixedSize(22, 20)
        btn_next.setToolTip("Next match")
        btn_next.clicked.connect(self.navigate_next.emit)
        layout.addWidget(btn_next)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setToolTip("Close (Esc)")
        btn_close.clicked.connect(self.closed.emit)
        layout.addWidget(btn_close)

    def _on_text_changed(self, text: str):
        self.search_changed.emit(text.strip())

    def set_match_status(self, current: int, total: int):
        if total == 0:
            self.match_lbl.setText("No matches")
            self.match_lbl.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: 600;")
        else:
            self.match_lbl.setText(f"{current} of {total}")
            self.match_lbl.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: 600;")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.closed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


def _format_latex_math(text: str) -> str:
    """Converts LaTeX display ($$...$$) and inline ($...$) formulas into formatted HTML."""
    if not text:
        return text

    def _convert_math_tokens(expr: str) -> str:
        s = expr.strip()
        s = re.sub(
            r"\\frac\{([^{}]+)\}\{([^{}]+)\}",
            r'<span style="display:inline-block;vertical-align:middle;text-align:center;font-size:0.9em;margin:0 2px;"><span style="display:block;border-bottom:1px solid #7dd3fc;padding:0 2px;">\1</span><span style="display:block;padding:0 2px;">\2</span></span>',
            s
        )
        s = re.sub(r"\\sqrt\{([^{}]+)\}", r'√(\1)', s)
        greek = {
            r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
            r"\epsilon": "ε", r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ",
            r"\pi": "π", r"\sigma": "σ", r"\tau": "τ", r"\phi": "φ",
            r"\omega": "ω", r"\Delta": "Δ", r"\Gamma": "Γ", r"\Lambda": "Λ",
            r"\Sigma": "Σ", r"\Omega": "Ω", r"\Theta": "Θ"
        }
        for k, v in greek.items():
            s = s.replace(k, v)
        ops = {
            r"\times": "×", r"\cdot": "·", r"\pm": "±", r"\mp": "∓",
            r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥",
            r"\neq": "≠", r"\approx": "≈", r"\equiv": "≡", r"\infty": "∞",
            r"\sum": "∑", r"\prod": "∏", r"\int": "∫", r"\partial": "∂",
            r"\nabla": "∇", r"\in": "∈", r"\notin": "∉", r"\subset": "⊂",
            r"\cup": "∪", r"\cap": "∩", r"\to": "→", r"\rightarrow": "→",
            r"\leftarrow": "←", r"\Rightarrow": "⇒", r"\forall": "∀", r"\exists": "∃"
        }
        for k, v in ops.items():
            s = s.replace(k, v)
        s = re.sub(r"\^\{([^{}]+)\}", r'<sup>\1</sup>', s)
        s = re.sub(r"\^([a-zA-Z0-9+\-])", r'<sup>\1</sup>', s)
        s = re.sub(r"_\{([^{}]+)\}", r'<sub>\1</sub>', s)
        s = re.sub(r"_([a-zA-Z0-9+\-])", r'<sub>\1</sub>', s)
        return s

    def _replace_display_math(match):
        raw_eq = match.group(1)
        converted = _convert_math_tokens(raw_eq)
        return (
            f'<div style="text-align:center;margin:8px 0;padding:8px 14px;'
            f'background:#070d18;border:1px solid #1e3a5f;border-radius:6px;'
            f'font-family:\'Cambria Math\',\'DejaVu Math TeX Gyre\',Georgia,serif;'
            f'font-size:13px;color:#38bdf8;letter-spacing:0.4px;">'
            f'{converted}</div>'
        )

    text = re.sub(r"\$\$(.+?)\$\$", _replace_display_math, text, flags=re.DOTALL)

    def _replace_inline_math(match):
        raw_eq = match.group(1)
        if re.match(r"^\d+(?:\.\d+)?$", raw_eq.strip()):
            return f"${raw_eq}$"
        converted = _convert_math_tokens(raw_eq)
        return (
            f'<span style="font-family:\'Cambria Math\',\'DejaVu Math TeX Gyre\',Georgia,serif;'
            f'color:#7dd3fc;padding:0 3px;font-size:12px;">'
            f'{converted}</span>'
        )

    text = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", _replace_inline_math, text)
    return text


def _format_inline(text: str) -> str:
    escaped = html_lib.escape(text)
    escaped = _format_latex_math(escaped)
    # Bold: **bold**
    escaped = re.sub(r"\*\*(.+?)\*\*", r'<b style="color:#ffffff;font-weight:700;">\1</b>', escaped)
    # Inline code: `code`
    escaped = re.sub(r"`([^`]+)`", r'<code style="background:#13131c;color:#38bdf8;padding:1px 5px;border-radius:4px;font-family:Consolas,monospace;border:1px solid #1f1f2e;font-size:11px;">\1</code>', escaped)
    # Links: [label](url)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2" style="color:#38bdf8;text-decoration:none;font-weight:600;">\1</a>', escaped)
    # Italic: *italic* or _italic_
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r'<i style="color:#cbd5e1;">\1</i>', escaped)
    return escaped


def _is_table_separator(line: str) -> bool:
    """Checks whether a markdown line is a table delimiter (e.g. |:---|:---:|---:|)."""
    s = line.strip()
    if not s or ("|" not in s and "-" not in s):
        return False
    parts = [p.strip() for p in s.strip("|").split("|")]
    if not parts or not any(parts):
        return False
    return all(bool(re.match(r"^:?-{2,}:?$", p)) for p in parts if p)


def _render_markdown_table(header_line: str, sep_line: str, body_lines: list[str]) -> str:
    """Renders a parsed markdown table into a sleek Obsidian-dark HTML table with zebra striping."""
    sep_parts = [p.strip() for p in sep_line.strip("|").split("|")]
    alignments: list[str] = []
    for p in sep_parts:
        if not p:
            continue
        if p.startswith(":") and p.endswith(":"):
            alignments.append("center")
        elif p.endswith(":"):
            alignments.append("right")
        else:
            alignments.append("left")

    col_count = len(alignments)
    if col_count == 0:
        return ""

    raw_headers = [p.strip() for p in header_line.strip("|").split("|")]
    while len(raw_headers) < col_count:
        raw_headers.append("")
    raw_headers = raw_headers[:col_count]

    th_cells: list[str] = []
    for idx, h in enumerate(raw_headers):
        align = alignments[idx] if idx < len(alignments) else "left"
        th_cells.append(
            f'<th style="padding:7px 12px;font-weight:700;color:#f8fafc;border-right:1px solid #262638;text-align:{align};letter-spacing:0.3px;">{_format_inline(h)}</th>'
        )

    tr_rows: list[str] = []
    for r_idx, r_line in enumerate(body_lines):
        raw_cells = [p.strip() for p in r_line.strip("|").split("|")]
        while len(raw_cells) < col_count:
            raw_cells.append("")
        raw_cells = raw_cells[:col_count]

        bg_color = "#0e0e18" if r_idx % 2 == 0 else "#090912"
        td_cells: list[str] = []
        for c_idx, cell in enumerate(raw_cells):
            align = alignments[c_idx] if c_idx < len(alignments) else "left"
            td_cells.append(
                f'<td style="padding:6px 12px;border-right:1px solid #1a1a28;text-align:{align};color:#e2e8f0;">{_format_inline(cell)}</td>'
            )
        tr_rows.append(f'<tr style="background:{bg_color};border-bottom:1px solid #1a1a28;">{"".join(td_cells)}</tr>')

    return (
        '<div style="overflow-x:auto;margin:8px 0;border-radius:6px;border:1px solid #262638;">'
        '<table style="width:100%;border-collapse:collapse;font-size:12px;background:#0d0d16;line-height:1.5;">'
        '<thead>'
        f'<tr style="background:#161626;border-bottom:2px solid #3b3b55;">{"".join(th_cells)}</tr>'
        '</thead>'
        f'<tbody>{"".join(tr_rows)}</tbody>'
        '</table>'
        '</div>'
    )


def _render_prose(text: str) -> str:
    """High-fidelity executive markdown parser for chat bubbles."""
    if not text or not text.strip():
        return ""

    lines = text.strip().splitlines()
    html_lines: list[str] = []
    in_ul = False
    in_ol = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Markdown Table Detection
        if "|" in stripped and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False

            header_line = stripped
            sep_line = lines[i + 1].strip()
            i += 2
            table_body: list[str] = []
            while i < len(lines):
                row = lines[i].strip()
                if not row or "|" not in row:
                    break
                table_body.append(row)
                i += 1

            html_lines.append(_render_markdown_table(header_line, sep_line, table_body))
            continue

        # Horizontal Rule
        if re.match(r"^(\-{3,}|\_{3,}|\*{3,})$", stripped):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            html_lines.append('<hr style="border:none;border-top:1px solid #22222f;margin:8px 0;">')
            i += 1
            continue

        # Headers
        h1_m = re.match(r"^#\s+(.+)$", stripped)
        h2_m = re.match(r"^##\s+(.+)$", stripped)
        h3_m = re.match(r"^###\s+(.+)$", stripped)
        if h1_m or h2_m or h3_m:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False

            if h1_m:
                h_text = _format_inline(h1_m.group(1))
                html_lines.append(f'<div style="font-size:15px;font-weight:800;color:#ffffff;margin:10px 0 4px 0;padding-bottom:3px;border-bottom:1px solid #22222e;">{h_text}</div>')
            elif h2_m:
                h_text = _format_inline(h2_m.group(1))
                html_lines.append(f'<div style="font-size:13px;font-weight:700;color:#38bdf8;margin:8px 0 3px 0;">{h_text}</div>')
            else:
                h_text = _format_inline(h3_m.group(1))
                html_lines.append(f'<div style="font-size:12px;font-weight:700;color:#e2e8f0;margin:6px 0 2px 0;">{h_text}</div>')
            i += 1
            continue

        # Blockquote
        bq_m = re.match(r"^>\s*(.+)$", stripped)
        if bq_m:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            q_text = _format_inline(bq_m.group(1))
            html_lines.append(f'<div style="border-left:3px solid #6366f1;background:#0c0c16;padding:6px 12px;margin:6px 0;border-radius:0 6px 6px 0;color:#cbd5e1;font-size:12px;line-height:1.5;">{q_text}</div>')
            i += 1
            continue

        # Bullet List (- or * or •)
        ul_m = re.match(r"^[\-\*\•]\s+(.+)$", stripped)
        if ul_m:
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                html_lines.append('<ul style="margin:4px 0;padding-left:18px;list-style-type:square;">')
                in_ul = True
            li_text = _format_inline(ul_m.group(1))
            html_lines.append(f'<li style="margin:3px 0;color:#e2e8f0;line-height:1.55;font-size:13px;">{li_text}</li>')
            i += 1
            continue

        # Numbered List (1. 2. etc.)
        ol_m = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ol_m:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                html_lines.append('<ol style="margin:4px 0;padding-left:20px;">')
                in_ol = True
            li_text = _format_inline(ol_m.group(2))
            html_lines.append(f'<li style="margin:3px 0;color:#e2e8f0;line-height:1.55;font-size:13px;">{li_text}</li>')
            i += 1
            continue

        # Normal paragraph line
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False

        if not stripped:
            html_lines.append('<div style="height:4px;"></div>')
        else:
            p_text = _format_inline(stripped)
            html_lines.append(f'<p style="margin:4px 0;line-height:1.6;color:#e2e8f0;font-size:13px;">{p_text}</p>')
        i += 1

    if in_ul:
        html_lines.append("</ul>")
    if in_ol:
        html_lines.append("</ol>")

    return "".join(html_lines)


def _render_message_html(content: str) -> str:
    pieces: list[str] = []
    last_end = 0
    for m in _CODE_FENCE_RE.finditer(content):
        before = content[last_end:m.start()]
        if before.strip():
            pieces.append(_render_prose(before))
        lang = (m.group(1) or "code").strip()
        code = html_lib.escape(m.group(2).rstrip("\n"))
        pieces.append(
            '<div style="margin:8px 0;border-radius:6px;overflow:hidden;border:1px solid #272733;">'
            f'<div style="background:#13131a;color:#38bdf8;font-size:10px;font-weight:700;'
            'padding:4px 10px;letter-spacing:0.5px;font-family:Consolas,monospace;border-bottom:1px solid #22222d;">'
            f'{lang.upper()}</div>'
            '<pre style="background:#07070a;color:#e2e8f0;padding:10px 12px;margin:0;'
            'font-family:Consolas,monospace;font-size:12px;line-height:1.5;'
            f'white-space:pre-wrap;">{code}</pre></div>'
        )
        last_end = m.end()
    tail = content[last_end:]
    if tail.strip():
        pieces.append(_render_prose(tail))
    return "".join(pieces) if pieces else _render_prose(content)


_MD_IMAGE_RE = re.compile(r"!\[(.*?)\]\((.*?)\)")


def _render_images(html_content: str) -> str:
    def replace_tag(match):
        path_str = match.group(1).strip()
        path = Path(path_str)
        if path.exists():
            return f'<div style="margin:6px 0;"><img src="{path.resolve().as_uri()}" style="border-radius:6px;border:1px solid #2d2d38;max-width:480px;" width="480"></div>'
        return f"[Image: {path_str}]"

    def replace_md_image(match):
        alt = match.group(1).strip()
        url_or_path = match.group(2).strip()
        if url_or_path.startswith("file:///"):
            clean_p = url_or_path[8:]
            p = Path(clean_p)
            if p.exists():
                return f'<div style="margin:6px 0;"><img src="{p.resolve().as_uri()}" alt="{alt}" style="border-radius:6px;border:1px solid #2d2d38;max-width:480px;" width="480"></div>'
        elif Path(url_or_path).exists():
            p = Path(url_or_path)
            return f'<div style="margin:6px 0;"><img src="{p.resolve().as_uri()}" alt="{alt}" style="border-radius:6px;border:1px solid #2d2d38;max-width:480px;" width="480"></div>'
        elif url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            return f'<div style="margin:6px 0;"><img src="{url_or_path}" alt="{alt}" style="border-radius:6px;border:1px solid #2d2d38;max-width:480px;" width="480"></div>'
        return match.group(0)

    res = IMAGE_TAG_RE.sub(replace_tag, html_content)
    res = _MD_IMAGE_RE.sub(replace_md_image, res)
    return res


SYSTEM_PROMPT_TEMPLATE = """
You are {name}, an Elite Senior Full-Stack Software Engineer, Principal Architect, and Autonomous Windows Desktop Assistant (JARVIS-grade).
You serve the user directly, decisively, and respectfully without unnecessary conversation or delay.

CODING EXPERTISE & STANDARDS:
- Mastery in Python, JavaScript, TypeScript, HTML/CSS, React, Vue, Node.js, C, C++, C#, Java, Go, Rust, SQL, Bash, PowerShell.
- Provide clean, production-ready, well-commented code. NEVER write incomplete code or placeholders like '// todo' or '...rest of code...'.
- Always wrap code in markdown code blocks with the exact language identifier (e.g. ```python, ```javascript, ```powershell, ```html, ```sql, ```cpp).
- For Python, write runnable, self-contained code that can execute directly with the user's built-in "Run Code" button.
- If diagnosing bugs or errors, identify the root cause in 1-2 concise sentences and provide the fully corrected code.

FILE & SPREADSHEET CREATION (CRITICAL DIRECT ACTION RULE):
- YOU HAVE FULL AUTONOMOUS CAPABILITY TO CREATE AND WRITE FILES ON THE USER'S COMPUTER.
- When the user asks you to create, make, generate, or export an Excel sheet, spreadsheet, marksheet, budget, invoice, table, or report:
  1. NEVER say "Main directly Excel file create nahi kar sakta" or "I cannot create files directly".
  2. NEVER merely provide code blocks in your chat response when asked to make or create a file!
  3. ALWAYS call [action:create_excel:<filename.xlsx>:<csv_or_table_data>] with complete, realistic rows.
     Example: [action:create_excel:Student_Marksheet.xlsx:Roll No,Student Name,Math,Science,English,Total,Percentage,Grade\n101,Ali Khan,85,90,88,263,87.7,A\n102,Sara Ahmed,92,95,90,277,92.3,A+]
  4. The file will be automatically generated with navy blue headers, borders, and auto-adjusted widths on the user's Desktop, and opened in Excel!
  5. In your chat message, speak directly: confirm that the file has been created on their Desktop.
- When the user asks to create or write scripts, HTML, text files, or programs on their computer:
  * Use [action:create_file:<filename>:<content>] or [action:save_code_file:<filename>:<content>] or [action:run_code:python:<python_code_that_creates_it>].

EMAIL & WEB ACCOUNTS 2FA SHIELD (CRITICAL DIRECT ACTION RULE):
- YOU HAVE FULL ACCESS TO CONNECTED EMAIL SERVICES, 2FA/OTP VERIFICATION CODES, AND WEB ACCOUNTS.
- When the user asks for their login OTP, verification code, or 2FA (e.g. "Google ka OTP kya hai", "GitHub verification code do", "Steam login code check karo"):
  * ALWAYS use [action:get_otp:<service>].
  * Example: [action:get_otp:google] or [action:get_otp:github] or [action:get_otp:steam].
  * If no service is specified, use [action:get_otp].
- When the user asks what web accounts or online platforms are linked or registered to their email (e.g. "is email pe konse accounts hain", "scan connected accounts", "show my web services"):
  * ALWAYS use [action:scan_web_accounts].
- When the user asks to search emails, receipts, or security alerts for a specific service or account:
  * ALWAYS use [action:search_account_emails:<service_or_query>].

LANGUAGE BEHAVIOR & COHERENCE (CRITICAL):
- You are fully fluent in English and natural Pakistani Urdu (اردو) and Roman Urdu.
- Always reply in the exact language or mix used by the user.
- NEVER repeat words, phrases, or syllables in loops (e.g. NEVER output "کیا کیا کیا کیا" or "میں میں میں").
- Always speak in full, coherent, well-structured sentences.
- In Urdu: Speak naturally and politely (e.g. "جی سر، میں نے کوڈ لکھ دیا ہے اور ٹیسٹ کے لیے تیار ہے۔", "جی سر، کام شروع کر دیا ہے۔").
- In Roman Urdu: Speak naturally (e.g. "Ji sir, main aapki files review karne ke liye tayyar hoon.").
- In English: Speak like an advanced assistant ("Right away, sir.", "Here is the production-ready code, sir.", "Executing now, sir.").

SCREEN CONTROL & VISION PROTOCOL (CRITICAL):
1. NEVER open or flash black PowerShell or CMD console windows to perform GUI, app, or web tasks.
2. Check your current screen state context: [Screen Vision: ON] or [Screen Vision: OFF].
3. If [Screen Vision: OFF] and the user asks you to interact with an application, website, button, form, or do work on their screen:
   - DO NOT run blind command-line or PowerShell scripts.
   - Politely ask the user to turn on Screen Share / Screen Vision (or click the 'Turn On Screen Vision' button) so you can see their screen and handle it directly.
   - Always include the tag [action:enable_vision] in your response.
4. If [Screen Vision: ON]:
   - You have real-time visual observation of the user's desktop.
   - Inspect the attached screen image carefully and perform visual computer operations:
     * [action:focus_app:<window_name>] — Brings target window to foreground
     * [action:click_at:<x%,y%>] — Clicks on screen percentage coordinates (e.g. 50,50 for center)
     * [action:click_and_type:<x%,y%>,<text>] — Clicks target input element and types text
     * [action:type_text:<text>] — Types text directly into focused field
     * [action:hotkey:<keys>] — Executes keyboard shortcuts (e.g. ctrl+t, enter, win+r, alt+f4)
     * [action:open_app:<name>] — Opens applications cleanly

AUTONOMOUS AGENT TASK & GOAL SAVING:
When given any multi-step, complex, or large task (e.g. building an application, creating scripts, multi-step desktop workflows, organizing files):
- Automatically save the goal and break it down into clear milestones using:
  [action:save_task:<Task Title>:<Step 1>|<Step 2>|<Step 3>...]
- As steps progress, update them with:
  [action:update_task:<task_id_or_title>:<step_index>]
- The user can view, track, and execute steps anytime via the 'Tasks Hub' button in the sidebar.
- To check existing tasks: [action:list_tasks]

AVAILABLE COMPUTER & CODING ACTIONS:
Embed one or more [action:NAME:ARG] tags when needed:
- [action:create_excel:<filename.xlsx>:<csv_or_data>] — Creates a beautifully formatted Excel (.xlsx) file on Desktop and opens it immediately
- [action:create_pdf:<filename.pdf>:<content>] — Creates a styled, publication-grade PDF report on Desktop
- [action:create_word:<filename.docx>:<content>] — Creates a formatted Microsoft Word (.docx) document on Desktop
- [action:create_presentation:<filename.pptx>:<content>] — Creates a widescreen PowerPoint (.pptx) presentation on Desktop
- [action:generate_image:<prompt>] — Generates a 1024x1024 high-resolution AI image and saves to Desktop
- [action:create_qrcode:<url_or_text>] — Generates a styled QR code image on Desktop
- [action:deep_research:<query>] — Multi-source autonomous deep web research with article synthesis
- [action:optimize_system] — Deep Windows system cleanup (Temp files, DNS flush, RAM trimming)
- [action:remember_fact:<fact>] — Permanently saves user preference or project fact in long-term memory
- [action:list_memory] — Displays all stored user memories
- [action:enable_vision] — Activates Screen Vision and captures current screen
- [action:save_task:<title>:<step1|step2|...>] — Saves structured multi-step agent task
- [action:update_task:<task_id>:<step_num>] — Updates agent task progress
- [action:list_tasks] — Lists all saved agent tasks
- [action:click_at:<x%,y%>] — Clicks at screen coordinates (0-100%)
- [action:click_and_type:<x%,y%>,<text>] — Clicks and types text
- [action:type_text:<text>] — Types text into focused window
- [action:hotkey:<keys>] — Presses shortcut (e.g. ctrl+c, alt+tab, win+d, enter)
- [action:focus_app:<name>] — Brings open app to foreground
- [action:open_app:<name>] — Opens any application or setting (code, notepad, chrome, calc, cmd, powershell, settings)
- [action:close_app:<name>] — Closes an app process or window
- [action:kill_process:<name_or_pid>] — Forcibly terminates program
- [action:run_code:<lang>:<code_snippet>] — Executes Python, PowerShell, Node, or Batch code silently
- [action:save_code_file:<filepath>:<content>] — Saves code directly to a file (defaults to Desktop if relative)
- [action:run_cmd:<command>] — Executes shell command silently without flashing windows
- [action:run_git:<git_args>] — Runs git command (e.g. status, diff, commit -m "msg", log)
- [action:pip_install:<package>] — Installs python package via pip
- [action:routine:<work|relax|clean|status|night>] — Smart routines
- [action:close_window] — Closes current window (Alt+F4)
- [action:snap_window:<left|right|up|down>] — Snaps window
- [action:open_folder:<path>] — Opens project folder in Windows Explorer
- [action:create_file:<filepath:content>] — Creates/writes a file
- [action:append_file:<filepath:content>] — Appends to file
- [action:create_folder:<dirname>] — Creates a folder
- [action:read_file:<filepath>] — Reads text file content
- [action:delete:<path>] — Deletes a file or directory
- [action:zip:<path>] / [action:unzip:<path>]
- [action:list_dir:<path>] — Lists directory contents
- [action:search_files:<query,drive>] — Searches files on E: or C:
- [action:set_volume:<0-100|up|down|mute>] — Controls volume
- [action:set_brightness:<0-100|up|down>] — Controls screen brightness
- [action:media:<play|pause|next|prev|stop>] — Controls media
- [action:clipboard_copy:<text>] / [action:clipboard_read]
- [action:calc:<math_expression>] — Instant offline math
- [action:screenshot] — Takes a desktop screenshot
- [action:empty_recycle_bin] / [action:clear_temp]
- [action:system_stats] — CPU, RAM, and Disk space for C: and E:
- [action:battery] / [action:wifi] / [action:network_info]
- [action:open_url:<url>] / [action:google_search:<query>] / [action:youtube_search:<query>]
- [action:web_search:<query>] — Autonomously searches web and returns research findings
- [action:send_email:<to>:<subject>:<body>] — Sends an email directly via configured email
- [action:check_emails] — Checks and reads recent emails
- [action:get_otp:<service>] — Extracts latest 4-8 digit OTP / 2FA login verification code from email (e.g. Google, GitHub, Steam, Discord, Netflix)
- [action:scan_web_accounts] — Deep-scans user inbox to detect all connected online services, accounts, and platforms registered under this email
- [action:search_account_emails:<service_or_query>] — Searches all emails, receipts, and security alerts for a specific service or account
- [action:schedule_daily:<HH:MM>:<prompt>] — Schedules a daily recurring automated task
- [action:schedule_once:<HH:MM>:<prompt>] — Schedules a one-off task for today
- [action:notify:<title>:<message>] — Pushes notification to Desktop, WhatsApp, and Discord
- [action:generate_image:<prompt>] — Generates AI image

RULES:
1. Always include the exact [action:...] tag when the user asks you to perform an action.
2. For multiple tasks, you can include multiple [action:...] tags sequentially.
3. Reply concisely. Never refuse a coding or computer task.
"""


class _CodeRunnerWorker(QThread):
    finished_run = Signal(bool, str, float)

    def __init__(self, lang: str, code: str):
        super().__init__()
        self.lang = lang
        self.code = code

    def run(self):
        import time
        from automation.actions import run_code
        t0 = time.perf_counter()
        ok, msg = run_code(f"{self.lang}:{self.code}")
        elapsed = time.perf_counter() - t0
        self.finished_run.emit(ok, msg, elapsed)


class ThinkingBlockWidget(QFrame):
    """Collapsible Claude 3.7-style Extended Thinking card."""

    def __init__(self, thinking_text: str):
        super().__init__()
        self.thinking_text = thinking_text.strip()
        self._expanded = False

        self.setStyleSheet("""
            QFrame {
                background-color: #0c0d14;
                border: 1px solid #1e202e;
                border-left: 3px solid #6366f1;
                border-radius: 6px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        self.toggle_btn = QPushButton("▶ Thought Process (Extended Thinking)")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #818cf8;
                font-size: 11px;
                font-weight: 700;
                text-align: left;
                padding: 0;
            }
            QPushButton:hover {
                color: #a5b4fc;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        self.body = QLabel(self.thinking_text)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: Consolas, monospace; line-height: 1.4; padding-top: 4px;")
        self.body.setVisible(False)
        layout.addWidget(self.body)

    def _toggle(self):
        self._expanded = not self._expanded
        self.body.setVisible(self._expanded)
        self.toggle_btn.setText(
            "▼ Thought Process (Extended Thinking)" if self._expanded else "▶ Thought Process (Extended Thinking)"
        )


class _UniversalCodeHighlighter(QSyntaxHighlighter):
    """
    Universal syntax highlighter for multi-language code snippets.
    Supports Python, JavaScript, TypeScript, HTML/CSS, SQL, Bash/PowerShell, JSON, C/C++, Java, Rust.
    """

    def __init__(self, parent_document, lang: str = "code"):
        super().__init__(parent_document)
        self.lang = (lang or "code").lower().strip()
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._init_styles()
        self._compile_rules()

    def _init_styles(self):
        # Keyword format: vibrant purple/indigo (#c084fc), bold
        self.fmt_keyword = QTextCharFormat()
        self.fmt_keyword.setForeground(QColor("#c084fc"))
        self.fmt_keyword.setFontWeight(QFont.Weight.Bold)

        # Builtin / Type format: sky blue (#38bdf8)
        self.fmt_builtin = QTextCharFormat()
        self.fmt_builtin.setForeground(QColor("#38bdf8"))

        # Function / Method format: light blue (#60a5fa)
        self.fmt_function = QTextCharFormat()
        self.fmt_function.setForeground(QColor("#60a5fa"))
        self.fmt_function.setFontWeight(QFont.Weight.DemiBold)

        # String format: vibrant mint/emerald (#4ade80)
        self.fmt_string = QTextCharFormat()
        self.fmt_string.setForeground(QColor("#4ade80"))

        # Number format: orange (#fb923c)
        self.fmt_number = QTextCharFormat()
        self.fmt_number.setForeground(QColor("#fb923c"))

        # Comment format: muted slate (#64748b), italic
        self.fmt_comment = QTextCharFormat()
        self.fmt_comment.setForeground(QColor("#64748b"))
        self.fmt_comment.setFontItalic(True)

        # Special format (decorators, tags, attributes): rose/pink (#f43f5e)
        self.fmt_special = QTextCharFormat()
        self.fmt_special.setForeground(QColor("#f43f5e"))

    def _compile_rules(self):
        # 1. Numbers (decimal, float, hex)
        self._rules.append((re.compile(r"\b(0x[0-9a-fA-F]+|\d+(\.\d+)?([eE][+-]?\d+)?)\b"), self.fmt_number))

        # 2. Keywords per language
        py_keywords = [
            "and", "as", "assert", "async", "await", "break", "class", "continue",
            "def", "del", "elif", "else", "except", "finally", "for", "from",
            "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
            "or", "pass", "raise", "return", "try", "while", "with", "yield"
        ]
        js_keywords = [
            "break", "case", "catch", "class", "const", "continue", "debugger",
            "default", "delete", "do", "else", "export", "extends", "finally",
            "for", "function", "if", "import", "in", "instanceof", "let", "new",
            "return", "super", "switch", "this", "throw", "try", "typeof", "var",
            "void", "while", "with", "yield", "async", "await", "package", "private",
            "protected", "public", "static", "interface", "type", "enum", "from", "as"
        ]
        sql_keywords = [
            "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET",
            "DELETE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "ON",
            "GROUP", "BY", "ORDER", "ASC", "DESC", "HAVING", "LIMIT", "OFFSET",
            "CREATE", "TABLE", "DROP", "ALTER", "ADD", "INDEX", "PRIMARY", "KEY",
            "FOREIGN", "REFERENCES", "AND", "OR", "NOT", "NULL", "IS", "IN", "LIKE",
            "UNION", "ALL", "EXISTS", "BETWEEN", "CASE", "WHEN", "THEN", "ELSE", "END",
            "select", "from", "where", "insert", "into", "values", "update", "set",
            "delete", "join", "left", "right", "inner", "on", "group", "by", "order"
        ]
        sh_keywords = [
            "if", "then", "else", "elif", "fi", "case", "esac", "for", "select",
            "while", "until", "do", "done", "in", "function", "time", "echo",
            "return", "exit", "export", "local", "source", "sudo", "apt", "npm",
            "pip", "python", "git", "node", "pnpm", "yarn", "cargo", "docker"
        ]
        c_keywords = [
            "auto", "break", "case", "char", "const", "continue", "default", "do",
            "double", "else", "enum", "extern", "float", "for", "goto", "if",
            "int", "long", "register", "return", "short", "signed", "sizeof",
            "static", "struct", "switch", "typedef", "union", "unsigned", "void",
            "volatile", "while", "public", "private", "protected", "virtual",
            "override", "template", "typename", "namespace", "using", "std", "fn",
            "mut", "let", "impl", "trait", "pub", "match", "ref", "self", "package"
        ]

        if self.lang in ("python", "py"):
            kw_list = py_keywords
        elif self.lang in ("js", "javascript", "ts", "typescript", "jsx", "tsx", "node", "json"):
            kw_list = js_keywords
        elif self.lang in ("sql",):
            kw_list = sql_keywords
        elif self.lang in ("bash", "sh", "powershell", "ps", "ps1", "cmd", "bat", "batch"):
            kw_list = sh_keywords
        elif self.lang in ("c", "cpp", "h", "hpp", "cs", "java", "rust", "go"):
            kw_list = c_keywords
        else:
            kw_list = list(set(py_keywords + js_keywords + c_keywords))

        if kw_list:
            pattern = r"\b(" + "|".join(kw_list) + r")\b"
            self._rules.append((re.compile(pattern), self.fmt_keyword))

        # 3. Builtins & Types
        builtins = [
            "True", "False", "None", "self", "cls", "true", "false", "null",
            "undefined", "NaN", "Infinity", "print", "len", "range", "str", "int",
            "float", "list", "dict", "set", "tuple", "bool", "type", "isinstance",
            "console", "window", "document", "Math", "JSON", "Array", "Object", "Promise",
            "string", "number", "boolean", "any", "void", "Exception", "ValueError", "TypeError"
        ]
        self._rules.append((re.compile(r"\b(" + "|".join(builtins) + r")\b"), self.fmt_builtin))

        # 4. Function invocations / definitions: word followed by '('
        self._rules.append((re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()"), self.fmt_function))

        # 5. Decorators (@decorator)
        self._rules.append((re.compile(r"@[A-Za-z_][A-Za-z0-9_.]*"), self.fmt_special))

        # 6. HTML / XML tags (<tag ... > or </tag>)
        if self.lang in ("html", "xml", "svg", "vue", "jsx", "tsx"):
            self._rules.append((re.compile(r"</?[a-zA-Z0-9_\-]+(?:\s|>|/)"), self.fmt_special))

        # 7. Strings (quoted)
        self._rules.append((re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\''), self.fmt_string))
        self._rules.append((re.compile(r'"(?:\\.|[^"\\])*"'), self.fmt_string))
        self._rules.append((re.compile(r"'(?:\\.|[^'\\])*'"), self.fmt_string))
        self._rules.append((re.compile(r"`(?:\\.|[^`\\])*`"), self.fmt_string))

        # 8. Comments (top precedence over tokens inside)
        if self.lang in ("python", "py", "bash", "sh", "powershell", "ps", "ps1", "yaml", "yml", "dockerfile"):
            self._rules.append((re.compile(r"#.*$"), self.fmt_comment))
        elif self.lang in ("sql",):
            self._rules.append((re.compile(r"--.*$"), self.fmt_comment))
            self._rules.append((re.compile(r"/\*[\s\S]*?\*/"), self.fmt_comment))
        elif self.lang in ("html", "xml", "svg"):
            self._rules.append((re.compile(r"<!--[\s\S]*?-->"), self.fmt_comment))
        else:
            self._rules.append((re.compile(r"//.*$"), self.fmt_comment))
            self._rules.append((re.compile(r"/\*[\s\S]*?\*/"), self.fmt_comment))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)


class CodeBlockWidget(QFrame):
    """Interactive Code Block card featuring 1-click Run, Copy, Save, and Live Console Output."""

    def __init__(self, lang: str, code: str):
        super().__init__()
        self.lang = (lang or "code").lower()
        self.code = code
        self._runner_worker: _CodeRunnerWorker | None = None
        self._highlighter: _UniversalCodeHighlighter | None = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #07070a;
                border: 1px solid {_BORDER};
                border-radius: 8px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: #101017;
                border-bottom: 1px solid {_BORDER};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 5, 10, 5)
        h_layout.setSpacing(8)

        lang_lbl = QLabel(self.lang.upper())
        lang_lbl.setStyleSheet(f"color: {_ACCENT_CYAN}; font-size: 10px; font-weight: 800; font-family: Consolas, monospace; letter-spacing: 0.8px;")
        h_layout.addWidget(lang_lbl)

        h_layout.addStretch()

        # Claude Live Artifact Preview button (for HTML/SVG/Web apps)
        if self.lang in ("html", "htm", "svg") or ("<html" in self.code.lower() or "<svg" in self.code.lower()):
            self.preview_btn = QPushButton("▶ Artifact Preview")
            self.preview_btn.setFixedHeight(22)
            self.preview_btn.setCursor(Qt.PointingHandCursor)
            self.preview_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e1b4b;
                    color: #a5b4fc;
                    border: 1px solid #4338ca;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 0 8px;
                }
                QPushButton:hover {
                    background-color: #312e81;
                    color: #ffffff;
                }
            """)
            self.preview_btn.clicked.connect(self._on_preview_clicked)
            h_layout.addWidget(self.preview_btn)

        # Run button (for runnable scripts)
        can_run = self.lang in ("python", "py", "powershell", "ps", "ps1", "cmd", "bat", "batch", "node", "js", "javascript")
        if can_run:
            self.run_btn = QPushButton("Run")
            self.run_btn.setFixedHeight(22)
            self.run_btn.setCursor(Qt.PointingHandCursor)
            self.run_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #022c22;
                    color: #6ee7b7;
                    border: 1px solid #065f46;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background-color: #047857;
                    color: #ffffff;
                }}
            """)
            self.run_btn.clicked.connect(self._on_run_clicked)
            h_layout.addWidget(self.run_btn)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(22)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #15151f;
                color: {_TEXT_MUTED};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {_BORDER_LIGHT};
                background-color: #1e1e2c;
            }}
        """)
        save_btn.clicked.connect(self._on_save_clicked)
        h_layout.addWidget(save_btn)

        # 1-Click Desktop Export Button
        self.desktop_btn = QPushButton("Desktop")
        self.desktop_btn.setToolTip("1-Click Instant Save to Desktop")
        self.desktop_btn.setFixedHeight(22)
        self.desktop_btn.setCursor(Qt.PointingHandCursor)
        self.desktop_btn.setStyleSheet(save_btn.styleSheet())
        self.desktop_btn.clicked.connect(self._on_desktop_export_clicked)
        h_layout.addWidget(self.desktop_btn)

        # Copy button
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setFixedHeight(22)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setStyleSheet(save_btn.styleSheet())
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        h_layout.addWidget(self.copy_btn)

        layout.addWidget(header)

        # Code display
        code_edit = QTextEdit()
        code_edit.setPlainText(self.code)
        code_edit.setReadOnly(True)
        self._highlighter = _UniversalCodeHighlighter(code_edit.document(), self.lang)
        line_count = len(self.code.splitlines())
        calc_height = min(max(line_count * 18 + 14, 45), 320)
        code_edit.setFixedHeight(calc_height)
        code_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: #07070a;
                border: none;
                color: #e2e8f0;
                font-family: Consolas, 'Fira Code', monospace;
                font-size: 12px;
                line-height: 1.45;
                padding: 8px 10px;
            }}
        """)
        layout.addWidget(code_edit)

        # Output console area (hidden initially)
        self.console_frame = QFrame()
        self.console_frame.setVisible(False)
        self.console_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #020204;
                border-top: 1px solid {_BORDER};
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
        """)
        cons_layout = QVBoxLayout(self.console_frame)
        cons_layout.setContentsMargins(10, 8, 10, 8)
        cons_layout.setSpacing(4)

        cons_header = QHBoxLayout()
        cons_header.setContentsMargins(0, 0, 0, 2)
        cons_header.setSpacing(6)

        cons_title = QLabel("CONSOLE OUTPUT:")
        cons_title.setStyleSheet("color: #64748b; font-size: 9px; font-weight: 800; font-family: Consolas, monospace;")
        cons_header.addWidget(cons_title)

        self.console_badge = QLabel("")
        self.console_badge.setStyleSheet("color: #38bdf8; font-size: 9px; font-weight: 700; font-family: Consolas, monospace;")
        cons_header.addWidget(self.console_badge)

        cons_header.addStretch()

        self.console_clear_btn = QPushButton("Clear")
        self.console_clear_btn.setFixedHeight(18)
        self.console_clear_btn.setCursor(Qt.PointingHandCursor)
        self.console_clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: 1px solid #1e293b;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 600;
                padding: 0 6px;
            }
            QPushButton:hover {
                color: #e2e8f0;
                border-color: #334155;
                background: #0f172a;
            }
        """)
        self.console_clear_btn.clicked.connect(self._clear_console)
        cons_header.addWidget(self.console_clear_btn)
        cons_layout.addLayout(cons_header)

        self.console_out = QLabel("")
        self.console_out.setWordWrap(True)
        self.console_out.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.console_out.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas, monospace;")
        cons_layout.addWidget(self.console_out)

        layout.addWidget(self.console_frame)

    def _clear_console(self):
        self.console_out.setText("")
        self.console_badge.setText("")
        self.console_frame.setVisible(False)

    def _on_copy_clicked(self):
        QApplication.clipboard().setText(self.code, QClipboard.Clipboard)
        self.copy_btn.setText("✓ Copied!")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                color: #a7f3d0;
                border: 1px solid #10b981;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 0 8px;
            }
        """)
        QTimer.singleShot(1500, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.copy_btn.setText("Copy")
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #15151f;
                color: {_TEXT_MUTED};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {_BORDER_LIGHT};
                background-color: #1e1e2c;
            }}
        """)

    def _on_save_clicked(self):
        ext_map = {
            "python": "py", "py": "py", "javascript": "js", "js": "js",
            "html": "html", "css": "css", "powershell": "ps1", "ps1": "ps1",
            "bash": "sh", "sh": "sh", "sql": "sql", "json": "json",
            "c": "c", "cpp": "cpp", "c++": "cpp", "csharp": "cs", "cs": "cs"
        }
        ext = ext_map.get(self.lang, "txt")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Code Snippet", f"script.{ext}", f"Source File (*.{ext});;All Files (*.*)"
        )
        if file_path:
            try:
                Path(file_path).write_text(self.code, encoding="utf-8")
                self.console_frame.setVisible(True)
                self.console_out.setText(f"[OK] Saved to: {file_path}")
                self.console_out.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas, monospace;")
            except Exception as e:
                self.console_frame.setVisible(True)
                self.console_out.setText(f"[ERROR] Save error: {e}")
                self.console_out.setStyleSheet("color: #ef4444; font-size: 11px; font-family: Consolas, monospace;")

    def _on_desktop_export_clicked(self):
        ext_map = {
            "python": "py", "py": "py", "javascript": "js", "js": "js",
            "typescript": "ts", "ts": "ts", "html": "html", "css": "css",
            "powershell": "ps1", "ps1": "ps1", "bash": "sh", "sh": "sh",
            "sql": "sql", "json": "json", "c": "c", "cpp": "cpp", "c++": "cpp",
            "csharp": "cs", "cs": "cs", "markdown": "md", "md": "md"
        }
        ext = ext_map.get(self.lang, "txt")
        dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        desktop_dir = Path.home() / "Desktop"
        target_path = desktop_dir / f"nova_{self.lang}_{dt_str}.{ext}"
        try:
            target_path.write_text(self.code, encoding="utf-8")
            self.console_frame.setVisible(True)
            self.console_out.setText(f"[OK] 1-Click Exported to Desktop: {target_path.name}")
            self.console_out.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas, monospace;")
            self.desktop_btn.setText("✓ Desktop")
            self.desktop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    color: #a7f3d0;
                    border: 1px solid #10b981;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 0 8px;
                }
            """)
            QTimer.singleShot(1800, self._reset_desktop_btn)
        except Exception as e:
            self.console_frame.setVisible(True)
            self.console_out.setText(f"[ERROR] Desktop export error: {e}")
            self.console_out.setStyleSheet("color: #ef4444; font-size: 11px; font-family: Consolas, monospace;")

    def _reset_desktop_btn(self):
        self.desktop_btn.setText("Desktop")
        self.desktop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #15151f;
                color: {_TEXT_MUTED};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {_BORDER_LIGHT};
                background-color: #1e1e2c;
            }}
        """)

    def _on_run_clicked(self):
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.console_frame.setVisible(True)
        self.console_out.setText("Executing code in background...")
        self.console_out.setStyleSheet("color: #38bdf8; font-size: 11px; font-family: Consolas, monospace;")

        self._runner_worker = _CodeRunnerWorker(self.lang, self.code)
        self._runner_worker.finished_run.connect(self._on_run_completed)
        self._runner_worker.start()

    def _on_run_completed(self, success: bool, output: str, elapsed: float = 0.0):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run")
        if success:
            badge_text = f"[SUCCESS • {elapsed:.2f}s]"
            badge_color = "#10b981"
        else:
            badge_text = f"[EXIT CODE 1 • {elapsed:.2f}s]"
            badge_color = "#ef4444"
        if hasattr(self, "console_badge"):
            self.console_badge.setStyleSheet(f"color: {badge_color}; font-size: 9px; font-weight: 700; font-family: Consolas, monospace;")
            self.console_badge.setText(badge_text)
        self.console_out.setStyleSheet(f"color: {badge_color}; font-size: 11px; font-family: Consolas, monospace;")
        self.console_out.setText(output)

    def _on_preview_clicked(self):
        top = self.window()
        if hasattr(top, "open_claude_artifact"):
            top.open_claude_artifact("Interactive Web App", self.code, self.lang)
        else:
            import tempfile, os
            tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
            tmp.write(self.code)
            tmp.close()
            os.startfile(tmp.name)


class _LLMWorker(QThread):
    chunk_received = Signal(str)
    reply_ready = Signal(str, float)
    failed = Signal(str)

    def __init__(self, manager: LLMManager, history: list[ChatMessage], system_prompt: str):
        super().__init__()
        self.manager = manager
        self.history = history
        self.system_prompt = system_prompt
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        start_time = time.time()
        try:
            chunks = []
            for chunk in self.manager.chat_stream(self.history, system_prompt=self.system_prompt):
                if self._cancelled:
                    break
                chunks.append(chunk)
                self.chunk_received.emit(chunk)
            full_reply = "".join(chunks)
            elapsed = time.time() - start_time
            if not self._cancelled:
                self.reply_ready.emit(full_reply, elapsed)
        except LLMError as exc:
            if not self._cancelled:
                self.failed.emit(str(exc))
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(f"Error: {exc}")


def _generate_chat_html(recent: list[dict], model_name: str) -> str:
    now_str = datetime.now().strftime("%B %d, %Y - %I:%M %p")
    items_html = []
    for msg in recent:
        is_user = msg.get("role") == "user"
        sender = "Commander" if is_user else "Nova AI Assistant"
        bg_col = "#111827" if is_user else "#0f172a"
        border_col = "#1f2937" if is_user else "#1e3a8a"
        badge_col = "#38bdf8" if not is_user else "#94a3b8"
        raw_content = msg.get("content", "")
        formatted = html_lib.escape(raw_content)
        formatted = re.sub(r"```(\w+)?\n?(.*?)```", r'<pre style="background:#090d16;padding:12px;border-radius:6px;border:1px solid #1e293b;overflow-x:auto;color:#38bdf8;font-family:Consolas,monospace;font-size:12px;"><code>\2</code></pre>', formatted, flags=re.DOTALL)
        formatted = re.sub(r"`([^`]+)`", r'<code style="background:#1e293b;color:#38bdf8;padding:2px 5px;border-radius:4px;font-family:Consolas,monospace;font-size:11px;">\1</code>', formatted)
        formatted = formatted.replace("\n", "<br>")

        items_html.append(f"""
        <div style="margin-bottom:16px;background:{bg_col};border:1px solid {border_col};border-radius:10px;padding:14px 18px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{badge_col};"></span>
                <span style="font-weight:700;font-size:12px;color:{badge_col};letter-spacing:0.5px;">{sender.upper()}</span>
            </div>
            <div style="color:#e2e8f0;font-size:13px;line-height:1.6;">{formatted}</div>
        </div>
        """)

    body_content = "\n".join(items_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nova AI - Executive Conversation Log</title>
<style>
  body {{ background-color: #06060a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 30px; display: flex; justify-content: center; }}
  .container {{ max-width: 860px; width: 100%; }}
  .header {{ border-bottom: 1px solid #1e293b; padding-bottom: 20px; margin-bottom: 24px; }}
  .title {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px; margin: 0; }}
  .meta {{ color: #94a3b8; font-size: 11px; margin-top: 6px; font-family: Consolas, monospace; }}
  @media print {{ body {{ background: #fff; color: #000; }} }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="title">NOVA AI — AUTONOMOUS CONVERSATION LOG</div>
    <div class="meta">Generated: {now_str} • Model Engine: {model_name} • Total Records: {len(recent)}</div>
  </div>
  {body_content}
</div>
</body>
</html>"""


class _ExecutionPlanWidget(QFrame):
    """
    Unified Autonomous Execution Pipeline Card.
    Displays live step-by-step progress with status badges, elapsed time, and completion report.
    """
    def __init__(self, steps: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.steps = steps
        self._start_time = time.time()
        self.setObjectName("executionPlanWidget")
        self.setStyleSheet("""
            QFrame#executionPlanWidget {
                background-color: #0c0c14;
                border: 1px solid #1e293b;
                border-radius: 10px;
                margin: 4px 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        pill = QLabel("PLAN")
        pill.setStyleSheet("background: #0284c7; color: #ffffff; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace;")
        hdr.addWidget(pill)

        title = QLabel(f"AUTONOMOUS AGENT PIPELINE ({len(steps)} Steps)")
        title.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700; letter-spacing: 0.6px;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.time_lbl = QLabel("Executing...")
        self.time_lbl.setStyleSheet("color: #38bdf8; font-size: 10px; font-family: Consolas, monospace;")
        hdr.addWidget(self.time_lbl)
        layout.addLayout(hdr)

        # Progress bar
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(3)
        self.pbar.setTextVisible(False)
        self.pbar.setRange(0, len(steps))
        self.pbar.setValue(0)
        self.pbar.setStyleSheet("QProgressBar { background: #161622; border-radius: 1px; } QProgressBar::chunk { background: #0284c7; border-radius: 1px; }")
        layout.addWidget(self.pbar)

        # Step rows
        self.row_labels: list[tuple[QLabel, QLabel]] = []
        for idx, (act_name, arg) in enumerate(steps, 1):
            row = QHBoxLayout()
            row.setSpacing(8)

            badge = QLabel("PENDING")
            badge.setFixedWidth(64)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet("background: #181824; color: #64748b; font-size: 9px; font-weight: 700; padding: 2px 4px; border-radius: 4px; border: 1px solid #242436;")
            row.addWidget(badge)

            short_arg = (arg[:60] + "...") if len(arg) > 60 else arg
            step_text = f"Step {idx}: [{act_name}] {short_arg}" if short_arg else f"Step {idx}: [{act_name}]"
            step_lbl = QLabel(step_text)
            step_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
            row.addWidget(step_lbl)
            row.addStretch()

            layout.addLayout(row)
            self.row_labels.append((badge, step_lbl))

    def mark_step_result(self, step_idx: int, success: bool, msg: str):
        if 0 <= step_idx < len(self.row_labels):
            badge, lbl = self.row_labels[step_idx]
            if success:
                badge.setText("DONE")
                badge.setStyleSheet("background: #064e3b; color: #6ee7b7; font-size: 9px; font-weight: 800; padding: 2px 4px; border-radius: 4px; border: 1px solid #059669;")
            else:
                badge.setText("FAILED")
                badge.setStyleSheet("background: #450a0a; color: #fca5a5; font-size: 9px; font-weight: 800; padding: 2px 4px; border-radius: 4px; border: 1px solid #991b1b;")
            if msg:
                clean_msg = msg.splitlines()[0] if msg else ""
                lbl.setText(f"{lbl.text().split(' -> ')[0]} -> {clean_msg[:65]}")
            self.pbar.setValue(step_idx + 1)

    def finalize(self, all_ok: bool):
        elapsed = round(time.time() - self._start_time, 2)
        status_txt = "Completed" if all_ok else "Finished with warnings"
        self.time_lbl.setText(f"{status_txt} in {elapsed}s")
        color = "#10b981" if all_ok else "#f59e0b"
        self.time_lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 700; font-family: Consolas, monospace;")
        self.pbar.setStyleSheet(f"QProgressBar {{ background: #161622; border-radius: 1px; }} QProgressBar::chunk {{ background: {color}; border-radius: 1px; }}")


class _SuperAgentFeedWidget(QFrame):
    """
    Real-time Autonomous Super Agent ReAct HUD Widget.
    Displays live Thought stream, active actions, auto-correction loop, and completion status.
    """
    def __init__(self, goal: str, max_iterations: int = 8, parent=None):
        super().__init__(parent)
        self.goal = goal
        self.max_iterations = max_iterations
        self._start_time = time.time()
        self.setObjectName("superAgentFeed")
        self.setStyleSheet("""
            QFrame#superAgentFeed {
                background-color: #070712;
                border: 1px solid #4338ca;
                border-radius: 10px;
                margin: 4px 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        pill = QLabel("SUPERAGENT")
        pill.setStyleSheet("background: #4f46e5; color: #ffffff; font-size: 9px; font-weight: 800; padding: 2px 7px; border-radius: 4px; font-family: Consolas, monospace;")
        hdr.addWidget(pill)

        title = QLabel(f"AUTONOMOUS ReAct EXECUTION (Max {max_iterations} Iterations)")
        title.setStyleSheet("color: #e0e7ff; font-size: 11px; font-weight: 700; letter-spacing: 0.6px;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.iter_lbl = QLabel("Iteration 1/8")
        self.iter_lbl.setStyleSheet("color: #a5b4fc; font-size: 10px; font-weight: 700; font-family: Consolas, monospace;")
        hdr.addWidget(self.iter_lbl)
        layout.addLayout(hdr)

        # Progress bar
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(3)
        self.pbar.setTextVisible(False)
        self.pbar.setRange(0, max_iterations)
        self.pbar.setValue(1)
        self.pbar.setStyleSheet("QProgressBar { background: #161622; border-radius: 1px; } QProgressBar::chunk { background: #6366f1; border-radius: 1px; }")
        layout.addWidget(self.pbar)

        # Active Thought Box
        self.thought_box = QLabel("Initializing autonomous loop and analyzing objective...")
        self.thought_box.setWordWrap(True)
        self.thought_box.setStyleSheet("background: #0f1026; color: #cbd5e1; border: 1px solid #282b52; border-radius: 6px; padding: 6px 10px; font-size: 11px; font-family: Consolas, monospace;")
        layout.addWidget(self.thought_box)

        # Actions Container
        self.actions_layout = QVBoxLayout()
        self.actions_layout.setSpacing(4)
        layout.addLayout(self.actions_layout)

    def set_thought(self, iteration: int, thought: str):
        self.iter_lbl.setText(f"Iteration {iteration}/{self.max_iterations}")
        self.pbar.setValue(iteration)
        self.thought_box.setText(f"Thought: {thought}")

    def add_action_result(self, iteration: int, act_name: str, success: bool, output: str):
        row = QHBoxLayout()
        row.setSpacing(6)

        tag = QLabel("DONE" if success else "FAIL")
        tag.setFixedWidth(52)
        tag.setAlignment(Qt.AlignCenter)
        tag_bg = "#064e3b" if success else "#450a0a"
        tag_color = "#6ee7b7" if success else "#fca5a5"
        tag_border = "#059669" if success else "#991b1b"
        tag.setStyleSheet(f"background: {tag_bg}; color: {tag_color}; font-size: 9px; font-weight: 800; padding: 2px; border-radius: 4px; border: 1px solid {tag_border}; font-family: Consolas, monospace;")
        row.addWidget(tag)

        clean_out = output.splitlines()[0][:70] if output else "Executed"
        desc = QLabel(f"[{act_name}] {clean_out}")
        desc.setStyleSheet("color: #94a3b8; font-size: 10px; font-family: Consolas, monospace;")
        row.addWidget(desc)
        row.addStretch()

        self.actions_layout.addLayout(row)

    def finalize(self, all_ok: bool, summary: str):
        elapsed = round(time.time() - self._start_time, 2)
        status_txt = "Goal Achieved" if all_ok else "Finished"
        self.iter_lbl.setText(f"{status_txt} ({elapsed}s)")
        color = "#10b981" if all_ok else "#f59e0b"
        self.iter_lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 800; font-family: Consolas, monospace;")
        self.pbar.setValue(self.max_iterations)
        self.pbar.setStyleSheet(f"QProgressBar {{ background: #161622; border-radius: 1px; }} QProgressBar::chunk {{ background: {color}; border-radius: 1px; }}")
        self.thought_box.setText(f"Summary: {summary[:120]}")


class _AntigravityStepsWidget(QFrame):
    """
    Antigravity Live Execution Steps & Focus Tracker HUD.
    Displays high-level focus headline and dynamic multi-step checklist
    with live status badges (in_progress, done, pending, failed, skipped).
    """
    def __init__(self, initial_focus: str = "", steps: list[dict] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("antigravitySteps")
        self.setStyleSheet("""
            QFrame#antigravitySteps {
                background-color: #06060e;
                border: 1px solid #312e81;
                border-radius: 9px;
                margin: 4px 6px;
            }
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 10)
        self._layout.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        pill = QLabel("ANTIGRAVITY STEPS")
        pill.setStyleSheet("background: #312e81; color: #a5b4fc; font-size: 9px; font-weight: 800; padding: 2px 7px; border-radius: 4px; font-family: Consolas, monospace;")
        hdr.addWidget(pill)

        self.focus_lbl = QLabel(initial_focus or "Orchestrating multi-step workflow...")
        self.focus_lbl.setStyleSheet("color: #e0e7ff; font-size: 11px; font-weight: 700;")
        hdr.addWidget(self.focus_lbl)
        hdr.addStretch()

        self.stats_lbl = QLabel("0/0 Completed")
        self.stats_lbl.setStyleSheet("color: #818cf8; font-size: 10px; font-weight: 700; font-family: Consolas, monospace;")
        hdr.addWidget(self.stats_lbl)
        self._layout.addLayout(hdr)

        # Container for steps
        self.steps_container = QVBoxLayout()
        self.steps_container.setSpacing(4)
        self._layout.addLayout(self.steps_container)

        if steps:
            self.set_steps(steps)

    def set_focus(self, focus_text: str):
        self.focus_lbl.setText(focus_text)

    def set_steps(self, steps: list[dict]):
        # Clear existing
        while self.steps_container.count():
            item = self.steps_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        done_count = sum(1 for s in steps if s.get("status") == "done")
        self.stats_lbl.setText(f"{done_count}/{len(steps)} Completed")

        for idx, step in enumerate(steps, 1):
            row = QHBoxLayout()
            row.setSpacing(8)

            status = step.get("status", "pending").lower()
            title = step.get("title", f"Step {idx}")

            badge = QLabel()
            badge.setFixedSize(26, 14)
            badge.setAlignment(Qt.AlignCenter)

            if status == "done":
                badge.setText("OK")
                badge.setStyleSheet("background: #065f46; color: #34d399; font-size: 8px; font-weight: 800; border-radius: 3px; font-family: Consolas;")
                title_lbl = QLabel(title)
                title_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; text-decoration: line-through;")
            elif status == "in_progress":
                badge.setText("RUN")
                badge.setStyleSheet("background: #4338ca; color: #a5b4fc; font-size: 8px; font-weight: 800; border-radius: 3px; font-family: Consolas;")
                title_lbl = QLabel(title)
                title_lbl.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700;")
            elif status == "failed":
                badge.setText("ERR")
                badge.setStyleSheet("background: #991b1b; color: #f87171; font-size: 7px; font-weight: 800; border-radius: 3px; font-family: Consolas;")
                title_lbl = QLabel(title)
                title_lbl.setStyleSheet("color: #f87171; font-size: 11px; font-weight: 600;")
            else:  # pending / skipped
                badge.setText("WAIT")
                badge.setStyleSheet("background: #1e1e2e; color: #64748b; font-size: 7px; font-weight: 800; border-radius: 3px; font-family: Consolas;")
                title_lbl = QLabel(title)
                title_lbl.setStyleSheet("color: #64748b; font-size: 11px;")

            row.addWidget(badge)
            row.addWidget(title_lbl)
            row.addStretch()

            w = QWidget()
            w.setLayout(row)
            self.steps_container.addWidget(w)


class _SwarmFeedWidget(QFrame):
    """
    Antigravity Multi-Agent Swarm Collaboration HUD.
    Displays live status of Researcher, Coder, and Verifier subagents,
    along with their shared message board entries.
    """
    def __init__(self, goal: str, parent=None):
        super().__init__(parent)
        self.goal = goal
        self.setObjectName("swarmFeed")
        self.setStyleSheet("""
            QFrame#swarmFeed {
                background-color: #06060f;
                border: 1px solid #4338ca;
                border-radius: 10px;
                margin: 4px 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        pill = QLabel("ANTIGRAVITY SWARM")
        pill.setStyleSheet("background: #4338ca; color: #ffffff; font-size: 9px; font-weight: 800; padding: 2px 7px; border-radius: 4px; font-family: Consolas, monospace;")
        hdr.addWidget(pill)

        title = QLabel("MULTI-AGENT COLLABORATION")
        title.setStyleSheet("color: #e0e7ff; font-size: 11px; font-weight: 700; letter-spacing: 0.6px;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.status_lbl = QLabel("Initializing Swarm...")
        self.status_lbl.setStyleSheet("color: #a5b4fc; font-size: 10px; font-weight: 700; font-family: Consolas, monospace;")
        hdr.addWidget(self.status_lbl)
        layout.addLayout(hdr)

        # Member Status Badges
        members_row = QHBoxLayout()
        members_row.setSpacing(6)

        self.member_badges = {}
        for mid, mname in [("researcher", "RESEARCHER"), ("coder", "ARCHITECT"), ("verifier", "VERIFIER")]:
            f = QFrame()
            f.setStyleSheet("background: #0d0d1a; border: 1px solid #1e1e30; border-radius: 5px; padding: 4px 8px;")
            fl = QHBoxLayout(f)
            fl.setContentsMargins(4, 2, 4, 2)
            fl.setSpacing(6)

            dot = QLabel("*")
            dot.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 800;")
            lbl = QLabel(mname)
            lbl.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: 700; font-family: Consolas;")
            st = QLabel("WAITING")
            st.setStyleSheet("color: #64748b; font-size: 9px; font-weight: 700;")

            fl.addWidget(dot)
            fl.addWidget(lbl)
            fl.addWidget(st)
            members_row.addWidget(f)
            self.member_badges[mid] = (dot, lbl, st, f)

        layout.addLayout(members_row)

        # Progress bar
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(3)
        self.pbar.setTextVisible(False)
        self.pbar.setRange(0, 3)
        self.pbar.setValue(0)
        self.pbar.setStyleSheet("QProgressBar { background: #161622; border-radius: 1px; } QProgressBar::chunk { background: #6366f1; border-radius: 1px; }")
        layout.addWidget(self.pbar)

        # Message Board Feed
        self.board_box = QLabel("Waiting for swarm coordinator to brief members...")
        self.board_box.setWordWrap(True)
        self.board_box.setStyleSheet("background: #0a0a14; color: #cbd5e1; border: 1px solid #1a1a2e; border-radius: 6px; padding: 8px 10px; font-size: 11px; font-family: Consolas, monospace;")
        layout.addWidget(self.board_box)

    def set_member_status(self, mid: str, role: str, status: str):
        if mid in self.member_badges:
            dot, lbl, st, f = self.member_badges[mid]
            st.setText(status.upper())
            if status == "working":
                dot.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 800;")
                lbl.setStyleSheet("color: #ffffff; font-size: 9px; font-weight: 700;")
                st.setStyleSheet("color: #a5b4fc; font-size: 9px; font-weight: 800;")
                f.setStyleSheet("background: #14142b; border: 1px solid #4f46e5; border-radius: 5px; padding: 4px 8px;")
            elif status == "done":
                dot.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 800;")
                lbl.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: 700;")
                st.setStyleSheet("color: #34d399; font-size: 9px; font-weight: 700;")
                f.setStyleSheet("background: #061a12; border: 1px solid #065f46; border-radius: 5px; padding: 4px 8px;")
            else:
                dot.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 800;")
                st.setStyleSheet("color: #f87171; font-size: 9px; font-weight: 700;")

    def set_progress(self, current: int, total: int, stage_name: str):
        self.pbar.setValue(current)
        self.status_lbl.setText(f"STAGE {current}/{total}: {stage_name.upper()}")

    def add_board_post(self, member: str, role: str, message: str):
        self.board_box.setText(f"[{member.upper()} - {role}]\n{message}")

    def set_complete(self, elapsed: float):
        self.pbar.setValue(3)
        self.status_lbl.setText(f"SWARM COMPLETED ({elapsed:.1f}s)")
        self.status_lbl.setStyleSheet("color: #34d399; font-size: 10px; font-weight: 800; font-family: Consolas, monospace;")


class BackgroundTaskWorker(QThread):
    progress = Signal(str)
    step_completed = Signal(int, bool, str, str)  # (step_idx, success, act_name, msg)
    finished_report = Signal(list)  # list of tuples (success: bool, act_name: str, msg: str)

    def __init__(self, actions_list: list[tuple[str, str]]):
        super().__init__()
        self.actions_list = actions_list

    def run(self):
        results = []
        total = len(self.actions_list)
        for idx, (act_name, act_arg) in enumerate(self.actions_list):
            step_lbl = f"Step {idx+1}/{total}: {act_name}" if total > 1 else f"Executing: {act_name}"
            self.progress.emit(step_lbl)
            if act_name == "generate_image":
                try:
                    img_path = generate_image(act_arg)
                    res = (True, act_name, f"Image generated: {img_path}")
                except Exception as e:
                    res = (False, act_name, f"Image error: {e}")
            else:
                success, msg = automation_executor.run_action(act_name, act_arg)
                res = (success, act_name, msg)
            results.append(res)
            self.step_completed.emit(idx, res[0], res[1], res[2])
        self.finished_report.emit(results)


class VoiceWaveformWidget(QWidget):
    """
    Animated 5-bar live voice visualizer equalizer.
    Provides visual feedback for idle, listening, and speaking states.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 24)
        self._state = "idle"  # "idle" | "listening" | "speaking"
        self._bar_heights = [3, 4, 3, 5, 3]
        self._phase = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._animate_frame)

    def set_state(self, state: str):
        self._state = state
        if state == "idle":
            self._timer.stop()
            self._bar_heights = [3, 4, 3, 5, 3]
            self.update()
        else:
            if not self._timer.isActive():
                self._timer.start()

    def _animate_frame(self):
        import math, random
        self._phase += 0.28
        if self._state == "listening":
            self._bar_heights = [
                int(4 + 10 * abs(math.sin(self._phase + 0.3)) + random.randint(0, 3)),
                int(5 + 13 * abs(math.sin(self._phase + 0.8)) + random.randint(0, 4)),
                int(6 + 15 * abs(math.sin(self._phase + 1.2)) + random.randint(0, 4)),
                int(5 + 12 * abs(math.sin(self._phase + 1.7)) + random.randint(0, 3)),
                int(4 + 9 * abs(math.sin(self._phase + 2.1)) + random.randint(0, 2)),
            ]
        elif self._state == "speaking":
            self._bar_heights = [
                int(4 + 8 * abs(math.sin(self._phase * 1.5 + 0.2))),
                int(6 + 12 * abs(math.sin(self._phase * 1.5 + 0.6))),
                int(8 + 14 * abs(math.sin(self._phase * 1.5 + 1.0))),
                int(6 + 11 * abs(math.sin(self._phase * 1.5 + 1.4))),
                int(4 + 7 * abs(math.sin(self._phase * 1.5 + 1.8))),
            ]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._state == "listening":
            bar_color = QColor("#10b981")  # Emerald green pulse
        elif self._state == "speaking":
            bar_color = QColor("#38bdf8")  # Sky cyan pulse
        else:
            bar_color = QColor("#334155")  # Muted slate

        p.setBrush(bar_color)
        p.setPen(Qt.NoPen)

        bar_width = 3
        spacing = 5
        start_x = 8
        mid_y = self.height() // 2

        for h in self._bar_heights:
            top_y = mid_y - (h // 2)
            p.drawRoundedRect(start_x, top_y, bar_width, h, 1.5, 1.5)
            start_x += bar_width + spacing

        p.end()


class _SystemPulseWidget(QFrame):
    """Compact Obsidian System Pulse widget displaying live CPU, RAM, and 1-Click RAM Boost."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            _SystemPulseWidget {
                background-color: #0b0b14;
                border: 1px solid #1a1a2b;
                border-radius: 7px;
            }
        """)
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_metrics)
        self._timer.start(3000)
        self._update_metrics()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(5)

        # Header: Pulse indicator + Title + Boost Button
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(5)

        dot = QLabel("●")
        dot.setStyleSheet("color: #10b981; font-size: 8px;")
        hdr.addWidget(dot)

        title = QLabel("SYSTEM PULSE")
        title.setStyleSheet("color: #64748b; font-size: 8px; font-weight: 800; letter-spacing: 0.8px;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.boost_btn = QPushButton("Boost")
        self.boost_btn.setFixedHeight(18)
        self.boost_btn.setCursor(Qt.PointingHandCursor)
        self.boost_btn.setToolTip("Trim working memory & optimize PC performance")
        self.boost_btn.setStyleSheet("""
            QPushButton {
                background-color: #022c22;
                color: #6ee7b7;
                border: 1px solid #065f46;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 700;
                padding: 0 6px;
            }
            QPushButton:hover {
                background-color: #047857;
                color: #ffffff;
            }
        """)
        self.boost_btn.clicked.connect(self._on_boost_clicked)
        hdr.addWidget(self.boost_btn)
        layout.addLayout(hdr)

        # CPU Row
        cpu_box = QHBoxLayout()
        cpu_box.setContentsMargins(0, 0, 0, 0)
        self.cpu_lbl = QLabel("CPU: 0%")
        self.cpu_lbl.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: 600; font-family: Consolas, monospace;")
        cpu_box.addWidget(self.cpu_lbl)
        cpu_box.addStretch()
        layout.addLayout(cpu_box)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFixedHeight(3)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        self.cpu_bar.setStyleSheet("""
            QProgressBar {
                background-color: #161622;
                border: none;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 1px;
            }
        """)
        layout.addWidget(self.cpu_bar)

        # RAM Row
        ram_box = QHBoxLayout()
        ram_box.setContentsMargins(0, 0, 0, 0)
        self.ram_lbl = QLabel("RAM: 0%")
        self.ram_lbl.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: 600; font-family: Consolas, monospace;")
        ram_box.addWidget(self.ram_lbl)
        ram_box.addStretch()
        layout.addLayout(ram_box)

        self.ram_bar = QProgressBar()
        self.ram_bar.setFixedHeight(3)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        self.ram_bar.setStyleSheet("""
            QProgressBar {
                background-color: #161622;
                border: none;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background-color: #818cf8;
                border-radius: 1px;
            }
        """)
        layout.addWidget(self.ram_bar)

    def _update_metrics(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            used_gb = mem.used / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)

            self.cpu_lbl.setText(f"CPU: {cpu:.0f}%")
            self.cpu_bar.setValue(int(cpu))

            self.ram_lbl.setText(f"RAM: {mem.percent:.0f}% ({used_gb:.1f}/{total_gb:.0f}G)")
            self.ram_bar.setValue(int(mem.percent))

            # Color coding on high load
            if cpu > 85:
                self.cpu_bar.setStyleSheet("QProgressBar { background-color: #161622; border: none; border-radius: 1px; } QProgressBar::chunk { background-color: #ef4444; }")
            else:
                self.cpu_bar.setStyleSheet("QProgressBar { background-color: #161622; border: none; border-radius: 1px; } QProgressBar::chunk { background-color: #38bdf8; }")

            if mem.percent > 85:
                self.ram_bar.setStyleSheet("QProgressBar { background-color: #161622; border: none; border-radius: 1px; } QProgressBar::chunk { background-color: #ef4444; }")
            else:
                self.ram_bar.setStyleSheet("QProgressBar { background-color: #161622; border: none; border-radius: 1px; } QProgressBar::chunk { background-color: #818cf8; }")
        except Exception:
            pass

    def _on_boost_clicked(self):
        import gc
        gc.collect()
        try:
            ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
        except Exception:
            pass
        self.boost_btn.setText("Trimmed!")
        self.boost_btn.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                color: #a7f3d0;
                border: 1px solid #10b981;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 700;
                padding: 0 6px;
            }
        """)
        QTimer.singleShot(1500, self._reset_boost_btn)
        self._update_metrics()

    def _reset_boost_btn(self):
        self.boost_btn.setText("Boost")
        self.boost_btn.setStyleSheet("""
            QPushButton {
                background-color: #022c22;
                color: #6ee7b7;
                border: 1px solid #065f46;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 700;
                padding: 0 6px;
            }
            QPushButton:hover {
                background-color: #047857;
                color: #ffffff;
            }
        """)


_THEME_PALETTES = {
    "indigo": {
        "name": "Obsidian Indigo",
        "primary": "#4f46e5",
        "primary_hover": "#4338ca",
        "accent": "#38bdf8",
        "accent_glow": "#6366f1",
        "badge_bg": "#1e1b4b",
        "badge_border": "#4338ca",
        "badge_text": "#a5b4fc",
    },
    "emerald": {
        "name": "Emerald Matrix",
        "primary": "#059669",
        "primary_hover": "#047857",
        "accent": "#10b981",
        "accent_glow": "#34d399",
        "badge_bg": "#062e24",
        "badge_border": "#059669",
        "badge_text": "#6ee7b7",
    },
    "cyan": {
        "name": "Cyber Cyan",
        "primary": "#0891b2",
        "primary_hover": "#0e7490",
        "accent": "#06b6d4",
        "accent_glow": "#22d3ee",
        "badge_bg": "#082f49",
        "badge_border": "#0284c7",
        "badge_text": "#7dd3fc",
    },
    "purple": {
        "name": "Royal Amethyst",
        "primary": "#7c3aed",
        "primary_hover": "#6d28d9",
        "accent": "#a855f7",
        "accent_glow": "#c084fc",
        "badge_bg": "#2e1065",
        "badge_border": "#7c3aed",
        "badge_text": "#d8b4fe",
    },
    "crimson": {
        "name": "Rose Crimson",
        "primary": "#e11d48",
        "primary_hover": "#be123c",
        "accent": "#f43f5e",
        "accent_glow": "#fb7185",
        "badge_bg": "#4c0519",
        "badge_border": "#e11d48",
        "badge_text": "#fda4af",
    },
}


class _PromptRefineWorker(QThread):
    refined = Signal(str)
    failed = Signal(str)

    def __init__(self, llm_manager, raw_prompt: str):
        super().__init__()
        self.llm_manager = llm_manager
        self.raw_prompt = raw_prompt

    def run(self):
        try:
            from ai.llm_manager import ChatMessage, clean_repetitive_patterns
            system_prompt = (
                "You are an elite AI prompt engineer. Rewrite the user's raw prompt draft into a world-class, "
                "well-structured prompt with clear context, core objectives, constraints, and expected output format. "
                "Output ONLY the enhanced prompt directly. Do not include introductory remarks, meta-commentary, or code blocks."
            )
            messages = [ChatMessage(role="user", content=f"Refine this prompt draft:\n\n{self.raw_prompt}")]
            res = self.llm_manager.chat(messages, system_prompt=system_prompt)
            res = clean_repetitive_patterns(res).strip()
            if res:
                self.refined.emit(res)
            else:
                self.failed.emit("Empty result")
        except Exception as e:
            self.failed.emit(str(e))


class _SlashCommandsMenuWidget(QFrame):
    """Sleek obsidian popup suggesting available slash commands when user types '/' in input."""
    command_selected = Signal(str)

    COMMANDS = [
        ("/otp", "Extract 2FA / OTP verification code from email", "SECURITY", "#38bdf8"),
        ("/accounts", "Discover connected online web accounts & platforms", "ACCOUNTS", "#a855f7"),
        ("/clean", "1-Click PC cleanup, temp cache flush & RAM trim", "OPTIMIZE", "#10b981"),
        ("/excel", "Create formatted Excel spreadsheet with formulas", "EXCEL", "#34d399"),
        ("/refine", "Refine & structure current draft into an expert prompt", "PROMPT", "#38bdf8"),
        ("/theme", "Toggle obsidian UI accent theme (Indigo, Emerald, Cyan, Purple)", "THEME", "#ec4899"),
        ("/rename", "Rename current active conversation session", "SESSION", "#f59e0b"),
        ("/sys", "View live CPU, RAM, and hardware telemetry diagnostics", "HARDWARE", "#60a5fa"),
        ("/super", "Launch autonomous multi-step SuperAgent task", "AUTONOMOUS", "#ec4899"),
        ("/new", "Start a fresh unpolluted conversation session", "SESSION", "#a5b4fc"),
        ("/clear", "Clear chat history from active session", "MEMORY", "#f43f5e"),
        ("/export", "Export conversation transcript to Markdown", "EXPORT", "#94a3b8"),
        ("/compact", "Compact & summarize older conversation turns", "MEMORY", "#38bdf8"),
        ("/find", "Search all saved conversation history across sessions", "SEARCH", "#38bdf8"),
        ("/starred", "Display bookmarked & starred assistant answers", "BOOKMARK", "#f59e0b"),
        ("/shortcuts", "Display keyboard navigation & power keys cheat-sheet", "HELP", "#f59e0b"),
        ("/palette", "Open full desktop command palette", "SHORTCUT", "#e2e8f0"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            _SlashCommandsMenuWidget {
                background-color: #0c0c16;
                border: 1px solid #232338;
                border-radius: 8px;
            }
        """)
        self._filtered_cmds = list(self.COMMANDS)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(4, 2, 4, 2)
        dot = QLabel("●")
        dot.setStyleSheet("color: #38bdf8; font-size: 8px;")
        hdr.addWidget(dot)

        title = QLabel("COMMAND SHORTCUTS (Tab or Enter to select)")
        title.setStyleSheet("color: #64748b; font-size: 8px; font-weight: 800; letter-spacing: 0.6px;")
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        self.list_widget = QListWidget()
        self.list_widget.setFixedHeight(140)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                color: #e2e8f0;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px 6px;
                border-radius: 4px;
                margin-bottom: 1px;
            }
            QListWidget::item:selected {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QListWidget::item:hover:!selected {
                background-color: #121220;
            }
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)
        self._populate_list()

    def _populate_list(self):
        self.list_widget.clear()
        for cmd, desc, badge, color in self._filtered_cmds:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, cmd)

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            row_layout.setSpacing(8)

            cmd_lbl = QLabel(cmd)
            cmd_lbl.setStyleSheet(f"color: {color}; font-weight: 700; font-family: Consolas, monospace; font-size: 11px;")
            row_layout.addWidget(cmd_lbl)

            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
            row_layout.addWidget(desc_lbl)
            row_layout.addStretch()

            badge_lbl = QLabel(badge)
            badge_lbl.setStyleSheet(f"background: #141426; color: {color}; font-size: 8px; font-weight: 700; padding: 1px 5px; border-radius: 3px; font-family: Consolas;")
            row_layout.addWidget(badge_lbl)

            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def filter_commands(self, query: str):
        q = (query or "").lower().strip()
        if not q:
            self._filtered_cmds = list(self.COMMANDS)
        else:
            self._filtered_cmds = [
                (c, d, b, clr) for (c, d, b, clr) in self.COMMANDS
                if q in c.lower() or q in d.lower() or q in b.lower()
            ]
        self._populate_list()

    def has_matches(self) -> bool:
        return len(self._filtered_cmds) > 0

    def select_next(self):
        cur = self.list_widget.currentRow()
        if cur < self.list_widget.count() - 1:
            self.list_widget.setCurrentRow(cur + 1)
        else:
            self.list_widget.setCurrentRow(0)

    def select_prev(self):
        cur = self.list_widget.currentRow()
        if cur > 0:
            self.list_widget.setCurrentRow(cur - 1)
        else:
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def trigger_selected(self):
        item = self.list_widget.currentItem()
        if item:
            cmd = item.data(Qt.UserRole)
            if cmd:
                self.command_selected.emit(cmd)

    def _on_item_clicked(self, item):
        if item:
            cmd = item.data(Qt.UserRole)
            if cmd:
                self.command_selected.emit(cmd)


class _SessionItemWidget(QWidget):
    """Sleek sidebar session item with title, chat indicator, and 1-click delete button."""
    delete_requested = Signal(str)

    def __init__(self, session_id: str, title: str, is_active: bool = False, is_pinned: bool = False):
        super().__init__()
        self.session_id = session_id
        self.title = title
        self.is_active = is_active
        self.is_pinned = is_pinned

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        # Pin / Dot indicator
        if is_pinned:
            pin_lbl = QLabel("📌")
            pin_lbl.setStyleSheet("font-size: 9px; color: #f59e0b;")
            pin_lbl.setToolTip("Pinned conversation")
            layout.addWidget(pin_lbl)
        else:
            dot = QLabel("●" if is_active else "○")
            dot.setStyleSheet("color: #38bdf8; font-size: 8px;" if is_active else "color: #475569; font-size: 8px;")
            layout.addWidget(dot)

        # Title
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(
            "color: #38bdf8; font-weight: 700; font-size: 11px;" if is_active
            else ("color: #f1f5f9; font-weight: 600; font-size: 11px;" if is_pinned
                  else "color: #94a3b8; font-weight: 500; font-size: 11px;")
        )
        self.title_lbl.setToolTip(f"{title} (Pinned)" if is_pinned else title)
        layout.addWidget(self.title_lbl, 1)

        # Delete Button (×)
        self.del_btn = QPushButton("×")
        self.del_btn.setFixedSize(18, 18)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.setToolTip("Delete this chat")
        self.del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 700;
                line-height: 14px;
            }
            QPushButton:hover {
                background: #450a0a;
                color: #ef4444;
            }
        """)
        self.del_btn.clicked.connect(lambda: self.delete_requested.emit(self.session_id))
        layout.addWidget(self.del_btn)


class _MessageBubble(QWidget):
    """Modern conversational message stream: unboxed natural prose like top AIs, elevated cards for code/files."""

    def __init__(self, role: str, content: str = "", on_speak_clicked=None, on_enable_vision_clicked=None, on_suggestion_clicked=None, on_regenerate_clicked=None, on_edit_clicked=None, message_id: int | None = None, is_starred: bool = False):
        super().__init__()
        self.role = role
        self.content = content
        self.on_speak_clicked = on_speak_clicked
        self.on_enable_vision_clicked = on_enable_vision_clicked
        self.on_suggestion_clicked = on_suggestion_clicked
        self.on_regenerate_clicked = on_regenerate_clicked
        self.on_edit_clicked = on_edit_clicked
        self.message_id = message_id
        self.is_starred = is_starred
        self._is_speaking_this = False
        self.is_user = (role == "user")
        self.vision_cta_btn: QPushButton | None = None

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 4, 8, 4)

        self.card = QFrame()
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(12, 8, 12, 8)
        self.card_layout.setSpacing(6)

        if self.is_user:
            self._orig_style = f"""
                QFrame {{
                    background-color: {_BG_USER};
                    color: {_TEXT_MAIN};
                    border-radius: 12px;
                    border: 1px solid #2b2b38;
                }}
            """
            self.card.setStyleSheet(self._orig_style)
            self.card.setMaximumWidth(720)
            self.layout.addStretch()
            self.layout.addWidget(self.card, 0)
        else:
            # Top-notch unboxed assistant response: seamless canvas, transparent, no square box
            self._orig_style = """
                QFrame {
                    background-color: transparent;
                    color: #e2e8f0;
                    border: none;
                }
            """
            self.card.setStyleSheet(self._orig_style)
            self.layout.addWidget(self.card, 1)

        # Assistant Header
        if not self.is_user:
            header_row = QHBoxLayout()
            header_row.setContentsMargins(0, 0, 0, 2)
            header_row.setSpacing(6)

            dot = QLabel("●")
            dot.setStyleSheet("color: #38bdf8; font-size: 8px;")
            header_row.addWidget(dot)

            name_lbl = QLabel("NOVA")
            name_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 0.8px;")
            header_row.addWidget(name_lbl)

            header_row.addStretch()
            self.card_layout.addLayout(header_row)

        # Dynamic content container
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(6)
        self.card_layout.addWidget(self.content_widget)

        # Single streaming label for live token rendering
        self.stream_label = QLabel()
        self.stream_label.setTextFormat(Qt.RichText)
        self.stream_label.setWordWrap(True)
        self.stream_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.stream_label.setStyleSheet("background: transparent; border: none; font-size: 13px; line-height: 1.55;")
        self.content_layout.addWidget(self.stream_label)

        # Bottom action bar for User cards (Copy & Edit Prompt)
        if self.is_user:
            user_action_row = QHBoxLayout()
            user_action_row.setContentsMargins(0, 4, 0, 0)
            user_action_row.setSpacing(6)
            user_action_row.addStretch()

            self.user_copy_btn = QPushButton("Copy")
            self.user_copy_btn.setFixedHeight(20)
            self.user_copy_btn.setCursor(Qt.PointingHandCursor)
            self.user_copy_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #64748b;
                    border: 1px solid #2b2b38;
                    border-radius: 4px;
                    font-size: 9px;
                    font-weight: 600;
                    padding: 0 6px;
                }
                QPushButton:hover {
                    color: #e2e8f0;
                    background: #1e1e2d;
                    border-color: #475569;
                }
            """)
            self.user_copy_btn.clicked.connect(self._copy_user_content)
            user_action_row.addWidget(self.user_copy_btn)

            if on_edit_clicked:
                self.user_edit_btn = QPushButton("Edit Prompt")
                self.user_edit_btn.setFixedHeight(20)
                self.user_edit_btn.setCursor(Qt.PointingHandCursor)
                self.user_edit_btn.setStyleSheet(self.user_copy_btn.styleSheet())
                self.user_edit_btn.clicked.connect(lambda: on_edit_clicked(self.content))
                user_action_row.addWidget(self.user_edit_btn)

            self.card_layout.addLayout(user_action_row)

        # Bottom action bar for Assistant
        if not self.is_user:
            self.action_bar = QHBoxLayout()
            self.action_bar.setContentsMargins(0, 4, 0, 0)
            self.action_bar.setSpacing(6)

            self.full_copy_btn = QPushButton("Copy All")
            self.full_copy_btn.setIcon(create_copy_icon("#94a3b8", size=12))
            self.full_copy_btn.setFixedHeight(24)
            self.full_copy_btn.setMinimumWidth(76)
            self.full_copy_btn.setCursor(Qt.PointingHandCursor)
            self.full_copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #171720;
                    color: {_TEXT_MUTED};
                    border: 1px solid #262633;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    color: #ffffff;
                    border-color: #3f3f50;
                    background-color: #20202c;
                }}
            """)
            self.full_copy_btn.clicked.connect(self._copy_full_content)
            self.action_bar.addWidget(self.full_copy_btn)

            self.star_btn = QPushButton("Starred" if is_starred else "Star")
            self.star_btn.setFixedHeight(24)
            self.star_btn.setMinimumWidth(64)
            self.star_btn.setCursor(Qt.PointingHandCursor)
            self.star_btn.setToolTip("Bookmark response in Starred library")
            self._update_star_btn_style()
            self.star_btn.clicked.connect(self._toggle_star)
            self.action_bar.addWidget(self.star_btn)

            if on_regenerate_clicked:
                self.regenerate_btn = QPushButton("Regenerate")
                self.regenerate_btn.setFixedHeight(24)
                self.regenerate_btn.setMinimumWidth(82)
                self.regenerate_btn.setCursor(Qt.PointingHandCursor)
                self.regenerate_btn.setStyleSheet(self.full_copy_btn.styleSheet())
                self.regenerate_btn.setToolTip("Regenerate assistant response with fresh perspective")
                self.regenerate_btn.clicked.connect(lambda: on_regenerate_clicked(self))
                self.action_bar.addWidget(self.regenerate_btn)

            if on_speak_clicked:
                self.listen_btn = QPushButton("Speak")
                self.listen_btn.setIcon(create_speaker_icon("#94a3b8", size=12))
                self.listen_btn.setFixedHeight(24)
                self.listen_btn.setMinimumWidth(68)
                self.listen_btn.setCursor(Qt.PointingHandCursor)
                self.listen_btn.setStyleSheet(self.full_copy_btn.styleSheet())
                self.listen_btn.clicked.connect(self._on_speak_toggle)
                self.action_bar.addWidget(self.listen_btn)

            self.action_bar.addStretch()
            self.meta_lbl = QLabel("")
            self.meta_lbl.setStyleSheet("color: #475569; font-size: 9px; font-weight: 600; font-family: Consolas, monospace;")
            self.action_bar.addWidget(self.meta_lbl)
            self.card_layout.addLayout(self.action_bar)

            self.suggestions_frame = QWidget()
            self.suggestions_frame.setStyleSheet("background: transparent;")
            self.suggestions_layout = QHBoxLayout(self.suggestions_frame)
            self.suggestions_layout.setContentsMargins(0, 4, 0, 2)
            self.suggestions_layout.setSpacing(6)
            self.suggestions_frame.setVisible(False)
            self.card_layout.addWidget(self.suggestions_frame)

    def _copy_user_content(self):
        QApplication.clipboard().setText(self.content, QClipboard.Clipboard)
        if hasattr(self, "user_copy_btn"):
            self.user_copy_btn.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.user_copy_btn.setText("Copy") if hasattr(self, "user_copy_btn") else None)

    def _update_star_btn_style(self):
        if not hasattr(self, "star_btn"):
            return
        if getattr(self, "is_starred", False):
            self.star_btn.setText("Starred")
            self.star_btn.setStyleSheet("""
                QPushButton {
                    background-color: #291805;
                    color: #fbbf24;
                    border: 1px solid #d97706;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 0 8px;
                }
                QPushButton:hover {
                    background-color: #3d2308;
                }
            """)
        else:
            self.star_btn.setText("Star")
            self.star_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #171720;
                    color: {_TEXT_MUTED};
                    border: 1px solid #262633;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    color: #ffffff;
                    border-color: #3f3f50;
                    background-color: #20202c;
                }}
            """)

    def _toggle_star(self):
        if getattr(self, "message_id", None):
            import memory.database as db
            self.is_starred = db.toggle_star_message(self.message_id)
            self._update_star_btn_style()
            top = self.window()
            if hasattr(top, "show_toast"):
                msg = "Response bookmarked in Starred library" if self.is_starred else "Response removed from Starred library"
                top.show_toast(msg, "BOOKMARK")
        else:
            self.is_starred = not getattr(self, "is_starred", False)
            self._update_star_btn_style()

    def _on_speak_toggle(self):
        if not self.on_speak_clicked:
            return
        if self._is_speaking_this:
            from voice.tts import tts
            tts.stop()
            self._reset_speak_btn()
        else:
            self._is_speaking_this = True
            if hasattr(self, "listen_btn"):
                self.listen_btn.setText("Stop (Speaking...)")
                self.listen_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #450a0a;
                        color: #f87171;
                        border: 1px solid #dc2626;
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: 700;
                        padding: 0 8px;
                    }
                    QPushButton:hover {
                        background-color: #7f1d1d;
                        color: #ffffff;
                    }
                """)
            self.on_speak_clicked(self.content, on_done=self._reset_speak_btn)

    def _reset_speak_btn(self):
        self._is_speaking_this = False
        if hasattr(self, "listen_btn"):
            self.listen_btn.setText("Speak")
            self.listen_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #171720;
                    color: {_TEXT_MUTED};
                    border: 1px solid #262633;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    color: #ffffff;
                    border-color: #3f3f50;
                    background-color: #20202c;
                }}
            """)

    def _derive_suggestions(self, text: str) -> list[tuple[str, str]]:
        if not text or len(text.strip()) < 10:
            return []
        lower = text.lower()
        suggestions: list[tuple[str, str]] = []

        if "```" in text or any(k in lower for k in ["def ", "class ", "import ", "function", "return "]):
            suggestions.append(("Unit Tests", "Generate comprehensive unit tests for this code."))
            suggestions.append(("Optimize", "Optimize this code for speed, readability, and low memory usage."))
            suggestions.append(("Explain Code", "Explain the logic and flow of this implementation step by step."))
        elif any(k in lower for k in ["error", "exception", "traceback", "failed", "bug"]):
            suggestions.append(("Root Cause", "Explain the exact root cause of this error."))
            suggestions.append(("Fix & Prevent", "Show how to fix this issue and avoid similar bugs in production."))
        elif any(k in lower for k in ["$$", "\\frac", "equation", "formula", "theorem", "math"]):
            suggestions.append(("Detailed Proof", "Provide the step-by-step mathematical derivation."))
            suggestions.append(("Practical Example", "Give a real-world calculation example using this formula."))
        elif any(k in lower for k in ["architecture", "database", "design", "system", "api"]):
            suggestions.append(("Architecture Diagram", "Describe the system architecture and component interactions."))
            suggestions.append(("Implementation Plan", "Outline a prioritized roadmap for implementing this."))
        else:
            suggestions.append(("Elaborate", "Can you elaborate further with additional details and context?"))
            suggestions.append(("Alternative Approaches", "What are the alternative approaches and trade-offs?"))
            suggestions.append(("Action Plan", "Summarize this into a concise, actionable checklist."))

        return suggestions[:3]

        if content:
            self.finalize_content(content)

    def set_meta(self, time_str: str, latency_sec: float = 0.0, model_name: str = ""):
        parts = [time_str]
        words = len((self.content or "").split())
        if words > 0:
            parts.append(f"{words} words")
            read_sec = max(1, round(words / 4.0))
            if read_sec >= 3:
                parts.append(f"~{read_sec}s read")
        if latency_sec > 0:
            parts.append(f"{latency_sec:.1f}s gen")
        if model_name:
            short_model = model_name.split("/")[-1]
            parts.append(short_model)
        if hasattr(self, "meta_lbl"):
            self.meta_lbl.setText(" • ".join(parts))

    def highlight_search(self, query: str = "") -> bool:
        """Highlights the bubble if query matches; returns True if matched."""
        if not query:
            self.card.setStyleSheet(self._orig_style)
            return False
        if query.lower() in (self.content or "").lower():
            accent = "#38bdf8"
            self.card.setStyleSheet(f"""
                QFrame {{
                    border: 1px solid {accent} !important;
                    background-color: #0c1524 !important;
                    border-radius: 8px;
                }}
            """)
            return True
        else:
            self.card.setStyleSheet(self._orig_style)
            return False

    def update_stream_text(self, text: str):
        """Called dynamically as tokens arrive in real-time."""
        self.content = text
        self.stream_label.setText(_render_images(_render_prose(text)))

    def finalize_content(self, text: str):
        """Parses finished text into prose sections, ThinkingBlockWidgets, and interactive CodeBlockWidgets."""
        self.content = text
        if self.is_user:
            self.stream_label.setText(_render_images(_render_message_html(text)))
            return

        # Clear content layout
        while self.content_layout.count() > 0:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Claude Extended Thinking CoT Detection
        think_match = re.search(r"<(think|thinking|reasoning)>(.*?)</\1>", text, re.DOTALL | re.IGNORECASE)
        if think_match:
            thinking_content = think_match.group(2).strip()
            text = re.sub(r"<(think|thinking|reasoning)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
            if thinking_content:
                think_widget = ThinkingBlockWidget(thinking_content)
                self.content_layout.addWidget(think_widget)

        # Parse markdown code fences
        last_end = 0
        has_code_block = False
        for m in _CODE_FENCE_RE.finditer(text):
            has_code_block = True
            before = text[last_end:m.start()].strip()
            if before:
                prose_lbl = QLabel()
                prose_lbl.setTextFormat(Qt.RichText)
                prose_lbl.setWordWrap(True)
                prose_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
                prose_lbl.setStyleSheet("background: transparent; border: none; font-size: 13px; line-height: 1.45;")
                prose_lbl.setText(_render_images(_render_prose(before)))
                self.content_layout.addWidget(prose_lbl)

            lang = (m.group(1) or "code").strip()
            code_text = m.group(2).rstrip("\n")
            code_widget = CodeBlockWidget(lang, code_text)
            self.content_layout.addWidget(code_widget)

            # If HTML or SVG, attach inline Claude Artifact Card
            if lang.lower() in ("html", "htm", "svg") or ("<html" in code_text.lower() or "<svg" in code_text.lower()):
                try:
                    from ui.claude_artifacts_widget import ClaudeArtifactCard
                    card_title = "Interactive Web Artifact"
                    title_m = re.search(r"<title>(.*?)</title>", code_text, re.I)
                    if title_m:
                        card_title = title_m.group(1).strip()
                    artifact_card = ClaudeArtifactCard(card_title, code_text, lang)
                    artifact_card.open_requested.connect(
                        lambda t, c, l: self.window().open_claude_artifact(t, c, l) if hasattr(self.window(), "open_claude_artifact") else None
                    )
                    self.content_layout.addWidget(artifact_card)
                except Exception as e:
                    log.warning("Could not instantiate ClaudeArtifactCard: {}", e)

            last_end = m.end()

        tail = text[last_end:].strip()
        if tail or not has_code_block:
            display_tail = tail if has_code_block else text
            prose_lbl = QLabel()
            prose_lbl.setTextFormat(Qt.RichText)
            prose_lbl.setWordWrap(True)
            prose_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
            prose_lbl.setStyleSheet("background: transparent; border: none; font-size: 13px; line-height: 1.45;")
            prose_lbl.setText(_render_images(_render_prose(display_tail)))
            self.content_layout.addWidget(prose_lbl)

        # 1-Click Screen Vision Call-to-Action button if vision is requested
        if not self.is_user and self.on_enable_vision_clicked and hasattr(self, "action_bar"):
            text_l = text.lower()
            needs_vision = any(k in text_l for k in [
                "screen vision", "screen share", "enable_vision", "اسکرین شیئر", "اسکرین ویژن", "اسکرین آن", "screen on"
            ])
            if needs_vision and not self.vision_cta_btn:
                self.vision_cta_btn = QPushButton("Turn On Screen Vision")
                self.vision_cta_btn.setFixedHeight(24)
                self.vision_cta_btn.setCursor(Qt.PointingHandCursor)
                self.vision_cta_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #042f2e;
                        color: #5eead4;
                        border: 1px solid #0d9488;
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: 700;
                        padding: 0 10px;
                    }}
                    QPushButton:hover {{
                        background-color: #0f766e;
                        color: #ffffff;
                    }}
                """)
                def _trigger_vision():
                    self.on_enable_vision_clicked()
                    if self.vision_cta_btn:
                        self.vision_cta_btn.setText("Vision Activated")
                        self.vision_cta_btn.setEnabled(False)
                self.vision_cta_btn.clicked.connect(_trigger_vision)
                self.action_bar.insertWidget(0, self.vision_cta_btn)

        # Context-aware follow-up suggestion chips
        if not self.is_user and hasattr(self, "suggestions_layout") and self.on_suggestion_clicked:
            while self.suggestions_layout.count() > 0:
                item = self.suggestions_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            suggestions = self._derive_suggestions(text)
            if suggestions:
                lbl = QLabel("Suggested:")
                lbl.setStyleSheet("color: #64748b; font-size: 9px; font-weight: 700; margin-right: 4px;")
                self.suggestions_layout.addWidget(lbl)
                for label, prompt in suggestions:
                    chip = QPushButton(label)
                    chip.setFixedHeight(22)
                    chip.setCursor(Qt.PointingHandCursor)
                    chip.setStyleSheet("""
                        QPushButton {
                            background-color: #0b1329;
                            color: #7dd3fc;
                            border: 1px solid #1e293b;
                            border-radius: 11px;
                            font-size: 10px;
                            font-weight: 600;
                            padding: 0 10px;
                        }
                        QPushButton:hover {
                            background-color: #0369a1;
                            color: #ffffff;
                            border-color: #38bdf8;
                        }
                    """)
                    chip.clicked.connect(lambda checked=False, p=prompt: self.on_suggestion_clicked(p))
                    self.suggestions_layout.addWidget(chip)
                self.suggestions_layout.addStretch()
                self.suggestions_frame.setVisible(True)
            else:
                self.suggestions_frame.setVisible(False)

    def _copy_full_content(self):
        QApplication.clipboard().setText(self.content, QClipboard.Clipboard)
        self.full_copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.full_copy_btn.setText("Copy All"))


class ChatHeroWidget(QFrame):
    """Modern executive hero greeting and quick-action capability card for empty chat state."""

    def __init__(self, user_name: str = "", on_action=None):
        super().__init__()
        self.user_name = user_name or "Commander"
        self.on_action = on_action
        self._build_ui()

    def update_user_name(self, name: str):
        self.user_name = name or "Commander"
        if hasattr(self, "greeting_lbl"):
            self.greeting_lbl.setText("How can I help you today?")

    def _build_ui(self):
        self.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 28, 16, 20)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignCenter)

        # Central Card Container
        hero_card = QFrame()
        hero_card.setMaximumWidth(680)
        hero_card.setStyleSheet(f"""
            QFrame {{
                background-color: #0b0b14;
                border: 1px solid #1c1c2e;
                border-radius: 14px;
            }}
        """)
        card_vbox = QVBoxLayout(hero_card)
        card_vbox.setContentsMargins(28, 26, 28, 26)
        card_vbox.setSpacing(16)

        # Header with Logo & Brand
        hdr_box = QVBoxLayout()
        hdr_box.setSpacing(6)
        hdr_box.setAlignment(Qt.AlignCenter)

        logo = QLabel("N")
        logo.setFixedSize(42, 42)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #06b6d4);
            color: #ffffff;
            font-weight: 900;
            font-size: 20px;
            border-radius: 10px;
        """)
        hdr_box.addWidget(logo, 0, Qt.AlignCenter)

        self.greeting_lbl = QLabel("How can I help you today?")
        self.greeting_lbl.setAlignment(Qt.AlignCenter)
        self.greeting_lbl.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 800; letter-spacing: -0.2px;")
        hdr_box.addWidget(self.greeting_lbl)

        sub_title = QLabel("Powered by Gemini 2.0, ChatGPT 4o, Claude 3.7 & Autonomous SuperAgent")
        sub_title.setAlignment(Qt.AlignCenter)
        sub_title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
        hdr_box.addWidget(sub_title)
        card_vbox.addLayout(hdr_box)

        # 6 Clean Action Cards (3x2 Grid)
        grid_container = QWidget()
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(0, 8, 0, 0)
        grid.setSpacing(10)

        actions_data = [
            ("2FA & Web Accounts", "Extract login OTPs & discover email services", "Check connected web accounts for my email and fetch latest 2FA OTP codes.", "SECURITY", "#38bdf8"),
            ("Deep PC Optimizer", "Clean temporary junk, flush cache & trim RAM", "Run full PC system optimization, clean temp cache, and trim RAM.", "OPTIMIZE", "#10b981"),
            ("Automated Excel Creator", "Generate styled spreadsheets with formulas", "Create an Excel spreadsheet on Desktop for Student Marksheet with Roll No, Name, Marks, and Percentage.", "EXCEL", "#34d399"),
            ("Python Engineering Suite", "Production-ready scripts with 1-click execution", "Write a Python script with GUI using PySide6 that monitors network ping and internet connection.", "RUNNABLE", "#818cf8"),
            ("Desktop Screen Vision", "Inspect active desktop, read UI & guide actions", "Analyze my active screen, explain what is open, and guide me on next actions.", "VISION", "#f59e0b"),
            ("Deep Autonomous Research", "Multi-source web synthesis & comprehensive report", "Conduct deep web research on latest AI agent frameworks in 2026 and synthesize a report.", "RESEARCH", "#ec4899"),
        ]

        for idx, (title, subtitle, prompt, badge, color) in enumerate(actions_data):
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #10101c;
                    border: 1px solid #1e1e30;
                    border-radius: 10px;
                    padding: 12px 14px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: #17172a;
                    border-color: {color};
                }}
            """)
            btn_layout = QVBoxLayout(btn)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(4)

            top_row = QHBoxLayout()
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 700;")
            top_row.addWidget(t_lbl)
            top_row.addStretch()

            b_lbl = QLabel(badge)
            b_lbl.setStyleSheet(f"background: #14142b; color: {color}; font-size: 8px; font-weight: 800; padding: 2px 6px; border-radius: 4px; font-family: Consolas;")
            top_row.addWidget(b_lbl)
            btn_layout.addLayout(top_row)

            s_lbl = QLabel(subtitle)
            s_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
            btn_layout.addWidget(s_lbl)

            btn.clicked.connect(lambda _, p=prompt: self._handle_click(p, False))
            r = idx // 2
            c = idx % 2
            grid.addWidget(btn, r, c)

        card_vbox.addWidget(grid_container)
        layout.addWidget(hero_card)

    def _handle_click(self, prompt: str, is_instant: bool):
        if self.on_action:
            self.on_action(prompt, is_instant)


class MainWindow(QWidget):
    def __init__(self, config: AppConfig, llm_manager: LLMManager):
        super().__init__()
        self.config = config
        self.llm_manager = llm_manager

        self.snipper = SnippingWidget()
        self.snipper.snipped.connect(self._on_region_snipped)

        self._continuous_thread: QThread | None = None
        self._continuous_worker: ContinuousVoiceWorker | None = None
        self._hands_free_active = False
        self._single_shot_thread: QThread | None = None
        self._single_shot_worker: SingleShotVoiceWorker | None = None
        self._llm_thread: _LLMWorker | None = None
        self._task_worker: BackgroundTaskWorker | None = None
        self._attached_path: Path | None = None

        self._current_assistant_bubble: _MessageBubble | None = None
        self._stream_text: str = ""
        self.hero_widget: ChatHeroWidget | None = None
        self._search_matches: list[_MessageBubble] = []
        self._search_idx: int = -1
        self._current_plan_widget: _ExecutionPlanWidget | None = None
        self._code_artifacts: list[dict] = []
        self._active_session_id = "default"
        self._prompt_history: list[str] = []
        self._prompt_history_idx: int = -1

        # Global Hotkey Thread (Ctrl+Shift+D for Snip, Ctrl+Shift+N to Toggle Nova)
        self.hotkey_thread = GlobalHotkeyThread()
        self.hotkey_thread.hotkey_triggered.connect(self.snipper.start_snip)
        self.hotkey_thread.summon_triggered.connect(self._toggle_window_visibility)
        self.hotkey_thread.start()

        self._setup_window()
        self._build_ui()
        self._refresh_session_combo(selected_id=self._active_session_id)
        self._load_history()
        self._update_tasks_btn_badge()

        # Seed prompt history from recent sessions
        try:
            recent_msgs = db.get_recent_history(limit=25, session_id=self._active_session_id)
            for m in recent_msgs:
                if m["role"] == "user" and m["content"] and not m["content"].startswith("["):
                    self._prompt_history.append(m["content"])
        except Exception:
            pass

        # System Tray Integration
        self._is_force_quitting = False
        self._setup_tray_icon()

        self._operating_mode = "ENGINEER"

        # Keyboard Shortcuts
        self.cmd_k_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.cmd_k_shortcut.activated.connect(self._open_command_palette)

        self.cmd_new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.cmd_new_shortcut.activated.connect(self._create_new_session)

        self.cmd_attach_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.cmd_attach_shortcut.activated.connect(self._on_attach_file)

        self.cmd_git_shortcut = QShortcut(QKeySequence("Ctrl+G"), self)
        self.cmd_git_shortcut.activated.connect(self._open_git_manager)

        self.cmd_find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.cmd_find_shortcut.activated.connect(self._toggle_search_bar)

        self.cmd_prompt_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.cmd_prompt_shortcut.activated.connect(self._open_prompt_library)

        self.cmd_artifacts_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.cmd_artifacts_shortcut.activated.connect(self._open_artifacts_drawer)

        self.cmd_terminal_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.cmd_terminal_shortcut.activated.connect(self._open_terminal_runner)

        # Antigravity Shortcuts & Listeners
        self.cmd_skills_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.cmd_skills_shortcut.activated.connect(self._open_skills_manager)

        self._active_steps_widget: _AntigravityStepsWidget | None = None
        self._swarm_worker = None

        from automation.actions import register_steps_listener, register_focus_listener
        register_steps_listener(self._on_antigravity_steps_update)
        register_focus_listener(self._on_antigravity_focus_update)

        self.cmd_help_shortcut = QShortcut(QKeySequence("F1"), self)
        self.cmd_help_shortcut.activated.connect(self._show_shortcuts_dialog)

        # Telemetry Polling Timer (smooth 2.5s interval)
        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.setInterval(2500)
        self._telemetry_timer.timeout.connect(self._update_telemetry)
        self._telemetry_timer.start()
        QTimer.singleShot(300, self._update_telemetry)

        # Start non-blocking Desktop-Hybrid cloud sync in background
        remote_sync.start_background_sync(self.config, delay_sec=1.2)

        # Check API key seamlessly on startup
        QTimer.singleShot(600, self._check_api_key_on_startup)

    def _check_api_key_on_startup(self):
        key = get_api_key(self.config)
        if hasattr(self, "model_combo"):
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == self.config.llm.model:
                    self.model_combo.blockSignals(True)
                    self.model_combo.setCurrentIndex(i)
                    self.model_combo.blockSignals(False)
                    break
        if self.hero_widget and self.config.user_name:
            self.hero_widget.update_user_name(self.config.user_name)

        if not key or len(key) < 10 or key.startswith("AQ."):
            self.status_pill.setText("SETUP REQUIRED")
            from ui.onboarding_dialog import WelcomeWizardDialog
            wiz = WelcomeWizardDialog(self.config, self)
            if wiz.exec():
                new_key = get_api_key(self.config)
                if new_key and len(new_key) >= 10:
                    self.status_pill.setText("READY")
                if hasattr(self, "model_combo"):
                    for i in range(self.model_combo.count()):
                        if self.model_combo.itemData(i) == self.config.llm.model:
                            self.model_combo.blockSignals(True)
                            self.model_combo.setCurrentIndex(i)
                            self.model_combo.blockSignals(False)
                            break
                if self.config.user_name:
                    self.title_label.setText(self.config.ui.assistant_name.upper())
                    self.setWindowTitle(f"{self.config.ui.assistant_name} - Autonomous Desktop Studio")
                    if self.hero_widget:
                        self.hero_widget.update_user_name(self.config.user_name)
        else:
            self.status_pill.setText("READY")

    def _update_telemetry(self):
        if not self.isVisible():
            return
        try:
            cpu_pct, ram_pct, used_gb, total_gb = _get_live_telemetry()
            if hasattr(self, "cpu_lbl"):
                self.cpu_lbl.setText(f"CPU: {cpu_pct}%")
            if hasattr(self, "cpu_bar"):
                self.cpu_bar.setValue(cpu_pct)
                cpu_color = "#ef4444" if cpu_pct > 80 else "#38bdf8"
                self.cpu_bar.setStyleSheet(f"QProgressBar {{ background: #1a1a26; border-radius: 1px; }} QProgressBar::chunk {{ background: {cpu_color}; border-radius: 1px; }}")

            if hasattr(self, "ram_lbl"):
                self.ram_lbl.setText(f"RAM: {ram_pct}% ({used_gb}G)")
            if hasattr(self, "ram_bar"):
                self.ram_bar.setValue(ram_pct)
                ram_color = "#ef4444" if ram_pct > 85 else "#10b981"
                self.ram_bar.setStyleSheet(f"QProgressBar {{ background: #1a1a26; border-radius: 1px; }} QProgressBar::chunk {{ background: {ram_color}; border-radius: 1px; }}")
        except Exception:
            pass

    def show_toast(self, text: str, tag: str = "INFO", duration_ms: int = 2600):
        """Displays a floating HUD toast banner in the top-right corner."""
        try:
            if hasattr(self, "_active_toast") and self._active_toast:
                try:
                    self._active_toast.deleteLater()
                except Exception:
                    pass
            toast = NovaToast(self, text, tag, duration_ms)
            toast.show()
            t_width = toast.sizeHint().width()
            t_height = toast.sizeHint().height()
            toast.setGeometry(self.width() - t_width - 24, 18, t_width, t_height)
            toast.raise_()
            self._active_toast = toast
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_active_toast") and self._active_toast:
            try:
                t_width = self._active_toast.width()
                self._active_toast.move(self.width() - t_width - 24, 18)
            except Exception:
                pass
        if hasattr(self, "dropzone_overlay") and self.dropzone_overlay.isVisible() and hasattr(self, "main_stack"):
            self.dropzone_overlay.setGeometry(self.main_stack.currentWidget().rect())

    def _find_model_index(self, name: str) -> int:
        name_lower = name.strip().lower()
        for i in range(self.model_combo.count()):
            m_id = (self.model_combo.itemData(i) or "").lower()
            text = self.model_combo.itemText(i).lower()
            if name_lower in m_id or name_lower in text:
                return i
        return -1

    def _find_mode_index(self, name: str) -> int:
        name_lower = name.strip().lower()
        mode_keys = ["gemini", "chatgpt", "claude", "superagent", "engineer", "research", "sysadmin", "general"]
        for idx, key in enumerate(mode_keys):
            if name_lower in key or key in name_lower:
                return idx
        return -1

    def open_claude_artifact(self, title: str, content: str, lang: str = "html"):
        """Displays interactive artifact in the Claude Artifacts dual-view panel."""
        if hasattr(self, "claude_artifact_viewer"):
            self.claude_artifact_viewer.load_artifact(title, content, lang)
            self.claude_artifact_viewer.setVisible(True)
            if hasattr(self, "chat_splitter"):
                self.chat_splitter.setSizes([550, 450])
            self.show_toast(f"Artifact loaded: {title}", "SUCCESS")

    def _on_top_model_changed(self, index: int):
        if index < 0 or index >= self.model_combo.count():
            return
        m_id = self.model_combo.itemData(index)
        if m_id and m_id != self.config.llm.model:
            self.config.llm.model = m_id
            if m_id.startswith("claude-"):
                self.config.llm.provider = "anthropic"
            elif any(m_id.startswith(p) for p in ["gpt-", "o1", "o3", "chatgpt"]):
                self.config.llm.provider = "openai"
            elif m_id.startswith("gemini-"):
                self.config.llm.provider = "gemini"
            else:
                self.config.llm.provider = "groq"
            save_config(self.config)
            self.status_pill.setText("ENGINE SWITCHED")
            short_name = m_id.split("/")[-1]
            self.show_toast(f"Engine switched: {short_name}", "MODEL")
            QTimer.singleShot(1500, lambda: self.status_pill.setText("READY"))

    def _toggle_search_bar(self):
        if hasattr(self, "search_bar"):
            if self.search_bar.isVisible():
                self._close_search()
            else:
                self.search_bar.setVisible(True)
                self.search_bar.input.setFocus()
                self.search_bar.input.selectAll()

    def _close_search(self):
        if hasattr(self, "search_bar"):
            self.search_bar.setVisible(False)
        self.input_edit.setFocus()
        self._search_matches = []
        self._search_idx = -1
        if hasattr(self, "search_bar"):
            self.search_bar.set_match_status(0, 0)
        for i in range(self.message_layout.count()):
            item = self.message_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), _MessageBubble):
                item.widget().highlight_search("")

    def _on_search_query_changed(self, query: str):
        self._search_matches = []
        self._search_idx = -1
        if not query:
            self._close_search()
            return

        for i in range(self.message_layout.count()):
            item = self.message_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), _MessageBubble):
                bubble: _MessageBubble = item.widget()
                if bubble.highlight_search(query):
                    self._search_matches.append(bubble)

        total = len(self._search_matches)
        if total > 0:
            self._search_idx = 0
            self.search_bar.set_match_status(1, total)
            self._scroll_to_bubble(self._search_matches[0])
        else:
            self.search_bar.set_match_status(0, 0)

    def _navigate_search_next(self):
        if not self._search_matches:
            return
        self._search_idx = (self._search_idx + 1) % len(self._search_matches)
        self.search_bar.set_match_status(self._search_idx + 1, len(self._search_matches))
        self._scroll_to_bubble(self._search_matches[self._search_idx])

    def _navigate_search_prev(self):
        if not self._search_matches:
            return
        self._search_idx = (self._search_idx - 1) % len(self._search_matches)
        self.search_bar.set_match_status(self._search_idx + 1, len(self._search_matches))
        self._scroll_to_bubble(self._search_matches[self._search_idx])

    def _scroll_to_bubble(self, bubble: _MessageBubble):
        try:
            self.scroll.ensureWidgetVisible(bubble, 0, 60)
        except Exception:
            pass

    def _show_shortcuts_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nova AI - Keyboard Shortcuts")
        dlg.setFixedSize(480, 420)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #0b0b12;
                border: 1px solid #1e293b;
                border-radius: 10px;
            }
            QLabel {
                color: #e2e8f0;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
        """)
        d_layout = QVBoxLayout(dlg)
        d_layout.setContentsMargins(20, 20, 20, 20)
        d_layout.setSpacing(12)

        t_lbl = QLabel("KEYBOARD SHORTCUTS & POWER KEYS")
        t_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #38bdf8; font-family: Consolas, monospace;")
        d_layout.addWidget(t_lbl)

        shortcuts = [
            ("Ctrl + K", "Spotlight Command Palette (Actions & Navigation)"),
            ("Ctrl + N", "Start New Chat Session / Thread"),
            ("Ctrl + O", "Attach File Context (Code, Logs, Data, Images)"),
            ("Ctrl + G", "Git Workspace Manager (Status, Diff, Commit & Push)"),
            ("Ctrl + P", "Prompt & Automation Library (Templates & Workflows)"),
            ("Ctrl + B", "Code Artifacts & Scripts Drawer"),
            ("Ctrl + Shift + S", "Antigravity Skills & Customizations Manager"),
            ("Ctrl + T", "Quick Embedded PowerShell Terminal"),
            ("Ctrl + F", "Find in Chat Conversation"),
            ("Ctrl + Shift + D", "Desktop Screen Snip & Vision OCR"),
            ("Ctrl + Shift + N", "Summon Nova AI from System Tray"),
            ("Enter", "Send Message / Prompt"),
            ("Shift + Enter", "Insert newline in prompt box"),
            ("F1", "Open this Keyboard Shortcuts cheat sheet"),
            ("Esc", "Dismiss active Palette, Search bar, or Modal"),
        ]

        grid = QFrame()
        grid.setStyleSheet("background: #111118; border-radius: 8px; border: 1px solid #1e293b; padding: 10px;")
        g_layout = QVBoxLayout(grid)
        g_layout.setSpacing(8)
        for key, desc in shortcuts:
            row = QHBoxLayout()
            k_lbl = QLabel(key)
            k_lbl.setStyleSheet("background: #1e293b; color: #38bdf8; font-family: Consolas, monospace; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 4px;")
            k_lbl.setFixedWidth(130)
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
            row.addWidget(k_lbl)
            row.addWidget(d_lbl)
            row.addStretch()
            g_layout.addLayout(row)
        d_layout.addWidget(grid)

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("background-color: #0284c7; color: #ffffff; border: none; border-radius: 6px; font-weight: 700;")
        btn_close.clicked.connect(dlg.accept)
        d_layout.addWidget(btn_close)

        dlg.exec()

    def _open_prompt_library(self):
        try:
            from ui.prompt_library import PromptLibraryDialog
            dlg = PromptLibraryDialog(self)
            dlg.prompt_selected.connect(self._on_prompt_selected)
            dlg.exec()
        except Exception as e:
            self.show_toast(f"Prompt Library notice: {e}", "WARNING")

    def _on_prompt_selected(self, prompt: str):
        self.input_edit.setText(prompt)
        self.input_edit.setFocus()
        self.show_toast("Prompt template loaded into chat", "INFO")

    def _open_artifacts_drawer(self):
        try:
            from ui.code_artifacts_dialog import CodeArtifactsDialog
            dlg = CodeArtifactsDialog(self._code_artifacts, self)
            dlg.exec()
        except Exception as e:
            self.show_toast(f"Artifacts Drawer notice: {e}", "WARNING")

    def _open_terminal_runner(self):
        try:
            from ui.quick_terminal_dialog import QuickTerminalDialog
            dlg = QuickTerminalDialog("E:\\Nova_AI", self)
            dlg.analyze_requested.connect(self._on_terminal_analyze)
            dlg.exec()
        except Exception as e:
            self.show_toast(f"Terminal notice: {e}", "WARNING")

    def _open_git_manager(self):
        try:
            from ui.git_manager_dialog import GitManagerDialog
            dlg = GitManagerDialog("E:\\Nova_AI", self)
            def _on_analyze(prompt_type, text):
                self.input_edit.setText(text)
                self.input_edit.setFocus()
                self.show_toast("Git diff handed off to Nova", "INFO")
            dlg.analyze_requested.connect(_on_analyze)
            dlg.exec()
        except Exception as e:
            self.show_toast(f"Git notice: {e}", "WARNING")

    def _on_terminal_analyze(self, cmd: str, output: str):
        prompt = (
            f"Analyze this terminal command output for `{cmd}`:\n"
            f"```\n{output[:1600]}\n```\n"
            f"Please explain the execution results, identify any issues or warnings, and recommend next actions."
        )
        self.input_edit.setText(prompt)
        self.input_edit.setFocus()
        self.show_toast("Terminal output handed off to Nova", "INFO")

    def _launch_super_agent(self, goal: str):
        if hasattr(self, "_super_agent_worker") and self._super_agent_worker and self._super_agent_worker.isRunning():
            self._super_agent_worker.cancel()
            self.show_toast("Previous SuperAgent execution cancelled", "SYSTEM")

        from ai.super_agent import SuperAgentWorker
        self.status_pill.setText("SUPERAGENT RUNNING...")
        self.status_pill.setStyleSheet("""
            color: #a5b4fc;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 0.6px;
            padding: 3px 10px;
            border-radius: 9px;
            background: #1e1b4b;
            border: 1px solid #4338ca;
        """)

        # Insert live SuperAgent visual HUD into chat
        self._super_agent_feed = _SuperAgentFeedWidget(goal, max_iterations=8)
        self.message_layout.insertWidget(self.message_layout.count() - 1, self._super_agent_feed)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

        # Update Send button to Stop
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Stop")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                padding: 0 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)

        self._super_agent_worker = SuperAgentWorker(goal, self.config, self.llm_manager, max_iterations=8)

        def on_iteration(it, thought):
            self.status_pill.setText(f"SUPERAGENT STEP {it}/8...")
            if hasattr(self, "_super_agent_feed") and self._super_agent_feed:
                self._super_agent_feed.set_thought(it, thought)
                self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

        def on_action_done(it, act_name, success, out):
            if hasattr(self, "_super_agent_feed") and self._super_agent_feed:
                self._super_agent_feed.add_action_result(it, act_name, success, out)
                self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

        def on_finished(all_ok, summary, total_steps, elapsed):
            self._reset_send_button()
            mode = getattr(self, "_operating_mode", "ENGINEER")
            if mode == "SUPERAGENT":
                self.status_pill.setText("SUPERAGENT READY")
                self.status_pill.setStyleSheet("""
                    color: #a5b4fc;
                    font-size: 9px;
                    font-weight: 800;
                    letter-spacing: 0.6px;
                    padding: 3px 10px;
                    border-radius: 9px;
                    background: #1e1b4b;
                    border: 1px solid #4338ca;
                """)
            else:
                self.status_pill.setText("READY")
                self.status_pill.setStyleSheet("""
                    color: #38bdf8;
                    font-size: 9px;
                    font-weight: 800;
                    letter-spacing: 0.6px;
                    padding: 3px 10px;
                    border-radius: 9px;
                    background: #111118;
                    border: 1px solid #272735;
                """)
            if hasattr(self, "_super_agent_feed") and self._super_agent_feed:
                self._super_agent_feed.finalize(all_ok, summary)

            now_str = datetime.now().strftime("%I:%M %p")
            deliverable_text = f"**Autonomous SuperAgent Deliverable ({total_steps} actions in {elapsed:.1f}s):**\n\n{summary}"
            b = self._add_bubble("assistant", deliverable_text)
            b.set_meta(now_str, elapsed, self.config.llm.model)
            cur_sid = getattr(self, "_active_session_id", "default")
            db.add_message("assistant", deliverable_text, session_id=cur_sid)
            self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

            if self.config.voice.auto_speak:
                self._speak_text(summary[:200])

        self._super_agent_worker.iteration_started.connect(on_iteration)
        self._super_agent_worker.action_completed.connect(on_action_done)
        self._super_agent_worker.agent_finished.connect(on_finished)
        self._super_agent_worker.start()

    def _open_skills_manager(self):
        """Opens the Antigravity Skills & Extensions Manager Dialog."""
        from ui.skills_manager_dialog import SkillsManagerDialog
        dlg = SkillsManagerDialog(self)
        dlg.exec()

    def _on_antigravity_steps_update(self, steps: list[dict]):
        """Live slot for updating Antigravity execution steps checklist."""
        if not hasattr(self, "_active_steps_widget") or self._active_steps_widget is None:
            self._active_steps_widget = _AntigravityStepsWidget(steps=steps)
            self.message_layout.insertWidget(self.message_layout.count() - 1, self._active_steps_widget)
        else:
            self._active_steps_widget.set_steps(steps)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _on_antigravity_focus_update(self, focus_text: str):
        """Live slot for broadcasting Antigravity high-level focus banner."""
        if not hasattr(self, "_active_steps_widget") or self._active_steps_widget is None:
            self._active_steps_widget = _AntigravityStepsWidget(initial_focus=focus_text)
            self.message_layout.insertWidget(self.message_layout.count() - 1, self._active_steps_widget)
        else:
            self._active_steps_widget.set_focus(focus_text)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _launch_swarm(self, goal: str):
        """Launches an Antigravity multi-agent swarm collaboration workflow."""
        if hasattr(self, "_swarm_worker") and self._swarm_worker and self._swarm_worker.isRunning():
            self._swarm_worker.cancel()
            self.show_toast("Previous Swarm execution cancelled", "SYSTEM")

        from ai.swarm_manager import SwarmWorker
        self.status_pill.setText("SWARM WORKING...")
        self.status_pill.setStyleSheet("""
            color: #818cf8;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 0.6px;
            padding: 3px 10px;
            border-radius: 9px;
            background: #1e1b4b;
            border: 1px solid #4f46e5;
        """)

        # Insert live Swarm visual HUD into chat
        self._swarm_feed = _SwarmFeedWidget(goal)
        self.message_layout.insertWidget(self.message_layout.count() - 1, self._swarm_feed)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

        # Update Send button to Stop
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Stop")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                padding: 0 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)

        self._swarm_worker = SwarmWorker(goal, self.config, self.llm_manager)

        def on_member_status(mid, role, status):
            if hasattr(self, "_swarm_feed") and self._swarm_feed:
                self._swarm_feed.set_member_status(mid, role, status)

        def on_board_post(member, role, message):
            if hasattr(self, "_swarm_feed") and self._swarm_feed:
                self._swarm_feed.add_board_post(member, role, message)

        def on_swarm_progress(current, total, stage_name):
            if hasattr(self, "_swarm_feed") and self._swarm_feed:
                self._swarm_feed.set_progress(current, total, stage_name)

        def on_swarm_complete(synthesis, elapsed):
            self._reset_send_button()
            self.status_pill.setText("READY")
            self.status_pill.setStyleSheet("""
                color: #8e8ea0;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.6px;
                padding: 3px 10px;
                border-radius: 9px;
                background: #111118;
                border: 1px solid #272735;
            """)
            if hasattr(self, "_swarm_feed") and self._swarm_feed:
                self._swarm_feed.set_complete(elapsed)

            now_str = datetime.now().strftime("%I:%M %p")
            b = self._add_bubble("assistant", synthesis)
            b.set_meta(now_str, elapsed, self.config.llm.model)
            cur_sid = getattr(self, "_active_session_id", "default")
            db.add_message("assistant", synthesis, session_id=cur_sid)
            self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

            if self.config.voice.auto_speak:
                self._speak_text("Swarm collaboration workflow completed successfully.")

        def on_swarm_error(err_msg):
            self._reset_send_button()
            self.status_pill.setText("SWARM FAILED")
            self.show_toast(err_msg, "ERROR")

        self._swarm_worker.member_status.connect(on_member_status)
        self._swarm_worker.board_post.connect(on_board_post)
        self._swarm_worker.swarm_progress.connect(on_swarm_progress)
        self._swarm_worker.swarm_complete.connect(on_swarm_complete)
        self._swarm_worker.swarm_error.connect(on_swarm_error)
        self._swarm_worker.start()

    def _on_mode_changed(self, index: int):
        if index < 0 or index >= self.mode_combo.count():
            return
        m_id = self.mode_combo.itemData(index) or "ENGINEER"
        self._operating_mode = m_id
        if hasattr(self, "mode_combo") and self.mode_combo.currentIndex() != index:
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(index)
            self.mode_combo.blockSignals(False)
        mode_names = {
            "GEMINI": "Google Gemini 2.0 & Multimodal",
            "CHATGPT": "ChatGPT 4o & Data Analyst",
            "CLAUDE": "Claude 3.7 Sonnet & Artifacts",
            "SUPERAGENT": "Autonomous Base44 SuperAgent",
            "ENGINEER": "Senior Software Architect",
            "RESEARCH": "Deep Research Analyst",
            "SYSADMIN": "Windows System Administrator",
            "GENERAL": "Executive General Assistant",
        }
        if self._operating_mode == "GEMINI":
            self.status_pill.setText("GEMINI 2.0 READY")
            self.status_pill.setStyleSheet("""
                color: #38bdf8;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.6px;
                padding: 3px 10px;
                border-radius: 9px;
                background: #082f49;
                border: 1px solid #0284c7;
            """)
        elif self._operating_mode == "CHATGPT":
            self.status_pill.setText("CHATGPT 4o READY")
            self.status_pill.setStyleSheet("""
                color: #34d399;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.6px;
                padding: 3px 10px;
                border-radius: 9px;
                background: #062b1b;
                border: 1px solid #059669;
            """)
        elif self._operating_mode == "CLAUDE":
            self.status_pill.setText("CLAUDE 3.7 READY")
            self.status_pill.setStyleSheet("""
                color: #c084fc;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.6px;
                padding: 3px 10px;
                border-radius: 9px;
                background: #2e1065;
                border: 1px solid #7e22ce;
            """)
        elif self._operating_mode == "SUPERAGENT":
            self.status_pill.setText("SUPERAGENT READY")
            self.status_pill.setStyleSheet("""
                color: #a5b4fc;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.6px;
                padding: 3px 10px;
                border-radius: 9px;
                background: #1e1b4b;
                border: 1px solid #4338ca;
            """)
        else:
            self.status_pill.setText("READY")
            self.status_pill.setStyleSheet("""
                color: #38bdf8;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.6px;
                padding: 3px 10px;
                border-radius: 9px;
                background: #111118;
                border: 1px solid #272735;
            """)
        display_name = mode_names.get(self._operating_mode, self._operating_mode)
        self.show_toast(f"Mode: {display_name}", "SYSTEM")

    def _register_code_artifact(self, lang: str, code: str):
        lines = code.splitlines()
        first_line = ""
        for line in lines[:3]:
            stripped = line.strip().lstrip("#/").strip()
            if stripped:
                first_line = stripped
                break
        title = first_line[:35] if first_line else f"{lang.upper()} Script"
        self._code_artifacts.append({
            "id": len(self._code_artifacts) + 1,
            "lang": lang or "txt",
            "code": code,
            "time": datetime.now().strftime("%I:%M %p"),
            "lines": len(lines),
            "title": title
        })
        if hasattr(self, "artifacts_btn"):
            self.artifacts_btn.setText(f"Artifacts ({len(self._code_artifacts)})")

    def _open_command_palette(self):
        palette = CommandPaletteDialog(self)
        palette.action_triggered.connect(self._handle_palette_action)
        geo = self.geometry()
        x = geo.x() + (geo.width() - palette.width()) // 2
        y = geo.y() + 80
        palette.move(x, y)
        palette.exec()

    def _handle_palette_action(self, cmd_id: str, payload: str):
        if cmd_id == "system_stats":
            self._quick_action("system_stats")
        elif cmd_id == "clear_temp":
            self._quick_action("clear_temp")
        elif cmd_id == "empty_recycle_bin":
            self._quick_action("empty_recycle_bin")
        elif cmd_id == "lock":
            self._quick_action("lock")
        elif cmd_id == "snip_screen":
            self.snipper.start_snip()
        elif cmd_id == "toggle_vision":
            self._toggle_screen_vision()
        elif cmd_id == "web_research":
            self._send_quick_prompt("[action:web_search:] ")
        elif cmd_id == "write_python":
            self._send_quick_prompt("Write a modular Python script with robust error handling and CLI arguments: ")
        elif cmd_id == "run_py_file":
            self._on_run_python_file()
        elif cmd_id == "nav_tasks":
            self._switch_nav(1)
        elif cmd_id == "nav_conn":
            self._switch_nav(2)
        elif cmd_id == "nav_feed":
            self._switch_nav(3)
        elif cmd_id == "nav_settings":
            self._switch_nav(4)
        elif cmd_id == "export_chat":
            self._export_conversation()
        elif cmd_id == "clear_chat":
            self._clear_conversation()
        elif cmd_id == "new_chat":
            self._create_new_session()
        elif cmd_id == "attach_file":
            self._on_attach_file()
        elif cmd_id == "find_chat":
            self._toggle_search_bar()
        elif cmd_id == "open_prompts":
            self._open_prompt_library()
        elif cmd_id == "open_artifacts":
            self._open_artifacts_drawer()
        elif cmd_id == "open_terminal":
            self._open_terminal_runner()
        elif cmd_id == "open_git":
            self._open_git_manager()
        elif cmd_id == "super_agent":
            self._send_quick_prompt("/super ")
        elif cmd_id == "open_skills":
            self._open_skills_manager()
        elif cmd_id == "swarm_agent":
            self._send_quick_prompt("/teamwork ")
        elif cmd_id == "compact_context":
            self.input_edit.setPlainText("/compact")
            self._send_message()
        elif cmd_id == "show_shortcuts":
            self._show_shortcuts_dialog()
        elif cmd_id == "custom_prompt":
            self._send_quick_prompt(payload)

    def _export_conversation(self):
        recent = db.get_recent_history(limit=200, session_id=self._active_session_id)
        if not recent:
            QMessageBox.information(self, "Export Conversation", "No conversation messages found to export.")
            return

        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"Nova_Chat_{now_str}.html"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Conversation Log", default_name, "Interactive HTML Document (*.html);;Markdown Log (*.md);;Text File (*.txt)"
        )
        if file_path:
            try:
                p = Path(file_path)
                if p.suffix.lower() == ".html" or "HTML" in selected_filter:
                    html_content = _generate_chat_html(recent, self.config.llm.model)
                    p.write_text(html_content, encoding="utf-8")
                else:
                    lines = [
                        "# Nova AI - Autonomous Conversation Log",
                        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        f"Model Engine: {self.config.llm.model}",
                        "",
                        "---",
                        ""
                    ]
                    for msg in recent:
                        role_title = "User" if msg["role"] == "user" else "Nova AI Assistant"
                        lines.append(f"### {role_title}\n")
                        lines.append(f"{msg['content']}\n")
                        lines.append("---\n")
                    p.write_text("\n".join(lines), encoding="utf-8")
                self.show_toast(f"Exported to {p.name}", "EXPORT")
            except Exception as e:
                self.show_toast(f"Export failed: {e}", "ERROR")

    def _setup_tray_icon(self):
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#0284c7"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 32, 32, 8, 8)
        p.setPen(QColor("#ffffff"))
        f = p.font()
        f.setBold(True)
        f.setPixelSize(20)
        p.setFont(f)
        p.drawText(pix.rect(), Qt.AlignCenter, "N")
        p.end()
        tray_icon = QIcon(pix)

        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip(f"{self.config.ui.assistant_name} - Autonomous Desktop Studio")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #121217;
                color: #f8fafc;
                border: 1px solid #22222b;
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        act_open = QAction("Open Nova Studio", self)
        act_open.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(act_open)

        act_palette = QAction("Quick Command Palette (Ctrl+K)", self)
        act_palette.triggered.connect(self._open_command_palette)
        tray_menu.addAction(act_palette)

        act_snip = QAction("Snip Screen (Ctrl+Shift+D)", self)
        act_snip.triggered.connect(self.snipper.start_snip)
        tray_menu.addAction(act_snip)

        act_stats = QAction("System Diagnostics", self)
        act_stats.triggered.connect(lambda: self._quick_action("system_stats"))
        tray_menu.addAction(act_stats)

        tray_menu.addSeparator()

        act_exit = QAction("Exit Completely", self)
        act_exit.triggered.connect(self._force_quit)
        tray_menu.addAction(act_exit)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _force_quit(self):
        self._is_force_quitting = True
        QApplication.quit()

    def closeEvent(self, event):
        if not getattr(self, "_is_force_quitting", False) and hasattr(self, "tray") and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Nova AI Assistant",
                "Nova is running in the background. Press Ctrl+Shift+N to summon or click the tray icon.",
                QSystemTrayIcon.Information,
                2200
            )
        else:
            event.accept()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            if hasattr(self, "dropzone_overlay") and hasattr(self, "main_stack") and self.main_stack.currentIndex() == 0:
                self.dropzone_overlay.setGeometry(self.main_stack.currentWidget().rect())
                self.dropzone_overlay.setVisible(True)
                self.dropzone_overlay.raise_()
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        if hasattr(self, "dropzone_overlay"):
            self.dropzone_overlay.setVisible(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if hasattr(self, "dropzone_overlay"):
            self.dropzone_overlay.setVisible(False)
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = Path(urls[0].toLocalFile())
                if file_path.exists():
                    self._process_attached_file(file_path)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

    def _on_hero_action(self, prompt: str, is_instant: bool):
        if is_instant and prompt == "system_stats":
            self._quick_action("system_stats")
        else:
            self._send_quick_prompt(prompt)

    def _toggle_window_visibility(self):
        """Summons Nova to foreground or tucks it away."""
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _setup_window(self):
        self.setWindowTitle(f"{self.config.ui.assistant_name} - Autonomous Desktop Studio")
        start_w = max(self.config.ui.start_width, 1140)
        start_h = max(self.config.ui.start_height, 760)
        self.resize(start_w, start_h)
        self.setMinimumSize(960, 620)
        self.setMaximumSize(16777215, 16777215)

        flags = Qt.Window
        if self.config.ui.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setWindowOpacity(self.config.ui.window_opacity)

        # High-End Dark Obsidian Styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {_BG_BLACK};
                color: {_TEXT_MAIN};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }}
            QScrollArea {{
                background: {_BG_BLACK};
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #272733;
                min-height: 28px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #3f3f50;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT SIDEBAR (Modern ChatGPT / Cursor Style) ──────────────
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(245)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #080811;
                border-right: 1px solid #1a1a2b;
            }
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 12)
        sidebar_layout.setSpacing(10)

        # Brand / Logo Header
        brand_box = QHBoxLayout()
        brand_box.setSpacing(10)
        logo_lbl = QLabel("N")
        logo_lbl.setFixedSize(30, 30)
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #06b6d4);
            color: #ffffff;
            font-weight: 900;
            font-size: 15px;
            border-radius: 7px;
        """)
        brand_box.addWidget(logo_lbl)

        brand_text_box = QVBoxLayout()
        brand_text_box.setSpacing(1)
        self.title_label = QLabel(self.config.ui.assistant_name.upper())
        self.title_label.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 800; letter-spacing: 0.8px;")
        sub_brand = QLabel("Autonomous Agent")
        sub_brand.setStyleSheet("color: #64748b; font-size: 9px; font-weight: 600;")
        brand_text_box.addWidget(self.title_label)
        brand_text_box.addWidget(sub_brand)
        brand_box.addLayout(brand_text_box)
        brand_box.addStretch()

        self.beacon_dot = QLabel("●")
        self.beacon_dot.setStyleSheet("color: #10b981; font-size: 10px;")
        brand_box.addWidget(self.beacon_dot)
        sidebar_layout.addLayout(brand_box)

        # Prominent + New Chat Button (Ctrl+N)
        self.sidebar_new_btn = QPushButton("+  New Chat")
        self.sidebar_new_btn.setCursor(Qt.PointingHandCursor)
        self.sidebar_new_btn.setFixedHeight(34)
        self.sidebar_new_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e1b4b;
                color: #e0e7ff;
                border: 1px solid #4338ca;
                border-radius: 7px;
                font-size: 11px;
                font-weight: 700;
                padding-left: 12px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #312e81;
                border-color: #6366f1;
                color: #ffffff;
            }
        """)
        self.sidebar_new_btn.clicked.connect(self._create_new_session)
        sidebar_layout.addWidget(self.sidebar_new_btn)

        # Recent Chats Section
        sess_hdr = QLabel("RECENT CONVERSATIONS")
        sess_hdr.setStyleSheet("color: #475569; font-size: 9px; font-weight: 800; letter-spacing: 0.8px; margin-top: 4px;")
        sidebar_layout.addWidget(sess_hdr)

        # Instant Search / Filter bar for conversation sessions
        self.session_search = QLineEdit()
        self.session_search.setPlaceholderText("Filter chats...")
        self.session_search.setFixedHeight(25)
        self.session_search.setStyleSheet("""
            QLineEdit {
                background-color: #0b0b14;
                color: #e2e8f0;
                border: 1px solid #1a1a2b;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #4338ca;
                background-color: #10101f;
            }
        """)
        self.session_search.textChanged.connect(self._filter_sessions)
        sidebar_layout.addWidget(self.session_search)

        self.session_list = QListWidget()
        self.session_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(self._show_session_context_menu)
        self.session_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 11px;
                font-weight: 500;
            }
            QListWidget::item {
                padding: 3px 4px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background-color: #151528;
                color: #38bdf8;
                border-left: 3px solid #38bdf8;
            }
            QListWidget::item:hover:!selected {
                background-color: #0f0f1c;
                color: #f1f5f9;
            }
        """)
        self.session_list.currentRowChanged.connect(self._on_session_list_row_changed)
        self.session_list.itemDoubleClicked.connect(self._on_session_item_double_clicked)
        sidebar_layout.addWidget(self.session_list, 1)

        # Navigation Workspaces
        nav_sep = QFrame()
        nav_sep.setFixedHeight(1)
        nav_sep.setStyleSheet("background-color: #1a1a2b;")
        sidebar_layout.addWidget(nav_sep)

        ws_lbl = QLabel("WORKSPACES")
        ws_lbl.setStyleSheet("color: #475569; font-size: 9px; font-weight: 800; letter-spacing: 0.8px;")
        sidebar_layout.addWidget(ws_lbl)

        self.nav_btns = []
        self.nav_chat = self._create_nav_button("Chat Console", 0)
        sidebar_layout.addWidget(self.nav_chat)

        self.nav_tasks = self._create_nav_button("Tasks Hub", 1)
        sidebar_layout.addWidget(self.nav_tasks)

        self.nav_conn = self._create_nav_button("Connections", 2)
        sidebar_layout.addWidget(self.nav_conn)

        self.nav_feed = self._create_nav_button("Live Feed", 3)
        sidebar_layout.addWidget(self.nav_feed)

        self.nav_settings = self._create_nav_button("Settings", 4)
        sidebar_layout.addWidget(self.nav_settings)

        self.tasks_btn = self.nav_tasks
        self.conn_btn = self.nav_conn
        self.settings_btn = self.nav_settings

        # Quick Mode Toggles
        quick_toggles_row = QHBoxLayout()
        quick_toggles_row.setSpacing(6)

        self.screen_vision_btn = QPushButton("Vision: OFF")
        self.screen_vision_btn.setCursor(Qt.PointingHandCursor)
        self.screen_vision_btn.setFixedHeight(24)
        self._style_quick_button(self.screen_vision_btn, active=self.config.ui.screen_observing)
        self.screen_vision_btn.clicked.connect(self._toggle_screen_vision)
        quick_toggles_row.addWidget(self.screen_vision_btn)

        self.hands_free_btn = QPushButton("Mic: OFF")
        self.hands_free_btn.setCursor(Qt.PointingHandCursor)
        self.hands_free_btn.setFixedHeight(24)
        self._style_quick_button(self.hands_free_btn, active=False)
        self.hands_free_btn.clicked.connect(self._toggle_hands_free_mode)
        quick_toggles_row.addWidget(self.hands_free_btn)

        sidebar_layout.addLayout(quick_toggles_row)

        self.system_pulse = _SystemPulseWidget(self)
        sidebar_layout.addWidget(self.system_pulse)

        root.addWidget(self.sidebar)

        # ── RIGHT MAIN CONTAINER ─────────────────────────────────────
        main_content = QWidget()
        main_content.setStyleSheet("background-color: #07070a;")
        main_vbox = QVBoxLayout(main_content)
        main_vbox.setContentsMargins(14, 12, 14, 12)
        main_vbox.setSpacing(8)

        # ── TOP BAR (Clean, spacious, uncrowded) ──────────────────────
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 4)
        top_bar.setSpacing(10)

        self.view_title = QLabel("Chat & Autonomous Code Console")
        self.view_title.setVisible(False)

        # Mode / Persona Selector Pill (Left)
        self.mode_combo = QComboBox()
        self.mode_combo.setCursor(Qt.PointingHandCursor)
        self.mode_combo.setFixedHeight(28)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #0d0d1a;
                color: #a5b4fc;
                border: 1px solid #282845;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 700;
                font-family: Consolas, monospace;
            }
            QComboBox:hover {
                border-color: #6366f1;
                background-color: #14142b;
            }
            QComboBox::drop-down {
                border: none;
                width: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: #0b0b14;
                color: #e2e8f0;
                border: 1px solid #282845;
                selection-background-color: #4f46e5;
                selection-color: #ffffff;
                outline: none;
                padding: 4px;
            }
        """)
        mode_choices = [
            ("GEMINI", "Mode: Gemini 2.0"),
            ("CHATGPT", "Mode: ChatGPT 4o"),
            ("CLAUDE", "Mode: Claude 3.7"),
            ("SUPERAGENT", "Mode: SuperAgent"),
            ("ENGINEER", "Mode: Engineer"),
            ("RESEARCH", "Mode: Research"),
            ("SYSADMIN", "Mode: SysAdmin"),
            ("GENERAL", "Mode: General"),
        ]
        for m_id, m_label in mode_choices:
            self.mode_combo.addItem(m_label, m_id)
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        top_bar.addWidget(self.mode_combo)

        # Model Selector Pill (Left)
        self.model_combo = QComboBox()
        self.model_combo.setCursor(Qt.PointingHandCursor)
        self.model_combo.setFixedHeight(28)
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #0d0d1a;
                color: #38bdf8;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 700;
                font-family: Consolas, monospace;
            }
            QComboBox:hover {
                border-color: #38bdf8;
                background-color: #132238;
            }
            QComboBox::drop-down {
                border: none;
                width: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: #090d16;
                color: #e2e8f0;
                border: 1px solid #1e3a5f;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
                outline: none;
                padding: 4px;
            }
        """)
        model_choices = [
            ("gemini-2.0-flash", "Gemini: 2.0 Flash (Google)"),
            ("gemini-2.0-pro-exp-02-05", "Gemini: 2.0 Pro (Google)"),
            ("gemini-1.5-pro", "Gemini: 1.5 Pro (2M Context)"),
            ("gemini-1.5-flash", "Gemini: 1.5 Flash (Google)"),
            ("gpt-4o", "OpenAI: GPT-4o (Omni)"),
            ("gpt-4o-mini", "OpenAI: GPT-4o Mini"),
            ("o3-mini", "OpenAI: o3-mini (Reasoning)"),
            ("o1", "OpenAI: o1 (Reasoning)"),
            ("claude-3-7-sonnet-20250219", "Claude: 3.7 Sonnet (Anthropic)"),
            ("claude-3-5-sonnet-20241022", "Claude: 3.5 Sonnet (Anthropic)"),
            ("claude-3-5-haiku-20241022", "Claude: 3.5 Haiku (Anthropic)"),
            ("qwen/qwen3.8-27b", "Groq: Qwen 3.8 (27B)"),
            ("deepseek-r1-distill-llama-70b", "Groq: DeepSeek R1 (70B)"),
            ("llama-3.3-70b-versatile", "Groq: Llama 3.3 (70B)"),
            ("llama-3.1-8b-instant", "Groq: Llama 3.1 (8B)"),
            ("mixtral-8x7b-32768", "Groq: Mixtral 8x7B"),
            ("gemma2-9b-it", "Groq: Gemma 2 (9B)"),
        ]
        for m_id, m_label in model_choices:
            self.model_combo.addItem(m_label, m_id)

        active_idx = 0
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == self.config.llm.model:
                active_idx = i
                break
        self.model_combo.setCurrentIndex(active_idx)
        self.model_combo.currentIndexChanged.connect(self._on_top_model_changed)
        self.model_badge = self.model_combo
        top_bar.addWidget(self.model_combo)

        # Status Pill
        self.status_pill = QLabel("READY")
        self.status_pill.setStyleSheet("""
            color: #10b981;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 0.6px;
            padding: 4px 10px;
            border-radius: 9px;
            background: #061a12;
            border: 1px solid #065f46;
        """)
        top_bar.addWidget(self.status_pill)

        # Real-time Context Window / Token meter pill
        self.context_meter = QLabel("Context: ~0")
        self.context_meter.setToolTip("Estimated context window token consumption (Click to Compact Memory)")
        self.context_meter.setCursor(Qt.PointingHandCursor)
        self.context_meter.mousePressEvent = lambda e: self._compact_conversation_memory()
        self.context_meter.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-size: 9px;
                font-weight: 700;
                font-family: Consolas, monospace;
                padding: 4px 8px;
                border-radius: 6px;
                background: #090912;
                border: 1px solid #1a1a2b;
            }
        """)
        top_bar.addWidget(self.context_meter)

        # Segmented Response Style Selector (Concise / Balanced / Deep)
        self._response_style = "balanced"
        self.style_frame = QFrame()
        self.style_frame.setStyleSheet("""
            QFrame {
                background-color: #080c16;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 1px;
            }
        """)
        style_layout = QHBoxLayout(self.style_frame)
        style_layout.setContentsMargins(2, 1, 2, 1)
        style_layout.setSpacing(2)

        self.style_btn_concise = QPushButton("Concise")
        self.style_btn_balanced = QPushButton("Balanced")
        self.style_btn_deep = QPushButton("Deep")

        for b, style_key in [(self.style_btn_concise, "concise"), (self.style_btn_balanced, "balanced"), (self.style_btn_deep, "deep")]:
            b.setFixedHeight(20)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, s=style_key: self._set_response_style(s))
            style_layout.addWidget(b)

        self._refresh_style_buttons()
        top_bar.addWidget(self.style_frame)

        top_bar.addStretch()

        # Hidden backwards-compatibility session_combo
        self.session_combo = QComboBox()
        self.session_combo.setVisible(False)

        # Sleek Action Button Styler helper
        btn_style = """
            QPushButton {
                background-color: #0e0e1a;
                color: #cbd5e1;
                border: 1px solid #1e1e30;
                border-radius: 6px;
                padding: 0 11px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1a1a2e;
                color: #ffffff;
                border-color: #6366f1;
            }
        """

        # Right Action Buttons
        self.api_btn = QPushButton("API Keys")
        self.api_btn.setToolTip("Configure Gemini, OpenAI, Claude, or Groq Keys")
        self.api_btn.setCursor(Qt.PointingHandCursor)
        self.api_btn.setFixedHeight(28)
        self.api_btn.setStyleSheet("""
            QPushButton {
                background-color: #0b1f1c;
                color: #34d399;
                border: 1px solid #065f46;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #064e3b;
                border-color: #10b981;
                color: #ffffff;
            }
        """)
        self.api_btn.clicked.connect(self._open_api_key_dialog)
        top_bar.addWidget(self.api_btn)

        # Retain references for compatibility
        self.skills_btn = QPushButton("Skills")
        self.git_btn = QPushButton("Git")
        self.terminal_btn = QPushButton("Terminal")

        # Unified Tools Dropdown Menu
        self.tools_menu_btn = QPushButton("Tools ▾")
        self.tools_menu_btn.setCursor(Qt.PointingHandCursor)
        self.tools_menu_btn.setFixedHeight(28)
        self.tools_menu_btn.setStyleSheet(btn_style)
        self._setup_tools_dropdown_menu()
        self.tools_menu_btn.clicked.connect(self._show_tools_dropdown_menu)
        top_bar.addWidget(self.tools_menu_btn)

        # Export Dropdown Menu
        self.export_menu_btn = QPushButton("Export ▾")
        self.export_menu_btn.setToolTip("Export conversation to Markdown, HTML, or Clipboard")
        self.export_menu_btn.setCursor(Qt.PointingHandCursor)
        self.export_menu_btn.setFixedHeight(28)
        self.export_menu_btn.setStyleSheet(btn_style)
        self._setup_export_dropdown_menu()
        self.export_menu_btn.clicked.connect(self._show_export_dropdown_menu)
        top_bar.addWidget(self.export_menu_btn)

        main_vbox.addLayout(top_bar)

        # Stacked Pages
        self.main_stack = QStackedWidget()

        # PAGE 0: Chat Console
        chat_page = QWidget()
        chat_vbox = QVBoxLayout(chat_page)
        chat_vbox.setContentsMargins(0, 0, 0, 0)
        chat_vbox.setSpacing(8)

        # Visual Drag & Drop Dropzone Overlay
        self.dropzone_overlay = QFrame(chat_page)
        self.dropzone_overlay.setVisible(False)
        self.dropzone_overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(7, 10, 18, 0.94);
                border: 2px dashed #38bdf8;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        dz_layout = QVBoxLayout(self.dropzone_overlay)
        dz_layout.setAlignment(Qt.AlignCenter)
        dz_layout.setSpacing(6)

        dz_title = QLabel("DROP FILES TO ATTACH")
        dz_title.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: 800; letter-spacing: 0.8px;")
        dz_title.setAlignment(Qt.AlignCenter)
        dz_layout.addWidget(dz_title)

        dz_sub = QLabel("Supports source code, data tables, text transcripts, and images")
        dz_sub.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
        dz_sub.setAlignment(Qt.AlignCenter)
        dz_layout.addWidget(dz_sub)

        # In-Chat Search Bar (Ctrl+F)
        self.search_bar = ChatSearchBar()
        self.search_bar.setVisible(False)
        self.search_bar.closed.connect(self._close_search)
        self.search_bar.search_changed.connect(self._on_search_query_changed)
        self.search_bar.navigate_next.connect(self._navigate_search_next)
        self.search_bar.navigate_prev.connect(self._navigate_search_prev)
        chat_vbox.addWidget(self.search_bar)

        # Scroll Area for Messages
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.message_container = QWidget()
        self.message_container.setStyleSheet("background: transparent;")
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(6)

        # Hero greeting card
        self.hero_widget = ChatHeroWidget(self.config.user_name, on_action=self._on_hero_action)
        self.message_layout.addWidget(self.hero_widget)
        self.message_layout.addStretch()
        self.scroll.setWidget(self.message_container)

        # Claude Artifacts Live Dual Pane Splitter
        self.chat_splitter = QSplitter(Qt.Horizontal)
        self.chat_splitter.setStyleSheet("QSplitter::handle { background: #1e2430; width: 2px; }")
        self.chat_splitter.addWidget(self.scroll)

        from ui.claude_artifacts_widget import ClaudeArtifactViewer
        self.claude_artifact_viewer = ClaudeArtifactViewer(self)
        self.claude_artifact_viewer.setVisible(False)
        self.claude_artifact_viewer.closed.connect(lambda: self.claude_artifact_viewer.setVisible(False))
        self.chat_splitter.addWidget(self.claude_artifact_viewer)
        self.chat_splitter.setSizes([600, 400])
        chat_vbox.addWidget(self.chat_splitter, 1)

        # Attachment preview bar
        self.attachment_preview = QLabel()
        self.attachment_preview.setVisible(False)
        self.attachment_preview.setStyleSheet(f"""
            color: {_ACCENT_CYAN};
            font-size: 11px;
            font-weight: 600;
            background: {_BG_PANEL};
            border: 1px solid {_BORDER};
            border-radius: 6px;
            padding: 4px 10px;
        """)
        chat_vbox.addWidget(self.attachment_preview)

        # Quick Command Action Strip
        action_strip = QFrame()
        action_strip.setStyleSheet("background: transparent; border: none;")
        strip_layout = QHBoxLayout(action_strip)
        strip_layout.setContentsMargins(4, 0, 4, 0)
        strip_layout.setSpacing(6)

        strip_pills = [
            ("PDF Report", lambda: self._send_quick_prompt("Generate an executive styled PDF report on: ")),
            ("Word Doc", lambda: self._send_quick_prompt("Create a professional Word document (.docx) covering: ")),
            ("AI Image", lambda: self._send_quick_prompt("Generate a high-resolution AI image of: ")),
            ("QR Code", lambda: self._send_quick_prompt("Generate a styled QR code for: ")),
            ("PowerPoint", lambda: self._send_quick_prompt("Create a PowerPoint presentation (.pptx) with slides on: ")),
            ("Deep Research", lambda: self._send_quick_prompt("Conduct deep autonomous web research and synthesize a report on: ")),
            ("PC Optimizer", lambda: self._send_quick_prompt("Optimize my system: clean temp, flush DNS, and trim memory.")),
            ("Excel Sheet", lambda: self._send_quick_prompt("Create an Excel spreadsheet with formulas for: ")),
            ("Interactive Chart", lambda: self._send_quick_prompt("Generate an interactive chart comparing: ")),
            ("Screen Vision", lambda: self._send_quick_prompt("Analyze my active screen and explain: ")),
            ("Prompt Library", self._open_prompt_library),
        ]

        for pill_label, pill_callback in strip_pills:
            p_btn = QPushButton(pill_label)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.setFixedHeight(24)
            p_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #0d0d16;
                    color: #94a3b8;
                    border: 1px solid {_BORDER};
                    border-radius: 12px;
                    padding: 0 12px;
                    font-size: 11px;
                    font-weight: 600;
                    white-space: nowrap;
                }}
                QPushButton:hover {{
                    background-color: #1a1a28;
                    color: {_ACCENT_CYAN};
                    border-color: {_ACCENT_CYAN};
                }}
            """)
            p_btn.clicked.connect(pill_callback)
            strip_layout.addWidget(p_btn)

        strip_layout.addStretch()

        action_scroll = QScrollArea()
        action_scroll.setFixedHeight(30)
        action_scroll.setWidgetResizable(True)
        action_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        action_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        action_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        action_scroll.setWidget(action_strip)
        chat_vbox.addWidget(action_scroll)

        # Input Card (Modern floating composer)
        input_card = QFrame()
        input_card.setObjectName("composer_card")
        input_card.setStyleSheet(f"""
            QFrame#composer_card {{
                background-color: #0d0d14;
                border: 1px solid #1f2030;
                border-radius: 12px;
            }}
            QFrame#composer_card:hover {{
                border-color: #2e3148;
            }}
        """)
        card_layout = QVBoxLayout(input_card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(6)

        # Text input field
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Message Nova AI... (Enter to send, Shift+Enter for new line)")
        self.input_edit.setMaximumHeight(95)
        self.input_edit.setMinimumHeight(44)
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                color: {_TEXT_MAIN};
                font-size: 13px;
                padding: 4px 6px;
                line-height: 1.4;
            }}
        """)
        self.input_edit.installEventFilter(self)
        self.input_edit.textChanged.connect(self._on_input_text_changed)
        card_layout.addWidget(self.input_edit)

        # Bottom controls row
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(2, 2, 2, 2)
        controls_row.setSpacing(6)

        # Plus / Attach button
        self.plus_btn = QPushButton()
        self.plus_btn.setIcon(create_attach_icon("#94a3b8", size=16))
        self.plus_btn.setToolTip("Attach File, Code, or Snip")
        self.plus_btn.setFixedSize(28, 28)
        self.plus_btn.setCursor(Qt.PointingHandCursor)
        self.plus_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: #38bdf8;
                background-color: #1e293b;
            }}
        """)
        self._setup_plus_menu()
        self.plus_btn.clicked.connect(self._show_plus_menu)
        controls_row.addWidget(self.plus_btn)

        # Mic Button
        self.mic_btn = QPushButton()
        self.mic_btn.setIcon(create_mic_icon("#94a3b8", size=16))
        self.mic_btn.setToolTip("Voice Typing (Click to Talk)")
        self.mic_btn.setFixedSize(28, 28)
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: #38bdf8;
                background-color: #1e293b;
            }}
        """)
        self.mic_btn.clicked.connect(self._on_single_shot_mic_clicked)
        controls_row.addWidget(self.mic_btn)

        # Animated Live Voice Waveform Equalizer
        self.voice_waveform = VoiceWaveformWidget()
        controls_row.addWidget(self.voice_waveform)

        # Real-time composer telemetry counter
        self.composer_stats_lbl = QLabel("")
        self.composer_stats_lbl.setStyleSheet("color: #475569; font-size: 10px; font-weight: 600; font-family: Consolas, monospace; padding-left: 4px;")
        controls_row.addWidget(self.composer_stats_lbl)

        controls_row.addStretch()

        # Send Button
        self.send_btn = QPushButton("Send ↑")
        self.send_btn.setFixedHeight(28)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #0284c7);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                padding: 0 16px;
                font-size: 11px;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4338ca, stop:1 #0369a1);
            }
        """)
        self.send_btn.clicked.connect(self._send_message)
        controls_row.addWidget(self.send_btn)

        # Prompt Refiner / Enhancer button
        self.refine_btn = QPushButton("Refine Prompt")
        self.refine_btn.setToolTip("Enhance and polish prompt draft into an expert prompt (Shift+Alt+E)")
        self.refine_btn.setFixedHeight(28)
        self.refine_btn.setCursor(Qt.PointingHandCursor)
        self.refine_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e1b4b;
                color: #c7d2fe;
                border: 1px solid #4338ca;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #312e81;
                border-color: #6366f1;
                color: #ffffff;
            }
        """)
        self.refine_btn.clicked.connect(self._refine_current_prompt)
        controls_row.addWidget(self.refine_btn)

        card_layout.addLayout(controls_row)

        self.slash_menu = _SlashCommandsMenuWidget(self)
        self.slash_menu.setVisible(False)
        self.slash_menu.command_selected.connect(self._on_slash_command_selected)
        chat_vbox.addWidget(self.slash_menu)

        chat_vbox.addWidget(input_card)

        self.main_stack.addWidget(chat_page)

        # PAGE 1: Tasks Hub View
        self.tasks_view = TasksView(self)
        self.main_stack.addWidget(self.tasks_view)

        # PAGE 2: Platform Connections View
        self.conn_view = ConnectionsView(self.config, self)
        self.main_stack.addWidget(self.conn_view)

        # PAGE 3: Central Admin Live Feed View
        self.feed_view = AdminFeedView(self)
        self.main_stack.addWidget(self.feed_view)

        # PAGE 4: Settings View
        self.settings_view = SettingsView(self.config, self)
        self.main_stack.addWidget(self.settings_view)

        main_vbox.addWidget(self.main_stack, 1)
        root.addWidget(main_content, 1)

        self._switch_nav(0)

    def _create_nav_button(self, text: str, index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.setStyleSheet(self._nav_btn_style(active=False))
        btn.clicked.connect(lambda: self._switch_nav(index))
        self.nav_btns.append(btn)
        return btn

    def _nav_btn_style(self, active: bool = False) -> str:
        if active:
            return """
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    border: 1px solid #38bdf8;
                    border-radius: 6px;
                    padding-left: 12px;
                    text-align: left;
                    font-size: 12px;
                    font-weight: 700;
                }
            """
        return """
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: 1px solid transparent;
                border-radius: 6px;
                padding-left: 12px;
                text-align: left;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1e293b;
                color: #ffffff;
            }
        """

    def _style_quick_button(self, btn: QPushButton, active: bool = False):
        if active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #032e22;
                    color: #6ee7b7;
                    border: 1px solid #059669;
                    border-radius: 5px;
                    font-size: 10px;
                    font-weight: 700;
                    text-align: left;
                    padding-left: 8px;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #111118;
                    color: #94a3b8;
                    border: 1px solid #1e293b;
                    border-radius: 5px;
                    font-size: 10px;
                    font-weight: 600;
                    text-align: left;
                    padding-left: 8px;
                }
                QPushButton:hover {
                    background-color: #1e293b;
                    color: #ffffff;
                }
            """)

    def _switch_nav(self, index: int):
        self.main_stack.setCurrentIndex(index)
        titles = [
            "Chat & Autonomous Code Console",
            "Autonomous Tasks & Automation Hub",
            "Platform Connections & Bot Integrations",
            "Central Admin Live Activity Feed",
            "Master System Settings",
        ]
        if index < len(titles):
            self.view_title.setText(titles[index])

        for i, b in enumerate(self.nav_btns):
            b.setStyleSheet(self._nav_btn_style(active=(i == index)))

    def _clear_conversation(self):
        # Remove all message bubbles except hero widget and stretch
        for i in reversed(range(self.message_layout.count())):
            item = self.message_layout.itemAt(i)
            if item and item.widget() and item.widget() != self.hero_widget:
                w = item.widget()
                self.message_layout.removeWidget(w)
                w.deleteLater()
        self.llm_manager.clear_history()
        db.clear_history(session_id=getattr(self, "_active_session_id", "default"))
        self._show_welcome_message()

    def _show_welcome_message(self):
        if self.hero_widget:
            self.hero_widget.setVisible(True)

    def _open_api_key_dialog(self):
        try:
            from ui.api_key_dialog import ApiKeyDialog
            dlg = ApiKeyDialog(self.config, self)
            if dlg.exec():
                self.show_toast(f"Active Provider: {self.config.llm.provider.upper()}", "SUCCESS")
                if hasattr(self, "status_pill"):
                    self.status_pill.setText("READY")
        except Exception:
            self._switch_nav(4)

    def _open_settings_dialog(self):
        self._switch_nav(4)

    def _open_connections_dialog(self):
        self._switch_nav(2)

    def _open_tasks_dialog(self):
        self._switch_nav(1)

    def _open_settings(self):
        self._switch_nav(4)

    def _send_quick_prompt(self, text: str):
        self.input_edit.setPlainText(text)
        self.input_edit.setFocus()
        cursor = self.input_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.input_edit.setTextCursor(cursor)

    def _style_header_button(self, btn: QPushButton, active: bool = False):
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #032e22;
                    color: #6ee7b7;
                    border: 1px solid #059669;
                    border-radius: 13px;
                    padding: 0 10px;
                    font-size: 10px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: #047857;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #111116;
                    color: {_TEXT_MUTED};
                    border: 1px solid {_BORDER};
                    border-radius: 13px;
                    padding: 0 10px;
                    font-size: 10px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    border-color: {_ACCENT_CYAN};
                    color: white;
                    background-color: #171720;
                }}
            """)

    def _setup_plus_menu(self):
        self.plus_menu = QMenu(self)
        self.plus_menu.setStyleSheet(f"""
            QMenu {{
                background-color: #121217;
                color: {_TEXT_MAIN};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {_ACCENT_BLUE};
                color: white;
            }}
        """)
        attach_act = QAction("Attach Source File or Image...", self)
        attach_act.triggered.connect(self._on_attach_file)
        self.plus_menu.addAction(attach_act)

        run_py_act = QAction("Run Python Script / File...", self)
        run_py_act.triggered.connect(self._on_run_python_file)
        self.plus_menu.addAction(run_py_act)

        snip_act = QAction("Snip Screen (Ctrl+Shift+D)", self)
        snip_act.triggered.connect(self.snipper.start_snip)
        self.plus_menu.addAction(snip_act)

        key_act = QAction("Configure Groq API Key...", self)
        key_act.triggered.connect(self._open_api_key_dialog)
        self.plus_menu.addAction(key_act)

        stats_act = QAction("Check System & Disks", self)
        stats_act.triggered.connect(lambda: self._quick_action("system_stats"))
        self.plus_menu.addAction(stats_act)

    def _on_run_python_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Python Script to Run", "", "Python Files (*.py);;All Files (*.*)"
        )
        if file_path:
            p = Path(file_path)
            code = p.read_text(encoding="utf-8")
            self._add_bubble("user", f"Run python file: `{p.name}`")
            self.status_pill.setText("RUNNING SCRIPT...")
            worker = _CodeRunnerWorker("python", code)
            def on_done(ok, msg):
                self.status_pill.setText("READY")
                self._add_bubble("assistant", f"**Execution Result ({p.name}):**\n```\n{msg}\n```")
            worker.finished_run.connect(on_done)
            worker.start()

    def _show_plus_menu(self):
        pos = self.plus_btn.mapToGlobal(QPoint(0, -self.plus_menu.sizeHint().height() - 4))
        self.plus_menu.exec(pos)

    def _setup_tools_dropdown_menu(self):
        """Unified clean tools menu dropdown (Find, Attach, Snip, Prompts, Artifacts, Export, Clear, Shortcuts)."""
        self._tools_menu = QMenu(self)
        self._tools_menu.setStyleSheet("""
            QMenu {
                background-color: #0b0b14;
                color: #e2e8f0;
                border: 1px solid #222238;
                border-radius: 8px;
                padding: 6px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 7px 20px 7px 10px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4f46e5;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #1e1e2f;
                margin: 4px 6px;
            }
        """)

        act_find = self._tools_menu.addAction("Find in Chat (Ctrl+F)")
        act_find.triggered.connect(self._toggle_search_bar)

        act_attach = self._tools_menu.addAction("Attach File Context (Ctrl+O)")
        act_attach.triggered.connect(self._on_attach_file)

        act_snip = self._tools_menu.addAction("Snip Desktop Screen (Ctrl+Shift+D)")
        act_snip.triggered.connect(self.snipper.start_snip)

        self._tools_menu.addSeparator()

        act_terminal = self._tools_menu.addAction("PowerShell Terminal (Ctrl+T)")
        act_terminal.triggered.connect(self._open_terminal_runner)

        act_git = self._tools_menu.addAction("Git Workspace Manager (Ctrl+G)")
        act_git.triggered.connect(self._open_git_manager)

        act_skills = self._tools_menu.addAction("Antigravity Skills (Ctrl+Shift+S)")
        act_skills.triggered.connect(self._open_skills_manager)

        self._tools_menu.addSeparator()

        act_prompts = self._tools_menu.addAction("Prompt Library (Ctrl+P)")
        act_prompts.triggered.connect(self._open_prompt_library)

        act_artifacts = self._tools_menu.addAction("Code Artifacts Drawer (Ctrl+B)")
        act_artifacts.triggered.connect(self._open_artifacts_drawer)

        act_export = self._tools_menu.addAction("Export Conversation (Ctrl+E)")
        act_export.triggered.connect(self._export_conversation)

        self._tools_menu.addSeparator()

        act_api = self._tools_menu.addAction("API Keys Setup (Gemini / OpenAI / Claude / Groq)")
        act_api.triggered.connect(self._open_api_key_dialog)

        act_clear = self._tools_menu.addAction("Clear Active Chat")
        act_clear.triggered.connect(self._clear_conversation)

        act_help = self._tools_menu.addAction("Keyboard Shortcuts (F1)")
        act_help.triggered.connect(self._show_shortcuts_dialog)

    def _show_tools_dropdown_menu(self):
        if hasattr(self, "_tools_menu") and hasattr(self, "tools_menu_btn"):
            pos = self.tools_menu_btn.mapToGlobal(self.tools_menu_btn.rect().bottomLeft())
            self._tools_menu.exec(pos)

    def _setup_export_dropdown_menu(self):
        """Dedicated quick-export dropdown menu (Markdown, HTML, Clipboard)."""
        self._export_menu = QMenu(self)
        self._export_menu.setStyleSheet("""
            QMenu {
                background-color: #0b0b14;
                color: #e2e8f0;
                border: 1px solid #222238;
                border-radius: 8px;
                padding: 6px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 7px 20px 7px 10px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4f46e5;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #1e1e2f;
                margin: 4px 6px;
            }
        """)
        act_md = self._export_menu.addAction("Export as Markdown (.md)")
        act_md.triggered.connect(self._export_markdown)

        act_html = self._export_menu.addAction("Export as Interactive HTML (.html)")
        act_html.triggered.connect(self._export_html)

        act_json = self._export_menu.addAction("Export as JSON Transcript (.json)")
        act_json.triggered.connect(self._export_json)

        self._export_menu.addSeparator()

        act_clip = self._export_menu.addAction("Copy Full Chat to Clipboard")
        act_clip.triggered.connect(self._copy_full_chat_to_clipboard)

    def _show_export_dropdown_menu(self):
        if hasattr(self, "_export_menu") and hasattr(self, "export_menu_btn"):
            pos = self.export_menu_btn.mapToGlobal(self.export_menu_btn.rect().bottomLeft())
            self._export_menu.exec(pos)

    def _export_markdown(self):
        recent = db.get_recent_history(limit=250, session_id=self._active_session_id)
        if not recent:
            self.show_toast("No messages to export", "WARNING")
            return
        lines = [
            f"# Nova AI Conversation Transcript",
            f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Session ID: `{self._active_session_id}`",
            f"- Model Engine: `{self.config.llm.model}`\n",
            "---",
            ""
        ]
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Nova AI"
            lines.append(f"### {role}\n\n{msg['content']}\n\n---\n")
        out_text = "\n".join(lines)

        dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Conversation Markdown", f"Nova_Chat_{dt_str}.md", "Markdown (*.md);;All Files (*.*)"
        )
        if file_path:
            try:
                Path(file_path).write_text(out_text, encoding="utf-8")
                self.show_toast(f"Exported to {Path(file_path).name}", "SUCCESS")
            except Exception as e:
                self.show_toast(f"Export error: {e}", "ERROR")

    def _export_html(self):
        recent = db.get_recent_history(limit=250, session_id=self._active_session_id)
        if not recent:
            self.show_toast("No messages to export", "WARNING")
            return
        dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Interactive HTML", f"Nova_Chat_{dt_str}.html", "Interactive HTML (*.html);;All Files (*.*)"
        )
        if file_path:
            try:
                html_content = _generate_chat_html(recent, self.config.llm.model)
                Path(file_path).write_text(html_content, encoding="utf-8")
                self.show_toast(f"Exported to {Path(file_path).name}", "SUCCESS")
            except Exception as e:
                self.show_toast(f"Export error: {e}", "ERROR")

    def _export_json(self):
        recent = db.get_recent_history(limit=500, session_id=self._active_session_id)
        if not recent:
            self.show_toast("No messages to export", "WARNING")
            return
        import json
        payload = {
            "session_id": self._active_session_id,
            "exported_at": datetime.now().isoformat(),
            "model": self.config.llm.model,
            "total_messages": len(recent),
            "messages": recent
        }
        dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON Transcript", f"Nova_Chat_{dt_str}.json", "JSON File (*.json);;All Files (*.*)"
        )
        if file_path:
            try:
                Path(file_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                self.show_toast(f"Exported to {Path(file_path).name}", "SUCCESS")
            except Exception as e:
                self.show_toast(f"Export error: {e}", "ERROR")

    def _copy_full_chat_to_clipboard(self):
        recent = db.get_recent_history(limit=250, session_id=self._active_session_id)
        if not recent:
            self.show_toast("No messages to copy", "WARNING")
            return
        lines = [f"# Nova AI Conversation Transcript ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"]
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Nova AI"
            lines.append(f"[{role}]:\n{msg['content']}\n")
        clipboard_text = "\n".join(lines)
        QApplication.clipboard().setText(clipboard_text, QClipboard.Clipboard)
        self.show_toast("Entire chat copied to clipboard!", "SUCCESS")

    def _refine_current_prompt(self):
        raw = self.input_edit.toPlainText().strip()
        if not raw:
            self.show_toast("Type a prompt draft first to refine it", "INFO")
            return
        if hasattr(self, "_refine_worker") and self._refine_worker and self._refine_worker.isRunning():
            return
        self.refine_btn.setEnabled(False)
        self.refine_btn.setText("Refining Prompt...")
        self.show_toast("Refining prompt draft with AI...", "SYSTEM")

        self._refine_worker = _PromptRefineWorker(self.llm_manager, raw)
        def on_refined(refined_text: str):
            self.refine_btn.setEnabled(True)
            self.refine_btn.setText("Refine Prompt")
            self.input_edit.setPlainText(refined_text)
            from PySide6.QtGui import QTextCursor
            c = self.input_edit.textCursor()
            c.movePosition(QTextCursor.End)
            self.input_edit.setTextCursor(c)
            self.input_edit.setFocus()
            self.show_toast("Prompt refined and structured!", "SUCCESS")

        def on_failed(err_msg: str):
            self.refine_btn.setEnabled(True)
            self.refine_btn.setText("Refine Prompt")
            structured = (
                f"{raw}\n\n"
                "Requirements & Guidelines:\n"
                "1. Provide a comprehensive, production-grade implementation with industry best practices.\n"
                "2. Include step-by-step reasoning, handle edge cases, and ensure clean error handling.\n"
                "3. Deliver concise, actionable outputs with full code snippets."
            )
            self.input_edit.setPlainText(structured)
            self.show_toast("Prompt structured with standard template", "INFO")

        self._refine_worker.refined.connect(on_refined)
        self._refine_worker.failed.connect(on_failed)
        self._refine_worker.start()

    def _update_context_meter(self):
        if not hasattr(self, "context_meter"):
            return
        cur_sid = getattr(self, "_active_session_id", "default")
        recent = db.get_recent_history(limit=250, session_id=cur_sid)
        total_chars = sum(len(m.get("content", "")) for m in recent)
        est_tokens = round(total_chars / 3.8)
        max_context = 1000000 if "gemini" in self.config.llm.model.lower() else 128000
        pct = (est_tokens / max_context) * 100
        tok_str = f"{est_tokens:,}" if est_tokens < 10000 else f"{est_tokens/1000:.1f}k"
        limit_str = "1M" if max_context == 1000000 else "128k"
        self.context_meter.setText(f"Context: {tok_str} / {limit_str} ({pct:.1f}%)")
        if pct > 40:
            self.context_meter.setStyleSheet("QLabel { color: #f59e0b; background: #1c1504; border: 1px solid #78350f; font-size: 9px; font-weight: 700; font-family: Consolas, monospace; padding: 4px 8px; border-radius: 6px; }")
        else:
            self.context_meter.setStyleSheet("QLabel { color: #64748b; background: #090912; border: 1px solid #1a1a2b; font-size: 9px; font-weight: 700; font-family: Consolas, monospace; padding: 4px 8px; border-radius: 6px; }")

    def _refresh_style_buttons(self):
        active_style = """
            QPushButton {
                background: #1e1b4b;
                color: #a5b4fc;
                border: 1px solid #4338ca;
                border-radius: 4px;
                font-size: 9px;
                font-weight: 700;
                padding: 0 6px;
            }
        """
        inactive_style = """
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                border-radius: 4px;
                font-size: 9px;
                font-weight: 600;
                padding: 0 6px;
            }
            QPushButton:hover {
                color: #cbd5e1;
                background: #0f172a;
            }
        """
        cur = getattr(self, "_response_style", "balanced")
        if hasattr(self, "style_btn_concise"):
            self.style_btn_concise.setStyleSheet(active_style if cur == "concise" else inactive_style)
            self.style_btn_balanced.setStyleSheet(active_style if cur == "balanced" else inactive_style)
            self.style_btn_deep.setStyleSheet(active_style if cur == "deep" else inactive_style)

    def _set_response_style(self, style: str):
        self._response_style = style
        self._refresh_style_buttons()
        desc = {
            "concise": "Concise (Direct answers & minimal preamble)",
            "balanced": "Balanced (Clear explanations & structured code)",
            "deep": "Deep & Exhaustive (Full implementations, tests & reasoning)"
        }.get(style, style)
        self.show_toast(f"Response style set to: {desc}", "STYLE")

    def _compact_conversation_memory(self):
        cur_sid = getattr(self, "_active_session_id", "default")
        recent = db.get_recent_history(limit=250, session_id=cur_sid)
        if len(recent) <= 4:
            self.show_toast("Context window is already compact", "INFO")
            return
        self.show_toast("Compacting conversation memory...", "SYSTEM")
        older = recent[:-3]
        summary_bubble = (
            f"**[Memory Compaction Summary - Archived {len(older)} turns]:**\n"
            f"- Prior discussions and context preserved.\n"
            f"- Context window refreshed to zero latency."
        )
        db.clear_history(session_id=cur_sid)
        db.add_message("assistant", summary_bubble, session_id=cur_sid)
        for m in recent[-3:]:
            db.add_message(m["role"], m["content"], session_id=cur_sid)
        self._clear_chat_bubbles()
        self._load_history()
        self._update_context_meter()
        self.show_toast("Conversation context compacted successfully!", "SUCCESS")

    def _apply_accent_theme(self, theme_key: str):
        theme = _THEME_PALETTES.get(theme_key.lower()) or _THEME_PALETTES["indigo"]
        self._current_theme_key = theme_key.lower()
        if hasattr(self, "send_btn") and self.send_btn.text() != "Stop":
            self.send_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {theme['primary']}, stop:1 {theme['accent']});
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    font-weight: 700;
                    padding: 0 16px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background: {theme['primary_hover']};
                }}
            """)
        if hasattr(self, "sidebar_new_btn"):
            self.sidebar_new_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme['badge_bg']};
                    color: {theme['badge_text']};
                    border: 1px solid {theme['badge_border']};
                    border-radius: 7px;
                    font-size: 11px;
                    font-weight: 700;
                    padding-left: 12px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {theme['primary']};
                    color: #ffffff;
                }}
            """)
        if hasattr(self, "refine_btn"):
            self.refine_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme['badge_bg']};
                    color: {theme['badge_text']};
                    border: 1px solid {theme['badge_border']};
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0 10px;
                }}
                QPushButton:hover {{
                    background-color: {theme['primary']};
                    color: #ffffff;
                }}
            """)

    def _refresh_session_combo(self, selected_id: str | None = None):
        target_id = selected_id or getattr(self, "_active_session_id", "default")
        sessions = db.get_all_sessions()

        if hasattr(self, "session_combo"):
            self.session_combo.blockSignals(True)
            self.session_combo.clear()
            active_index = 0
            for idx, sess in enumerate(sessions):
                self.session_combo.addItem(sess["title"], sess["id"])
                if sess["id"] == target_id:
                    active_index = idx
            self.session_combo.setCurrentIndex(active_index)
            self.session_combo.blockSignals(False)

        if hasattr(self, "session_list"):
            self.session_list.blockSignals(True)
            self.session_list.clear()
            active_row = 0
            for idx, sess in enumerate(sessions):
                title = sess.get("title") or f"Chat {sess['id'][:8]}"
                item = QListWidgetItem()
                item.setData(Qt.UserRole, sess["id"])
                is_cur = (sess["id"] == target_id)
                is_pinned = bool(sess.get("is_pinned", 0))
                widget = _SessionItemWidget(sess["id"], title, is_active=is_cur, is_pinned=is_pinned)
                widget.delete_requested.connect(self._delete_session)
                item.setSizeHint(widget.sizeHint())
                self.session_list.addItem(item)
                self.session_list.setItemWidget(item, widget)
                if is_cur:
                    active_row = idx
            if self.session_list.count() > 0:
                self.session_list.setCurrentRow(active_row)
            self.session_list.blockSignals(False)
            if hasattr(self, "session_search") and self.session_search.text().strip():
                self._filter_sessions(self.session_search.text())

    def _filter_sessions(self, query: str):
        query = (query or "").strip().lower()
        if not hasattr(self, "session_list"):
            return
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            w = self.session_list.itemWidget(item)
            if w and hasattr(w, "title"):
                match = (query in w.title.lower()) if query else True
                item.setHidden(not match)

    def _delete_session(self, session_id: str):
        reply = QMessageBox.question(
            self,
            "Delete Chat",
            "Are you sure you want to delete this chat session and its conversation history?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        db.delete_session(session_id)

        # If deleted active session, find next or create new
        if getattr(self, "_active_session_id", "default") == session_id:
            remaining = db.get_all_sessions()
            if remaining:
                next_id = remaining[0]["id"]
                self._active_session_id = next_id
                self._refresh_session_combo(selected_id=next_id)
                self._clear_chat_bubbles()
                self._load_history()
            else:
                self._create_new_session()
        else:
            self._refresh_session_combo()

        self.show_toast("Chat session deleted", "SESSION")

    def _show_session_context_menu(self, pos):
        item = self.session_list.itemAt(pos)
        if not item:
            return
        sid = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0d0d16;
                color: #e2e8f0;
                border: 1px solid #1e2030;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1e1b4b;
                color: #ffffff;
            }
        """)
        sess_data = db.get_session(sid)
        is_pinned = bool(sess_data.get("is_pinned", 0)) if sess_data else False
        act_pin = menu.addAction("📌 Unpin from Top" if is_pinned else "📌 Pin Chat to Top")
        act_pin.triggered.connect(lambda: self._toggle_pin_session(sid))

        act_rename = menu.addAction("✏ Rename Chat")
        act_rename.triggered.connect(lambda: self._rename_session(sid))

        act_del = menu.addAction("✕ Delete Chat")
        act_del.triggered.connect(lambda: self._delete_session(sid))

        act_new = menu.addAction("+ New Chat (Ctrl+N)")
        act_new.triggered.connect(self._create_new_session)

        menu.exec(self.session_list.mapToGlobal(pos))

    def _toggle_pin_session(self, session_id: str):
        if not session_id:
            return
        is_pin = db.toggle_pin_session(session_id)
        self._refresh_session_combo(selected_id=self._active_session_id)
        msg = "pinned to top" if is_pin else "unpinned"
        self.show_toast(f"Chat {msg}", "SESSION")

    def _rename_session(self, session_id: str):
        if not session_id:
            return
        sess = db.get_session(session_id)
        current_title = sess.get("title", "") if sess else ""
        from PySide6.QtWidgets import QInputDialog
        new_title, ok = QInputDialog.getText(
            self,
            "Rename Conversation",
            "Enter conversation title:",
            text=current_title
        )
        if ok and new_title.strip():
            db.rename_session(session_id, new_title.strip())
            self._refresh_session_combo(selected_id=self._active_session_id)
            self.show_toast(f"Renamed: {new_title.strip()}", "SESSION")

    def _on_session_item_double_clicked(self, item):
        if item:
            sid = item.data(Qt.UserRole)
            if sid:
                self._rename_session(sid)

    def _on_session_list_row_changed(self, row: int):
        if row < 0 or not hasattr(self, "session_list"):
            return
        item = self.session_list.item(row)
        if not item:
            return
        sid = item.data(Qt.UserRole)
        if sid and sid != getattr(self, "_active_session_id", "default"):
            self._switch_session(sid)

    def _on_session_combo_changed(self, index: int):
        if index < 0 or index >= self.session_combo.count():
            return
        sid = self.session_combo.itemData(index)
        if sid and sid != getattr(self, "_active_session_id", "default"):
            self._switch_session(sid)

    def _switch_session(self, session_id: str):
        self._active_session_id = session_id
        self._clear_chat_bubbles()
        self._load_history()
        if hasattr(self, "session_list"):
            for i in range(self.session_list.count()):
                it = self.session_list.item(i)
                w = self.session_list.itemWidget(it)
                if w and isinstance(w, _SessionItemWidget):
                    is_cur = (w.session_id == session_id)
                    w.title_lbl.setStyleSheet(
                        "color: #38bdf8; font-weight: 700; font-size: 11px;" if is_cur
                        else "color: #94a3b8; font-weight: 500; font-size: 11px;"
                    )
        sess = db.get_session(session_id)
        title = sess.get("title", "Session") if sess else "Session"
        self.show_toast(f"Switched session: {title}", "SESSION")

    def _create_new_session(self):
        sid = db.create_session("New Session")
        self._active_session_id = sid
        self._refresh_session_combo(selected_id=sid)
        self._clear_chat_bubbles()
        if self.hero_widget:
            self.hero_widget.setVisible(True)
        self.input_edit.clear()
        self.input_edit.setFocus()
        self.show_toast("Started fresh chat session (Ctrl+N)", "SESSION")

    def _clear_chat_bubbles(self):
        for i in reversed(range(self.message_layout.count())):
            item = self.message_layout.itemAt(i)
            if item and item.widget() and item.widget() != self.hero_widget:
                w = item.widget()
                self.message_layout.removeWidget(w)
                w.deleteLater()

    def _load_history(self):
        recent = db.get_recent_history(limit=50, session_id=getattr(self, "_active_session_id", "default"))
        if recent:
            if self.hero_widget:
                self.hero_widget.setVisible(False)
            for msg in recent:
                self._add_bubble(
                    msg["role"],
                    msg["content"],
                    message_id=msg.get("id"),
                    is_starred=msg.get("is_starred", False)
                )
        else:
            if self.hero_widget:
                self.hero_widget.setVisible(True)
        self._update_context_meter()

    def _on_suggestion_clicked(self, prompt: str):
        if prompt:
            self.input_edit.setPlainText(prompt)
            from PySide6.QtGui import QTextCursor
            c = self.input_edit.textCursor()
            c.movePosition(QTextCursor.End)
            self.input_edit.setTextCursor(c)
            self.input_edit.setFocus()
            self.show_toast("Suggestion loaded into prompt composer", "INFO")

    def _on_edit_user_message(self, text: str):
        if text:
            self.input_edit.setPlainText(text)
            from PySide6.QtGui import QTextCursor
            c = self.input_edit.textCursor()
            c.movePosition(QTextCursor.End)
            self.input_edit.setTextCursor(c)
            self.input_edit.setFocus()
            self.show_toast("Prompt loaded into composer for editing", "INFO")

    def _regenerate_response(self, bubble: _MessageBubble):
        if hasattr(self, "_llm_thread") and self._llm_thread and self._llm_thread.isRunning():
            self.show_toast("Generation already in progress", "WARNING")
            return
        if hasattr(self, "_super_agent_worker") and self._super_agent_worker and self._super_agent_worker.isRunning():
            self.show_toast("SuperAgent is currently running", "WARNING")
            return

        cur_sid = getattr(self, "_active_session_id", "default")
        recent = db.get_recent_history(limit=50, session_id=cur_sid)
        if not recent:
            return

        last_user_prompt = ""
        for m in reversed(recent):
            if m["role"] == "user":
                last_user_prompt = m["content"]
                break

        if not last_user_prompt:
            self.show_toast("No preceding user prompt found to regenerate", "WARNING")
            return

        db.delete_last_assistant_message(session_id=cur_sid)
        bubble.deleteLater()
        self.show_toast("Regenerating response...", "SYSTEM")
        self._send_message(override_prompt=last_user_prompt, is_regeneration=True)

    def _add_bubble(self, role: str, content: str = "", message_id: int | None = None, is_starred: bool = False) -> _MessageBubble:
        if self.hero_widget:
            self.hero_widget.setVisible(False)
        bubble = _MessageBubble(
            role,
            content,
            on_speak_clicked=self._speak_text,
            on_enable_vision_clicked=self.enable_screen_vision,
            on_suggestion_clicked=self._on_suggestion_clicked,
            on_regenerate_clicked=self._regenerate_response,
            on_edit_clicked=self._on_edit_user_message,
            message_id=message_id,
            is_starred=is_starred
        )
        self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)
        self._update_context_meter()
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
        return bubble

    def _add_action_badge(self, success: bool, message: str):
        tag = "[OK] Completed:" if success else "[FAIL] Notice:"
        badge = QLabel(f"{tag} {message}")
        color = _ACCENT_GREEN if success else _ACCENT_RED
        bg_color = "#03201a" if success else "#27070d"
        border_color = "#065f46" if success else "#991b1b"
        badge.setStyleSheet(f"""
            background-color: {bg_color};
            color: {color};
            border: 1px solid {border_color};
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
            margin: 2px 6px;
        """)
        self.message_layout.insertWidget(self.message_layout.count() - 1, badge)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _toggle_screen_vision(self):
        """Toggles background screen observing."""
        self.config.ui.screen_observing = not self.config.ui.screen_observing
        screen_observer.set_enabled(self.config.ui.screen_observing)
        self.screen_vision_btn.setText("Vision: ON" if self.config.ui.screen_observing else "Vision: OFF")
        self.screen_vision_btn.setIcon(create_screen_icon("#6ee7b7" if self.config.ui.screen_observing else "#94a3b8", size=14))
        self._style_header_button(self.screen_vision_btn, active=self.config.ui.screen_observing)
        save_config(self.config)
        log.info("Screen vision set to {}", self.config.ui.screen_observing)

    def enable_screen_vision(self, auto_capture: bool = True):
        """Explicitly enables screen vision, updates header controls, and captures screen."""
        self.config.ui.screen_observing = True
        screen_observer.set_enabled(True)
        self.screen_vision_btn.setText("Vision: ON")
        self.screen_vision_btn.setIcon(create_screen_icon("#6ee7b7", size=14))
        self._style_header_button(self.screen_vision_btn, active=True)
        save_config(self.config)
        log.info("Screen vision set to True")
        if auto_capture:
            shot_path, win_title = screen_observer.capture_now()
            self._add_action_badge(True, f"Screen Vision is now ON. Active Window: '{win_title}'.")

    def _open_tasks_dialog(self):
        self._switch_nav(1)
        self._update_tasks_btn_badge()

    def _on_resume_task_requested(self, task_id: str, prompt: str):
        self.input_edit.setText(prompt)
        self._send_message()

    def _update_tasks_btn_badge(self):
        try:
            active = db.get_active_agent_task()
            if active:
                tot = len(active.get("steps", []))
                cur = active.get("current_step", 0) + 1
                self.nav_tasks.setText(f"Tasks ({cur}/{tot})")
            else:
                self.nav_tasks.setText("Tasks Hub")
        except Exception:
            self.nav_tasks.setText("Tasks Hub")

    def _toggle_auto_speak(self):
        self.config.voice.auto_speak = not self.config.voice.auto_speak
        self.speak_toggle_btn.setText("Speech: ON" if self.config.voice.auto_speak else "Speech: OFF")
        self.speak_toggle_btn.setIcon(create_speaker_icon("#6ee7b7" if self.config.voice.auto_speak else "#94a3b8", size=14))
        self._style_header_button(self.speak_toggle_btn, active=self.config.voice.auto_speak)
        if not self.config.voice.auto_speak:
            tts.stop()
        save_config(self.config)

    def _toggle_hands_free_mode(self):
        """Toggles continuous hands-free voice loop in the background."""
        self._hands_free_active = not self._hands_free_active
        if self._hands_free_active:
            self.hands_free_btn.setText("Hands-Free: ON")
            self.hands_free_btn.setIcon(create_mic_icon("#6ee7b7", size=14))
            self._style_header_button(self.hands_free_btn, active=True)
            if hasattr(self, "voice_waveform"):
                self.voice_waveform.set_state("listening")
            self._start_continuous_listener()
        else:
            self.hands_free_btn.setText("Hands-Free: OFF")
            self.hands_free_btn.setIcon(create_mic_icon("#94a3b8", size=14))
            self._style_header_button(self.hands_free_btn, active=False)
            if hasattr(self, "voice_waveform"):
                self.voice_waveform.set_state("idle")
            self._stop_continuous_listener()

    def _start_continuous_listener(self):
        if self._continuous_thread and self._continuous_thread.isRunning():
            return

        self._continuous_thread = QThread()
        self._continuous_worker = ContinuousVoiceWorker(
            preferred_language=self.config.voice.stt_language
        )
        self._continuous_worker.moveToThread(self._continuous_thread)

        self._continuous_worker.status_changed.connect(lambda s: self.status_pill.setText(s.upper()))
        self._continuous_worker.speech_detected.connect(self._on_continuous_speech_detected)

        self._continuous_thread.started.connect(self._continuous_worker.run)
        self._continuous_thread.start()
        log.info("Continuous Hands-Free voice mode enabled.")

    def _stop_continuous_listener(self):
        if self._continuous_worker:
            self._continuous_worker.stop()
        if self._continuous_thread and self._continuous_thread.isRunning():
            self._continuous_thread.quit()
        self.status_pill.setText("READY")

    def _on_continuous_speech_detected(self, text: str):
        if not text:
            return
        if self._continuous_worker:
            self._continuous_worker.pause()

        self.input_edit.setText(text)
        self._send_message()

    def _on_single_shot_mic_clicked(self):
        """Single-shot recording when user clicks the Mic button."""
        if self._single_shot_thread and self._single_shot_thread.isRunning():
            return

        self.mic_btn.setText("Listening...")
        self.status_pill.setText("SPEAK NOW...")
        if hasattr(self, "voice_waveform"):
            self.voice_waveform.set_state("listening")

        self._single_shot_thread = QThread()
        self._single_shot_worker = SingleShotVoiceWorker(
            preferred_language=self.config.voice.stt_language,
            record_seconds=5
        )
        self._single_shot_worker.moveToThread(self._single_shot_thread)

        def on_transcribed(text: str):
            self.input_edit.setText(text)
            self._send_message()

        def on_done():
            self.mic_btn.setText("Listen")
            self.status_pill.setText("READY")
            if hasattr(self, "voice_waveform"):
                state = "listening" if (self._continuous_worker and self._hands_free_active) else "idle"
                self.voice_waveform.set_state(state)

        self._single_shot_worker.transcription_ready.connect(on_transcribed)
        self._single_shot_worker.error_occurred.connect(lambda err: self.status_pill.setText(err.upper()))
        self._single_shot_worker.finished.connect(on_done)

        self._single_shot_thread.started.connect(self._single_shot_worker.run)
        self._single_shot_worker.finished.connect(self._single_shot_thread.quit)
        self._single_shot_worker.finished.connect(self._single_shot_worker.deleteLater)
        self._single_shot_thread.finished.connect(self._single_shot_thread.deleteLater)
        self._single_shot_thread.start()

    def _speak_text(self, text: str, on_done=None):
        self.status_pill.setText("SPEAKING...")
        if hasattr(self, "voice_waveform"):
            self.voice_waveform.set_state("speaking")
        if self._continuous_worker and self._hands_free_active:
            self._continuous_worker.pause()

        voice = self.config.voice.tts_voice_ur if is_urdu_text(text) else self.config.voice.tts_voice_en

        def on_speech_ended():
            self.status_pill.setText("READY")
            if hasattr(self, "voice_waveform"):
                state = "listening" if (self._continuous_worker and self._hands_free_active) else "idle"
                self.voice_waveform.set_state(state)
            if self._continuous_worker and self._hands_free_active:
                self._continuous_worker.resume()
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass

        tts.speak(text, voice=voice, on_finished=on_speech_ended)

    def _on_region_snipped(self, image_path: str):
        self._attached_path = Path(image_path)
        self.attachment_preview.setText(f"[Attached: {self._attached_path.name}]")
        self.attachment_preview.setVisible(True)

    def _process_attached_file(self, p: Path):
        img_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        if p.suffix.lower() in img_exts:
            self._attached_path = p
            self.attachment_preview.setText(f"[Attached Image: {p.name}]")
            self.attachment_preview.setVisible(True)
            self.show_toast(f"Attached image for vision: {p.name}", "VISION")
        else:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                if len(content) > 40000:
                    content = content[:40000] + "\n...[Content truncated: file exceeds 40KB]..."
                ext = p.suffix.lstrip(".") or "txt"
                snippet = f"\n\n[Attached File: {p.name} ({len(lines)} lines)]\n```{ext}\n{content}\n```\n"
                cur = self.input_edit.toPlainText().strip()
                if cur:
                    self.input_edit.setText(f"{cur}\n{snippet}")
                else:
                    self.input_edit.setText(snippet.strip() + "\n\nAnalyze this file and ")
                self.input_edit.setFocus()
                self.show_toast(f"Injected {p.name} into prompt context", "CODE")
            except Exception as e:
                self.show_toast(f"Unable to read file: {e}", "WARNING")

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Attach Code, Logs, Data, or Image Context",
            "",
            "All Supported (*.py *.js *.ts *.html *.css *.json *.txt *.md *.log *.csv *.png *.jpg *.jpeg *.webp);;Code & Text (*.py *.js *.ts *.html *.css *.json *.txt *.md *.log *.csv *.bat *.ps1 *.sql);;Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*.*)"
        )
        if not file_path:
            return
        self._process_attached_file(Path(file_path))

    def _quick_action(self, action_name: str, arg: str = ""):
        self.input_edit.setText(f"Execute {action_name} {arg}".strip())
        self._send_message()

    def _clear_chat(self):
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        db.clear_history()

    def _open_settings(self):
        self._switch_nav(4)

    def _reset_send_button(self):
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_ACCENT_BLUE};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                padding: 0 16px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #1d4ed8;
            }}
        """)

    def _send_message(self, prefix: str = "", override_prompt: str = "", is_regeneration: bool = False):
        # If currently streaming, SuperAgent or Swarm running, clicking Stop aborts cleanly
        if self._llm_thread and self._llm_thread.isRunning():
            self._llm_thread.cancel()
            self._reset_send_button()
            self.status_pill.setText("READY")
            return
        if hasattr(self, "_super_agent_worker") and self._super_agent_worker and self._super_agent_worker.isRunning():
            self._super_agent_worker.cancel()
            self._reset_send_button()
            self.status_pill.setText("READY")
            self.show_toast("SuperAgent stopped by user", "SYSTEM")
            return
        if hasattr(self, "_swarm_worker") and self._swarm_worker and self._swarm_worker.isRunning():
            self._swarm_worker.cancel()
            self._reset_send_button()
            self.status_pill.setText("READY")
            self.show_toast("Swarm stopped by user", "SYSTEM")
            return

        if override_prompt:
            text = override_prompt.strip()
        else:
            text = self.input_edit.toPlainText().strip()
            if prefix:
                text = f"{prefix} {text}".strip()

        screen_context_path = None
        active_window_title = ""
        if self.config.ui.screen_observing and not self._attached_path:
            shot_path, win_title = screen_observer.capture_now()
            if shot_path and shot_path.exists():
                screen_context_path = shot_path
                active_window_title = win_title

        if not text and not self._attached_path and not screen_context_path:
            return

        image_path_to_send = self._attached_path or screen_context_path
        self._attached_path = None
        self.attachment_preview.setVisible(False)
        if not is_regeneration:
            self.input_edit.clear()

        # Handle instant slash commands without external API delay
        if text.startswith("/") and not image_path_to_send:
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd in ("/otp", "/2fa"):
                service = arg or "google"
                self._add_bubble("user", text)
                cur_sid = getattr(self, "_active_session_id", "default")
                db.add_message("user", text, session_id=cur_sid)
                from automation.actions import action_get_email_otp
                res_text = action_get_email_otp(service)
                b = self._add_bubble("assistant", res_text)
                b.set_meta(datetime.now().strftime("%I:%M %p"), 0.02, "Security Shield")
                db.add_message("assistant", res_text, session_id=cur_sid)
                return

            if cmd in ("/accounts", "/scan", "/webaccounts"):
                self._add_bubble("user", text)
                cur_sid = getattr(self, "_active_session_id", "default")
                db.add_message("user", text, session_id=cur_sid)
                from automation.actions import action_scan_web_accounts
                res_text = action_scan_web_accounts("")
                b = self._add_bubble("assistant", res_text)
                b.set_meta(datetime.now().strftime("%I:%M %p"), 0.05, "Account Discovery")
                db.add_message("assistant", res_text, session_id=cur_sid)
                return

            if cmd in ("/clean", "/optimize"):
                self._add_bubble("user", text)
                cur_sid = getattr(self, "_active_session_id", "default")
                db.add_message("user", text, session_id=cur_sid)
                from automation.actions import action_optimize_system
                res_text = action_optimize_system("")
                b = self._add_bubble("assistant", res_text)
                b.set_meta(datetime.now().strftime("%I:%M %p"), 0.02, "PC Optimizer")
                db.add_message("assistant", res_text, session_id=cur_sid)
                if hasattr(self, "system_pulse"):
                    self.system_pulse._on_boost_clicked()
                return

            if cmd == "/rename":
                cur_sid = getattr(self, "_active_session_id", "default")
                if arg:
                    db.rename_session(cur_sid, arg)
                    self._refresh_session_combo(selected_id=cur_sid)
                    self.show_toast(f"Renamed: {arg}", "SESSION")
                else:
                    self._rename_session(cur_sid)
                return

            if cmd == "/clear":
                self._clear_conversation()
                db.clear_history()
                self.show_toast("Conversation memory cleared", "SYSTEM")
                return

            if cmd == "/export":
                self._export_conversation()
                return

            if cmd == "/palette":
                self._open_command_palette()
                return

            if cmd in ("/shortcuts", "/keys", "/hotkeys"):
                self._show_shortcuts_dialog()
                return

            if cmd == "/find":
                if not arg:
                    self.show_toast("Usage: /find <keyword to search across all chats>", "INFO")
                    return
                matches = db.search_all_sessions(arg, limit=15)
                cur_sid = getattr(self, "_active_session_id", "default")
                if not matches:
                    self._add_bubble("user", text)
                    db.add_message("user", text, session_id=cur_sid)
                    b = self._add_bubble("assistant", f"No messages matching '{arg}' were found in any saved sessions.")
                    b.set_meta(datetime.now().strftime("%I:%M %p"), 0.01, "Global Search")
                    db.add_message("assistant", f"No messages matching '{arg}' were found in any saved sessions.", session_id=cur_sid)
                    return
                lines = [f"**Global Search Results for '{arg}' ({len(matches)} matches):**\n"]
                for m in matches:
                    role_str = "You" if m["role"] == "user" else "Nova"
                    snippet = m["content"].replace("\n", " ").strip()
                    if len(snippet) > 120:
                        snippet = snippet[:120] + "..."
                    time_str = m.get("timestamp", "")
                    s_title = m.get("session_title", "Main Workspace")
                    lines.append(f"- **[{s_title}]** *{role_str}* ({time_str}): {snippet}")
                out_msg = "\n".join(lines)
                self._add_bubble("user", text)
                db.add_message("user", text, session_id=cur_sid)
                b = self._add_bubble("assistant", out_msg)
                b.set_meta(datetime.now().strftime("%I:%M %p"), 0.02, "Global Search")
                db.add_message("assistant", out_msg, session_id=cur_sid)
                return

            if cmd in ("/starred", "/bookmarks", "/favorites"):
                starred = db.get_starred_messages(limit=30)
                cur_sid = getattr(self, "_active_session_id", "default")
                if not starred:
                    self._add_bubble("user", text)
                    db.add_message("user", text, session_id=cur_sid)
                    b = self._add_bubble("assistant", "You have not starred any responses yet. Click 'Star' on any assistant message to bookmark it.")
                    b.set_meta(datetime.now().strftime("%I:%M %p"), 0.01, "Bookmarks")
                    db.add_message("assistant", "You have not starred any responses yet. Click 'Star' on any assistant message to bookmark it.", session_id=cur_sid)
                    return
                lines = [f"**Starred & Bookmarked Responses ({len(starred)} items):**\n"]
                for s in starred:
                    snip = s["content"].replace("\n", " ").strip()
                    if len(snip) > 130:
                        snip = snip[:130] + "..."
                    t_str = s.get("timestamp", "")
                    s_title = s.get("session_title", "Main Workspace")
                    lines.append(f"- **[{s_title}]** ({t_str}): {snip}")
                out_msg = "\n".join(lines)
                self._add_bubble("user", text)
                db.add_message("user", text, session_id=cur_sid)
                b = self._add_bubble("assistant", out_msg)
                b.set_meta(datetime.now().strftime("%I:%M %p"), 0.02, "Bookmarks")
                db.add_message("assistant", out_msg, session_id=cur_sid)
                return

            if cmd == "/theme":
                keys = list(_THEME_PALETTES.keys())
                if arg and arg.lower() in _THEME_PALETTES:
                    tgt = arg.lower()
                else:
                    cur = getattr(self, "_current_theme_key", "indigo")
                    next_idx = (keys.index(cur) + 1) % len(keys) if cur in keys else 0
                    tgt = keys[next_idx]
                self._apply_accent_theme(tgt)
                theme_name = _THEME_PALETTES[tgt]["name"]
                self.show_toast(f"Theme switched to: {theme_name}", "THEME")
                return

            if cmd == "/refine":
                if arg:
                    self.input_edit.setPlainText(arg)
                self._refine_current_prompt()
                return

            if cmd == "/compact":
                self._compact_conversation_memory()
                return

            if cmd in ("/sys", "/status", "/diagnostics"):
                cpu_pct, ram_pct, ram_used, ram_total = _get_live_telemetry()
                diag_text = (
                    f"**Nova AI System Diagnostics:**\n\n"
                    f"- **Active LLM Engine:** `{self.config.llm.model}`\n"
                    f"- **CPU Utilization:** `{cpu_pct}%`\n"
                    f"- **Physical Memory:** `{ram_used:.1f} GB / {ram_total:.1f} GB ({ram_pct}%)`\n"
                    f"- **Voice Output:** `{'Active' if self.config.voice.enabled else 'Disabled'}`\n"
                    f"- **Screen Vision:** `{'Active' if self.config.ui.screen_observing else 'Standby'}`\n"
                    f"- **Runtime Workspace:** `E:\\Nova_AI`"
                )
                self._add_bubble("user", text)
                b = self._add_bubble("assistant", diag_text)
                b.set_meta(datetime.now().strftime("%I:%M %p"), 0.01, self.config.llm.model)
                db.add_message("user", text)
                db.add_message("assistant", diag_text)
                self.show_toast("System diagnostics telemetry refreshed", "SYSTEM")
                return

            if cmd == "/model":
                if arg:
                    idx = self._find_model_index(arg)
                    if idx >= 0:
                        self.model_combo.setCurrentIndex(idx)
                    else:
                        self.show_toast(f"Model not found: {arg}", "WARNING")
                else:
                    self.show_toast(f"Active Model: {self.config.llm.model}", "MODEL")
                return

            if cmd in ("/term", "/terminal"):
                self._open_terminal_runner()
                return

            if cmd == "/mode":
                if arg:
                    idx = self._find_mode_index(arg)
                    if idx >= 0:
                        self._on_mode_changed(idx)
                    else:
                        self.show_toast(f"Mode not found: {arg}. Available: engineer, research, sysadmin, superagent, general", "WARNING")
                else:
                    self.show_toast(f"Active Mode: {self._operating_mode}", "SYSTEM")
                return

            if cmd in ("/prompts", "/templates"):
                self._open_prompt_library()
                return

            if cmd in ("/artifacts", "/scripts"):
                self._open_artifacts_drawer()
                return

            if cmd in ("/new", "/newchat"):
                self._create_new_session()
                return

            if cmd in ("/session", "/sessions"):
                sess_list = db.get_all_sessions()
                lines = ["**Active Chat Sessions & Threads:**\n"]
                cur_id = getattr(self, "_active_session_id", "default")
                for s in sess_list:
                    marker = "[ACTIVE] " if s["id"] == cur_id else "- "
                    lines.append(f"{marker}**{s['title']}** (`{s['id']}`)")
                sess_text = "\n".join(lines)
                self._add_bubble("user", text)
                b = self._add_bubble("assistant", sess_text)
                b.set_meta(datetime.now().strftime("%I:%M %p"), 0.01, self.config.llm.model)
                return

            if cmd in ("/attach", "/file"):
                self._on_attach_file()
                return

            if cmd in ("/git", "/repo"):
                self._open_git_manager()
                return

            if cmd in ("/super", "/agent", "/goal"):
                if arg:
                    self._add_bubble("user", text)
                    cur_sid = getattr(self, "_active_session_id", "default")
                    db.add_message("user", text, session_id=cur_sid)
                    self._launch_super_agent(arg)
                else:
                    self.show_toast("Usage: /super <goal to accomplish>", "WARNING")
                return

            if cmd in ("/teamwork", "/swarm"):
                if arg:
                    self._add_bubble("user", text)
                    cur_sid = getattr(self, "_active_session_id", "default")
                    db.add_message("user", text, session_id=cur_sid)
                    self._launch_swarm(arg)
                else:
                    self.show_toast("Usage: /teamwork <goal for multi-agent swarm>", "WARNING")
                return

            if cmd in ("/skills", "/skill"):
                self._open_skills_manager()
                return

            if cmd == "/compact":
                cur_sid = getattr(self, "_active_session_id", "default")
                recent = db.get_recent_history(limit=25, session_id=cur_sid)
                if not recent:
                    self.show_toast("No messages in active session to compact", "SYSTEM")
                    return
                compact_prompt = (
                    "Summarize the key facts, decisions, and technical context from this conversation thread into a dense, highly structured reference brief:\n\n"
                    + "\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)
                )
                try:
                    compact_result = self.llm_manager.query_sync(
                        user_prompt=compact_prompt,
                        system_prompt="You are an expert context archivist. Compress context with zero fluff and zero emojis.",
                    )
                    db.add_message("system", f"[Antigravity Compacted Context Brief]\n{compact_result}", session_id=cur_sid)
                    self._add_bubble("user", "/compact")
                    b = self._add_bubble("assistant", f"**Antigravity Context Compacted Successfully:**\n\n{compact_result}")
                    b.set_meta(datetime.now().strftime("%I:%M %p"), 0.05, self.config.llm.model)
                    self.show_toast("Session context compacted into reference brief", "SUCCESS")
                except Exception as ex:
                    self.show_toast(f"Context compaction failed: {ex}", "ERROR")
                return

            if cmd == "/help":
                help_text = (
                    f"**Nova AI Studio — Quick Command Reference:**\n\n"
                    f"- `/teamwork <goal>` — Launch Antigravity Multi-Agent Swarm (Researcher, Architect, Verifier).\n"
                    f"- `/super <goal>` — Launch Autonomous Base44-grade SuperAgent Loop.\n"
                    f"- `/skills` — Open Antigravity Skills & Extensions Manager (`Ctrl+Shift+S`).\n"
                    f"- `/plan <goal>` — Dynamic Step-by-Step Execution Planner with Live Steps HUD.\n"
                    f"- `/boost <query>` — High-Intensity Deep Reasoning & Verification Mode.\n"
                    f"- `/compact` — Compress active conversation history into a dense reference brief.\n"
                    f"- `/new` — Start a fresh, isolated chat session (`Ctrl+N`).\n"
                    f"- `/sessions` — List all active and archived conversation threads.\n"
                    f"- `/attach` — Attach code, logs, data or image context (`Ctrl+O`).\n"
                    f"- `/git` — Open Git Workspace Manager (`Ctrl+G`).\n"
                    f"- `/clear` — Wipe active conversation and reset context memory.\n"
                    f"- `/export` — Save conversation logs to a clean Markdown (.md) or HTML file.\n"
                    f"- `/palette` — Open the Spotlight Command Palette (`Ctrl+K`).\n"
                    f"- `/term` — Launch Quick Embedded PowerShell Console (`Ctrl+T`).\n"
                    f"- `/mode <name>` — Switch Persona (`engineer`, `research`, `sysadmin`, `superagent`, `general`).\n"
                    f"- `/prompts` — Open Prompt & Workflow Library (`Ctrl+P`).\n"
                    f"- `/artifacts` — Open Code Artifacts & Script Drawer (`Ctrl+B`).\n"
                    f"- `/sys` — Display instant Win32 CPU, RAM & engine telemetry.\n"
                    f"- `Ctrl+Shift+S` — Antigravity Skills Manager.\n"
                    f"- `Ctrl+N` — New Chat Session.\n"
                    f"- `Ctrl+O` — Attach File / Code Context.\n"
                    f"- `Ctrl+G` — Git Workspace Manager.\n"
                    f"- `Ctrl+K` — Open Command Palette anywhere.\n"
                    f"- `Ctrl+T` — Quick Terminal Runner.\n"
                    f"- `Ctrl+P` — Prompt Library.\n"
                    f"- `Ctrl+B` — Artifacts Drawer."
                )
                self._add_bubble("user", text)
                b = self._add_bubble("assistant", help_text)
                b.set_meta(datetime.now().strftime("%I:%M %p"), 0.01, self.config.llm.model)
                cur_sid = getattr(self, "_active_session_id", "default")
                db.add_message("user", text, session_id=cur_sid)
                db.add_message("assistant", help_text, session_id=cur_sid)
                return

            if cmd == "/plan" and arg:
                text = f"[Antigravity Dynamic Planner] Create a structured step-by-step milestone execution plan using [action:update_steps:...] and [action:update_focus:...] for: {arg}"
            elif cmd == "/boost" and arg:
                text = f"[Antigravity Boost Mode] Perform exhaustive multi-angle analysis, verify all assumptions, check edge cases, and provide a verified solution for: {arg}"
            elif cmd == "/task" and arg:
                text = f"[Schedule Task] {arg}"
            elif cmd == "/research" and arg:
                text = f"[Deep Research] Perform comprehensive web research on: {arg}"
            elif cmd == "/code" and arg:
                text = f"[Code Architecture] Write complete, robust production code for: {arg}"

        # Record prompt into history for Up/Down arrow navigation
        if text and not text.startswith("/"):
            if not self._prompt_history or self._prompt_history[-1] != text:
                self._prompt_history.append(text)
        self._prompt_history_idx = -1

        # Autonomous SuperAgent Mode dispatch
        if getattr(self, "_operating_mode", "ENGINEER") == "SUPERAGENT" and not text.startswith("/"):
            bubble_text = text or "[Attached Screen Context]"
            if image_path_to_send:
                bubble_text = f"{bubble_text}\n[Image: {image_path_to_send}]"
            self._add_bubble("user", bubble_text)
            cur_sid = getattr(self, "_active_session_id", "default")
            db.add_message("user", bubble_text, session_id=cur_sid)
            self._launch_super_agent(text)
            return

        if not is_regeneration:
            # Add User bubble
            bubble_text = text or "[Attached Screen Context]"
            if image_path_to_send:
                bubble_text = f"{bubble_text}\n[Image: {image_path_to_send}]"
            self._add_bubble("user", bubble_text)
            cur_sid = getattr(self, "_active_session_id", "default")
            db.add_message("user", bubble_text, session_id=cur_sid)
        else:
            cur_sid = getattr(self, "_active_session_id", "default")

        # Smart Auto-Title for fresh conversations on first prompt
        if cur_sid != "default":
            try:
                sess_meta = db.get_session(cur_sid)
                if sess_meta and sess_meta.get("title", "") in ("New Session", "Session", "Untitled Session"):
                    clean_first = re.sub(r"[^\w\s]", "", text).strip()
                    words = clean_first.split()
                    if words:
                        smart_title = " ".join(words[:4]).capitalize()
                        if len(smart_title) > 28:
                            smart_title = smart_title[:28] + "..."
                        db.rename_session(cur_sid, smart_title)
                        self._refresh_session_combo(selected_id=cur_sid)
            except Exception:
                pass

        # Prepare Chat Messages
        history: list[ChatMessage] = []
        for msg in db.get_recent_history(limit=10, session_id=cur_sid):
            history.append(ChatMessage(role=msg["role"], content=msg["content"]))

        # Attach image to the latest user message for vision
        if image_path_to_send and history and history[-1].role == "user":
            history[-1].image_path = str(image_path_to_send)

        # Use latest cloud-synced system prompt (with offline built-in fallback)
        active_template = remote_sync.get_active_system_prompt(fallback=SYSTEM_PROMPT_TEMPLATE)
        system_prompt = active_template.format(name=self.config.ui.assistant_name)

        # Live Desktop Observation & Screen Vision Context
        if self.config.ui.screen_observing:
            open_wins = get_open_windows()
            wins_str = ", ".join(f"'{w}'" for w in open_wins) if open_wins else "Desktop"
            system_prompt += (
                f"\n[Screen Vision: ON]\n"
                f"- Active Foreground Window: '{active_window_title or 'Desktop'}'\n"
                f"- Open Application Windows: {wins_str}\n"
                f"- Screen observation is active and screenshot is attached. Inspect the screen and use visual desktop actions directly.\n"
            )
        else:
            system_prompt += (
                "\n[Screen Vision: OFF]\n"
                "- Screen Vision is currently OFF.\n"
                "- If the user asks you to interact with apps, websites, buttons, or perform GUI desktop tasks, DO NOT run black console PowerShell scripts! Instead, politely ask the user to turn on Screen Share / Screen Vision (or click the 'Turn On Screen Vision' button) and include [action:enable_vision] in your response.\n"
            )

        active_task = db.get_active_agent_task()
        if active_task:
            steps_preview = " -> ".join(active_task.get("steps", []))
            system_prompt += (
                f"\n[Active Agent Task in Progress]\n"
                f"- Task ID: {active_task['id']}\n"
                f"- Title: {active_task['title']}\n"
                f"- Current Step: Step {active_task['current_step'] + 1} of {len(active_task.get('steps', []))}\n"
                f"- Milestone Steps: {steps_preview}\n"
            )

        facts = db.get_all_facts()
        if facts:
            system_prompt += "\nUser Facts:\n" + "\n".join(f"- {f}" for f in facts)

        # Response Style Directive (Concise / Balanced / Deep)
        cur_style = getattr(self, "_response_style", "balanced")
        if cur_style == "concise":
            system_prompt += (
                "\n[Response Directive: CONCISE]\n"
                "- Deliver direct, ultra-concise answers with essential code only. Omit introductory chit-chat, conversational preamble, and verbose explanations.\n"
            )
        elif cur_style == "deep":
            system_prompt += (
                "\n[Response Directive: DEEP & EXHAUSTIVE]\n"
                "- Deliver an exhaustive, production-grade response. Detail architectural trade-offs, step-by-step reasoning, handle edge cases, include unit test cases, and ensure robust error handling.\n"
            )
        else:
            system_prompt += (
                "\n[Response Directive: BALANCED]\n"
                "- Deliver clear explanations, structured sections, complete code snippets, and key takeaways.\n"
            )

        # Operating Persona Steering
        mode = getattr(self, "_operating_mode", "ENGINEER")
        if mode == "GEMINI":
            system_prompt += (
                "\n[Operating Mode: Google Gemini 2.0 & Multimodal Intelligence]\n"
                "- You possess the extreme speed, multimodal perception, and 2M context synthesis of Google Gemini 2.0.\n"
                "- Multimodal Vision: Analyze active desktop screenshots, user images, UI elements, documents, and camera inputs with pixel-perfect precision.\n"
                "- Google Search Grounding: For real-time news, current events, latest documentation, or factual verification, utilize [action:web_search:query] or [action:fetch_webpage:url] to retrieve live, grounded sources.\n"
                "- Interactive Canvas & Charts: Execute [action:generate_chart:Title|type|labels|values] for visual metrics and generate interactive HTML5 applications inside ```html ``` code blocks.\n"
                "- Speed & Conciseness: Provide lightning-fast, structured, and factual answers. Zero emojis.\n"
            )
        elif mode == "CHATGPT":
            system_prompt += (
                "\n[Operating Mode: ChatGPT 4o & Advanced Data Analyst]\n"
                "- You possess the full intelligence, speed, and analytical power of OpenAI ChatGPT 4o.\n"
                "- Advanced Data Analysis & Charting: When the user asks for charts, plots, data analysis, or metrics, execute [action:generate_chart:Title|type|labels|values] or [action:generate_chart:{\"title\": \"...\", \"type\": \"bar|line|pie\", \"labels\": [...], \"datasets\": [...]}] to produce an interactive visual dashboard.\n"
                "- Excel & Documents: When asked for spreadsheets, execute [action:create_excel:filename.xlsx|{\"Sheet1\": [[\"A\",\"B\"], [1,2]]}] directly.\n"
                "- Interactive Canvas & Web Apps: When writing web applications, dashboards, or calculators, output full HTML/CSS/JS inside ```html ``` code blocks for live Chromium preview.\n"
                "- Rich Formatting: Format tabular data with clean markdown tables. Use clear headings, LaTeX math when appropriate, and crisp executive takeaways.\n"
                "- Zero fluff, extreme precision, production-ready code. Zero emojis.\n"
            )
        elif mode == "CLAUDE":
            system_prompt += (
                "\n[Operating Mode: Claude 3.7 Sonnet & Artifacts Engine]\n"
                "- You possess the full analytical, coding, and architectural intelligence of Claude 3.7 Sonnet.\n"
                "- Extended Thinking: For complex queries, architecture, math, or coding, wrap your reasoning inside <thinking>...</thinking> tags.\n"
                "- Claude Artifacts: When generating self-contained web apps, Canvas games, single-page dashboards, SVG graphics, or visual widgets, output full, runnable HTML/CSS/JS inside an ```html ``` code block. Nova AI will automatically open an interactive live preview pane beside the chat.\n"
                "- Excel & Data: When asked to create Excel sheets, do NOT just dump Python code. Execute [action:create_excel:filename.xlsx|{\"Sheet1\": [[\"Col1\",\"Col2\"], [\"Val1\",\"Val2\"]]}] directly so the user gets an actual formatted Excel file opened immediately.\n"
                "- Autonomous Execution: Always provide working, complete, production-grade solutions. Zero emojis.\n"
            )
        elif mode == "ENGINEER":
            system_prompt += (
                "\n[Operating Mode: Senior Software Engineer & Architect]\n"
                "- Write modular, production-grade, typed code with robust architecture.\n"
                "- Include docstrings, error handling, parameter validation, and runnable CLI entrypoints.\n"
                "- Prioritize performance, security, clean code, and zero emojis.\n"
            )
        elif mode == "RESEARCH":
            system_prompt += (
                "\n[Operating Mode: Deep Research & Intelligence Analyst]\n"
                "- Provide comprehensive, fact-dense, structured analyses with citations and source references.\n"
                "- Compare trade-offs, state-of-the-art benchmarks, and clear executive takeaways.\n"
                "- Structure insights with bulleted executive summaries and technical deep dives.\n"
            )
        elif mode == "SYSADMIN":
            system_prompt += (
                "\n[Operating Mode: Windows Systems & Infrastructure Administrator]\n"
                "- Provide robust PowerShell 5.1/7.x and batch scripts executed strictly with CREATE_NO_WINDOW.\n"
                "- Include parameter validation, error trapping ($ErrorActionPreference = 'Stop'), and path checks.\n"
                "- Focus on Windows health, diagnostics, networking, services, and system security.\n"
            )
        elif mode == "GENERAL":
            system_prompt += (
                "\n[Operating Mode: Executive General Assistant]\n"
                "- Deliver articulate, direct, and highly actionable answers with zero fluff.\n"
                "- Keep explanations crisp and prioritize user efficiency.\n"
            )
        elif mode == "SUPERAGENT":
            system_prompt += (
                "\n[Operating Mode: Autonomous Base44 SuperAgent]\n"
                "- You are an autonomous AI software engineer, sysadmin, and digital execution engine.\n"
                "- Decompose goals into clear milestone steps, execute actions directly, inspect observations, and self-correct.\n"
                "- Emphasize end-to-end task completion, zero fluff, and proactive problem solving.\n"
            )

        # Antigravity Dynamic Skills Matching & Injection
        try:
            from ai.skills_manager import skills_manager
            matched_skills = skills_manager.match_skills(text)
            if matched_skills:
                skills_injection = skills_manager.format_skills_injection(matched_skills)
                system_prompt += f"\n{skills_injection}"
        except Exception as e:
            log.warning(f"Skills injection error: {e}")

        # Long-Term Persistent Memory Recall Injection
        try:
            import memory.database as mem_db
            facts = mem_db.get_all_facts()
            if facts:
                facts_str = "\n".join(f"- {f}" for f in facts[-20:])
                system_prompt += f"\n[User Persistent Long-Term Memory & Profile]:\n{facts_str}\n"
        except Exception as e:
            log.warning(f"Memory injection error: {e}")

        # Antigravity Steps & Focus Protocol
        system_prompt += (
            "\n[Antigravity Live Execution Protocol]\n"
            "- When executing non-trivial or multi-step tasks, you may broadcast live UI updates:\n"
            "  - Broadcast high-level activity: [action:update_focus:Short present-participle description]\n"
            "  - Broadcast progress checklist: [action:update_steps:Step 1 (done)|Step 2 (in_progress)|Step 3 (pending)]\n"
            "- Valid step statuses: done, in_progress, pending, failed, skipped.\n"
        )

        self.send_btn.setEnabled(True)
        self.send_btn.setText("Stop")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                padding: 0 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        self.status_pill.setText("STREAMING...")

        # Create Assistant Bubble for live streaming output
        self._current_assistant_bubble = self._add_bubble("assistant", "")
        self._stream_text = ""

        self._llm_thread = _LLMWorker(self.llm_manager, history, system_prompt)
        self._llm_thread.chunk_received.connect(self._on_llm_chunk)
        self._llm_thread.reply_ready.connect(self._on_llm_replied)
        self._llm_thread.failed.connect(self._on_llm_failed)
        self._llm_thread.start()

    def _on_llm_chunk(self, chunk: str):
        self._stream_text += chunk
        if self._current_assistant_bubble:
            # Strip incomplete action tags from live preview
            clean_display = re.sub(r"\[action:[^\]]*\]?", "", self._stream_text, flags=re.IGNORECASE)
            self._current_assistant_bubble.update_stream_text(clean_display)
            self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _on_llm_replied(self, full_reply: str, elapsed_sec: float = 0.0):
        self._reset_send_button()
        full_reply = clean_repetitive_patterns(full_reply)
        clean_text, actions_list = automation_executor.extract_actions(full_reply)
        clean_text = clean_repetitive_patterns(clean_text)

        now_str = datetime.now().strftime("%I:%M %p")
        if self._current_assistant_bubble:
            self._current_assistant_bubble.finalize_content(clean_text or "(Task acknowledged)")
            self._current_assistant_bubble.set_meta(now_str, elapsed_sec, self.config.llm.model)
        else:
            b = self._add_bubble("assistant", clean_text or "(Task acknowledged)")
            b.set_meta(now_str, elapsed_sec, self.config.llm.model)

        # Register extracted code blocks into session artifacts drawer
        for m in _CODE_FENCE_RE.finditer(full_reply):
            lang = (m.group(1) or "code").strip()
            code_text = m.group(2).rstrip("\n")
            if code_text:
                self._register_code_artifact(lang, code_text)

        cur_sid = getattr(self, "_active_session_id", "default")
        if clean_text:
            msg_id = db.add_message("assistant", clean_text, session_id=cur_sid)
            if self._current_assistant_bubble:
                self._current_assistant_bubble.message_id = msg_id

        # Auto-name session if it was freshly created
        sess = db.get_session(cur_sid)
        if sess and sess.get("title") in ("New Session", "Untitled Session"):
            recent = db.get_recent_history(limit=4, session_id=cur_sid)
            user_msg = next((m["content"] for m in recent if m["role"] == "user"), "")
            first_line = user_msg.splitlines()[0][:32].strip() if user_msg else ""
            if first_line and not first_line.startswith("/"):
                cleaned = re.sub(r"^\[.*?\]\s*", "", first_line).strip()[:28]
                if cleaned:
                    db.rename_session(cur_sid, cleaned)
                    self._refresh_session_combo(selected_id=cur_sid)

        if not actions_list:
            self.status_pill.setText("READY")
            if self.config.voice.auto_speak and clean_text:
                self._speak_text(clean_text)
            elif self._continuous_worker and self._hands_free_active:
                self._continuous_worker.resume()
            return

        if self.config.voice.auto_speak and clean_text:
            self._speak_text(clean_text)

        # Run tasks in background thread with live visual execution pipeline
        total = len(actions_list)
        self.status_pill.setText(f"EXECUTING 1/{total}...")
        self._current_plan_widget = _ExecutionPlanWidget(actions_list)
        self.message_layout.insertWidget(self.message_layout.count() - 1, self._current_plan_widget)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

        self._task_worker = BackgroundTaskWorker(actions_list)
        self._task_worker.progress.connect(lambda s: self.status_pill.setText(s.upper()))
        self._task_worker.step_completed.connect(self._on_background_step_done)
        self._task_worker.finished_report.connect(self._on_background_tasks_completed)
        self._task_worker.start()

    def _on_background_step_done(self, idx: int, success: bool, act_name: str, msg: str):
        if hasattr(self, "_current_plan_widget") and self._current_plan_widget:
            self._current_plan_widget.mark_step_result(idx, success, msg)
            self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _on_background_tasks_completed(self, results: list[tuple[bool, str, str]]):
        if hasattr(self, "_current_plan_widget") and self._current_plan_widget:
            self._current_plan_widget.finalize(all(r[0] for r in results))

        total = len(results)
        for idx, (success, act_name, msg) in enumerate(results, 1):
            if act_name in ("enable_vision", "screen_vision", "start_vision") and success:
                self.enable_screen_vision(auto_capture=False)
            if act_name in ("save_task", "update_task", "complete_task", "plan_task"):
                self._update_tasks_btn_badge()

        is_ur = any(is_urdu_text(r[2]) for r in results) or is_urdu_text(self.config.voice.stt_language)
        reports = [r[2] for r in results if r[2]]
        summary = " | ".join(reports) if reports else "Action finished."
        all_ok = all(r[0] for r in results)

        name_tag = self.config.ui.assistant_name.upper()
        user_name = self.config.user_name or "Commander"
        if is_ur:
            spoken_report = f"کام مکمل ہو گیا ہے۔ {summary}" if all_ok else f"رپورٹ: {summary}"
            bubble_report = f"**{name_tag} رپورٹ:**\n{summary}"
        else:
            spoken_report = f"Task completed, {user_name}. {summary}" if all_ok else f"Task notice: {summary}"
            bubble_report = f"**{name_tag} Report:**\n{summary}"

        self._add_bubble("assistant", bubble_report)
        db.add_message("assistant", bubble_report)

        self.status_pill.setText("READY")

        if self.config.voice.auto_speak:
            self._speak_text(spoken_report)
        elif self._continuous_worker and self._hands_free_active:
            self._continuous_worker.resume()

    def _on_llm_failed(self, error: str):
        self._reset_send_button()
        self.status_pill.setText("ERROR")
        err_msg = f"[Error] {error}"
        if self._current_assistant_bubble:
            self._current_assistant_bubble.finalize_content(err_msg)
        else:
            self._add_bubble("assistant", err_msg)

        if self._continuous_worker and self._hands_free_active:
            self._continuous_worker.resume()

        # Only prompt on fatal missing key, never pop up automatically on transient provider errors
        pass

    def _on_input_text_changed(self):
        text = self.input_edit.toPlainText()
        if hasattr(self, "composer_stats_lbl"):
            chars = len(text)
            if chars > 0:
                words = len(text.split())
                est_tokens = max(1, round(chars / 3.8))
                self.composer_stats_lbl.setText(f"{chars} chars • {words} words • ~{est_tokens} tokens")
            else:
                self.composer_stats_lbl.setText("")

        if text.startswith("/") and len(text.strip()) <= 14 and "\n" not in text:
            filter_str = text[1:].lower().strip()
            if hasattr(self, "slash_menu"):
                self.slash_menu.filter_commands(filter_str)
                self.slash_menu.setVisible(self.slash_menu.has_matches())
        else:
            if hasattr(self, "slash_menu") and self.slash_menu.isVisible():
                self.slash_menu.setVisible(False)

    def _on_slash_command_selected(self, cmd: str):
        if hasattr(self, "slash_menu"):
            self.slash_menu.setVisible(False)
        self.input_edit.setPlainText(f"{cmd} ")
        from PySide6.QtGui import QTextCursor
        cursor = self.input_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.input_edit.setTextCursor(cursor)
        self.input_edit.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.input_edit and event.type() == QKeyEvent.KeyPress:
            if hasattr(self, "slash_menu") and self.slash_menu.isVisible():
                if event.key() == Qt.Key_Down:
                    self.slash_menu.select_next()
                    return True
                elif event.key() == Qt.Key_Up:
                    self.slash_menu.select_prev()
                    return True
                elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                    self.slash_menu.trigger_selected()
                    return True
                elif event.key() == Qt.Key_Escape:
                    self.slash_menu.setVisible(False)
                    return True

            if event.key() == Qt.Key_E and (event.modifiers() & Qt.AltModifier):
                self._refine_current_prompt()
                return True

            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self._send_message()
                return True
            elif event.key() == Qt.Key_Up:
                cursor = self.input_edit.textCursor()
                if (cursor.blockNumber() == 0 or not self.input_edit.toPlainText().strip()) and getattr(self, "_prompt_history", None):
                    if self._prompt_history_idx < len(self._prompt_history) - 1:
                        self._prompt_history_idx += 1
                        hist_text = self._prompt_history[-(self._prompt_history_idx + 1)]
                        self.input_edit.setPlainText(hist_text)
                        from PySide6.QtGui import QTextCursor
                        c = self.input_edit.textCursor()
                        c.movePosition(QTextCursor.End)
                        self.input_edit.setTextCursor(c)
                        return True
            elif event.key() == Qt.Key_Down:
                if getattr(self, "_prompt_history", None):
                    if self._prompt_history_idx > 0:
                        self._prompt_history_idx -= 1
                        hist_text = self._prompt_history[-(self._prompt_history_idx + 1)]
                        self.input_edit.setPlainText(hist_text)
                        from PySide6.QtGui import QTextCursor
                        c = self.input_edit.textCursor()
                        c.movePosition(QTextCursor.End)
                        self.input_edit.setTextCursor(c)
                        return True
                    elif self._prompt_history_idx == 0:
                        self._prompt_history_idx = -1
                        self.input_edit.clear()
                        return True
        return super().eventFilter(obj, event)