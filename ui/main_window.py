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
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
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


def _format_inline(text: str) -> str:
    escaped = html_lib.escape(text)
    # Bold: **bold**
    escaped = re.sub(r"\*\*(.+?)\*\*", r'<b style="color:#ffffff;font-weight:700;">\1</b>', escaped)
    # Inline code: `code`
    escaped = re.sub(r"`([^`]+)`", r'<code style="background:#13131c;color:#38bdf8;padding:1px 5px;border-radius:4px;font-family:Consolas,monospace;border:1px solid #1f1f2e;font-size:11px;">\1</code>', escaped)
    # Links: [label](url)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2" style="color:#38bdf8;text-decoration:none;font-weight:600;">\1</a>', escaped)
    # Italic: *italic* or _italic_
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r'<i style="color:#cbd5e1;">\1</i>', escaped)
    return escaped


def _render_prose(text: str) -> str:
    """High-fidelity executive markdown parser for chat bubbles."""
    if not text or not text.strip():
        return ""

    lines = text.strip().splitlines()
    html_lines: list[str] = []
    in_ul = False
    in_ol = False

    for line in lines:
        stripped = line.strip()

        # Horizontal Rule
        if re.match(r"^(\-{3,}|\_{3,}|\*{3,})$", stripped):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            html_lines.append('<hr style="border:none;border-top:1px solid #22222f;margin:8px 0;">')
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
            html_lines.append(f'<div style="border-left:3px solid #38bdf8;background:#101018;padding:4px 10px;margin:4px 0;border-radius:0 4px 4px 0;color:#cbd5e1;font-size:11px;">{q_text}</div>')
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
            html_lines.append(f'<li style="margin:2px 0;color:#e2e8f0;line-height:1.45;">{li_text}</li>')
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
            html_lines.append(f'<li style="margin:2px 0;color:#e2e8f0;line-height:1.45;">{li_text}</li>')
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
            html_lines.append(f'<p style="margin:2px 0;line-height:1.5;">{p_text}</p>')

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


def _render_images(html_content: str) -> str:
    def replace_tag(match):
        path_str = match.group(1).strip()
        path = Path(path_str)
        if path.exists():
            return f'<div style="margin:6px 0;"><img src="{path.resolve().as_uri()}" style="border-radius:6px;border:1px solid #2d2d38;max-width:320px;" width="320"></div>'
        return f"[Image: {path_str}]"
    return IMAGE_TAG_RE.sub(replace_tag, html_content)


SYSTEM_PROMPT_TEMPLATE = """
You are {name}, an Elite Senior Full-Stack Software Engineer, Principal Architect, and Autonomous Windows Desktop Assistant (JARVIS-grade).
You serve the user directly, decisively, and respectfully without unnecessary conversation or delay.

CODING EXPERTISE & STANDARDS:
- Mastery in Python, JavaScript, TypeScript, HTML/CSS, React, Vue, Node.js, C, C++, C#, Java, Go, Rust, SQL, Bash, PowerShell.
- Provide clean, production-ready, well-commented code. NEVER write incomplete code or placeholders like '// todo' or '...rest of code...'.
- Always wrap code in markdown code blocks with the exact language identifier (e.g. ```python, ```javascript, ```powershell, ```html, ```sql, ```cpp).
- For Python, write runnable, self-contained code that can execute directly with the user's built-in "Run Code" button.
- If diagnosing bugs or errors, identify the root cause in 1-2 concise sentences and provide the fully corrected code.

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
    finished_run = Signal(bool, str)

    def __init__(self, lang: str, code: str):
        super().__init__()
        self.lang = lang
        self.code = code

    def run(self):
        from automation.actions import run_code
        ok, msg = run_code(f"{self.lang}:{self.code}")
        self.finished_run.emit(ok, msg)


class CodeBlockWidget(QFrame):
    """Interactive Code Block card featuring 1-click Run, Copy, Save, and Live Console Output."""

    def __init__(self, lang: str, code: str):
        super().__init__()
        self.lang = (lang or "code").lower()
        self.code = code
        self._runner_worker: _CodeRunnerWorker | None = None
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

        cons_title = QLabel("CONSOLE OUTPUT:")
        cons_title.setStyleSheet("color: #64748b; font-size: 9px; font-weight: 800; font-family: Consolas, monospace;")
        cons_layout.addWidget(cons_title)

        self.console_out = QLabel("")
        self.console_out.setWordWrap(True)
        self.console_out.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.console_out.setStyleSheet("color: #10b981; font-size: 11px; font-family: Consolas, monospace;")
        cons_layout.addWidget(self.console_out)

        layout.addWidget(self.console_frame)

    def _on_copy_clicked(self):
        QApplication.clipboard().setText(self.code, QClipboard.Clipboard)
        self.copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy"))

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

    def _on_run_clicked(self):
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.console_frame.setVisible(True)
        self.console_out.setText("Executing code in background...")
        self.console_out.setStyleSheet("color: #38bdf8; font-size: 11px; font-family: Consolas, monospace;")

        self._runner_worker = _CodeRunnerWorker(self.lang, self.code)
        self._runner_worker.finished_run.connect(self._on_run_completed)
        self._runner_worker.start()

    def _on_run_completed(self, success: bool, output: str):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run")
        color = "#10b981" if success else "#ef4444"
        self.console_out.setStyleSheet(f"color: {color}; font-size: 11px; font-family: Consolas, monospace;")
        self.console_out.setText(output)


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


class _MessageBubble(QWidget):
    """Refined message card with live streaming, interactive code blocks, and screen vision action CTA."""

    def __init__(self, role: str, content: str = "", on_speak_clicked=None, on_enable_vision_clicked=None):
        super().__init__()
        self.role = role
        self.content = content
        self.on_speak_clicked = on_speak_clicked
        self.on_enable_vision_clicked = on_enable_vision_clicked
        self.is_user = (role == "user")
        self.vision_cta_btn: QPushButton | None = None

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 3, 6, 3)

        self.card = QFrame()
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(12, 10, 12, 10)
        self.card_layout.setSpacing(6)

        if self.is_user:
            self._orig_style = f"""
                QFrame {{
                    background-color: {_BG_USER};
                    color: {_TEXT_MAIN};
                    border-radius: 10px;
                    border: 1px solid #2b2b38;
                }}
            """
        else:
            self._orig_style = f"""
                QFrame {{
                    background-color: {_BG_CARD};
                    color: {_TEXT_MAIN};
                    border-radius: 10px;
                    border: 1px solid {_BORDER};
                }}
            """
        self.card.setStyleSheet(self._orig_style)

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
        self.stream_label.setStyleSheet("background: transparent; border: none; font-size: 13px; line-height: 1.45;")
        self.content_layout.addWidget(self.stream_label)

        # Bottom action bar for Assistant
        if not self.is_user:
            self.action_bar = QHBoxLayout()
            self.action_bar.setContentsMargins(0, 4, 0, 0)
            self.action_bar.setSpacing(6)

            self.full_copy_btn = QPushButton("Copy All")
            self.full_copy_btn.setIcon(create_copy_icon("#94a3b8", size=12))
            self.full_copy_btn.setFixedSize(76, 22)
            self.full_copy_btn.setCursor(Qt.PointingHandCursor)
            self.full_copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #171720;
                    color: {_TEXT_MUTED};
                    border: 1px solid #262633;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0 6px;
                }}
                QPushButton:hover {{
                    color: #ffffff;
                    border-color: #3f3f50;
                    background-color: #20202c;
                }}
            """)
            self.full_copy_btn.clicked.connect(self._copy_full_content)
            self.action_bar.addWidget(self.full_copy_btn)

            if on_speak_clicked:
                self.listen_btn = QPushButton("Speak")
                self.listen_btn.setIcon(create_speaker_icon("#94a3b8", size=12))
                self.listen_btn.setFixedSize(66, 22)
                self.listen_btn.setCursor(Qt.PointingHandCursor)
                self.listen_btn.setStyleSheet(self.full_copy_btn.styleSheet())
                self.listen_btn.clicked.connect(lambda: on_speak_clicked(self.content))
                self.action_bar.addWidget(self.listen_btn)

            self.action_bar.addStretch()
            self.meta_lbl = QLabel("")
            self.meta_lbl.setStyleSheet("color: #475569; font-size: 9px; font-weight: 600; font-family: Consolas, monospace;")
            self.action_bar.addWidget(self.meta_lbl)
            self.card_layout.addLayout(self.action_bar)

        if self.is_user:
            self.layout.addStretch()
            self.layout.addWidget(self.card, 0)
        else:
            self.layout.addWidget(self.card, 0)
            self.layout.addStretch()

        if content:
            self.finalize_content(content)

    def set_meta(self, time_str: str, latency_sec: float = 0.0, model_name: str = ""):
        parts = [time_str]
        if latency_sec > 0:
            parts.append(f"{latency_sec:.1f}s")
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
            self.card.setStyleSheet(self._orig_style + f"""
                QFrame {{
                    border: 2px solid {accent} !important;
                    background-color: #0f172a !important;
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
        """Parses finished text into prose sections and interactive CodeBlockWidgets."""
        self.content = text
        if self.is_user:
            self.stream_label.setText(_render_images(_render_message_html(text)))
            return

        # Clear content layout
        while self.content_layout.count() > 0:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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
            self.greeting_lbl.setText(f"Welcome, {self.user_name}")

    def _build_ui(self):
        self.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 14)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignCenter)

        # Central Card Container
        hero_card = QFrame()
        hero_card.setMaximumWidth(720)
        hero_card.setStyleSheet(f"""
            QFrame {{
                background-color: #0d0d14;
                border: 1px solid {_BORDER};
                border-radius: 12px;
            }}
        """)
        card_vbox = QVBoxLayout(hero_card)
        card_vbox.setContentsMargins(24, 22, 24, 22)
        card_vbox.setSpacing(14)

        # Header with Logo & Brand
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(10)

        logo = QLabel("N")
        logo.setFixedSize(36, 36)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("""
            background: #0284c7;
            color: #ffffff;
            font-weight: 900;
            font-size: 18px;
            border-radius: 8px;
        """)
        hdr_row.addWidget(logo)

        hdr_text_box = QVBoxLayout()
        hdr_text_box.setSpacing(1)
        self.greeting_lbl = QLabel(f"Welcome, {self.user_name}")
        self.greeting_lbl.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: 800; letter-spacing: 0.3px;")
        sub_title = QLabel("NOVA AUTONOMOUS AI • DESKTOP & MULTI-CHANNEL SUITE")
        sub_title.setStyleSheet(f"color: {_ACCENT_CYAN}; font-size: 9px; font-weight: 800; letter-spacing: 1px;")
        hdr_text_box.addWidget(self.greeting_lbl)
        hdr_text_box.addWidget(sub_title)
        hdr_row.addLayout(hdr_text_box)
        hdr_row.addStretch()

        badge_box = QHBoxLayout()
        badge_box.setSpacing(6)
        for b_text, b_color in [("GROQ READY", "#10b981"), ("OBSERVER ON", "#38bdf8"), ("CHANNELS STANDBY", "#a855f7")]:
            b_lbl = QLabel(b_text)
            b_lbl.setStyleSheet(f"background: #11111a; border: 1px solid #222230; color: {b_color}; font-size: 9px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
            badge_box.addWidget(b_lbl)
        hdr_row.addLayout(badge_box)

        card_vbox.addLayout(hdr_row)

        desc = QLabel(
            "Nova is your autonomous executive co-pilot. She can write and execute code in any language, "
            "inspect and manipulate active desktop windows, autonomously research the web, "
            "and synchronize tasks across WhatsApp, Discord, and scheduled background workers."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.5;")
        card_vbox.addWidget(desc)

        # Action Cards Section
        act_title = QLabel("QUICK CAPABILITIES:")
        act_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800; letter-spacing: 0.8px;")
        card_vbox.addWidget(act_title)

        grid = QHBoxLayout()
        grid.setSpacing(10)

        actions_data = [
            ("System Health", "CPU, RAM & Disks", "system_stats", True),
            ("Deep Research", "Autonomous Web Intel", "Perform a deep web research on latest AI agent advancements and generate a structured summary.", False),
            ("Code Architect", "Write Python Utilities", "Write a modular Python script with robust error handling and CLI arguments.", False),
            ("Screen Vision", "Inspect Desktop Display", "Analyze my active screen and summarize what is currently visible.", False),
        ]

        for title, subtitle, prompt, is_instant in actions_data:
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #12121a;
                    border: 1px solid {_BORDER};
                    border-radius: 8px;
                    padding: 10px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: #1a1a26;
                    border-color: {_ACCENT_CYAN};
                }}
            """)
            btn_layout = QVBoxLayout(btn)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(2)

            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700;")
            s_lbl = QLabel(subtitle)
            s_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 9px;")
            btn_layout.addWidget(t_lbl)
            btn_layout.addWidget(s_lbl)

            btn.clicked.connect(lambda _, p=prompt, i=is_instant: self._handle_click(p, i))
            grid.addWidget(btn, 1)

        card_vbox.addLayout(grid)
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
            self.cpu_lbl.setText(f"CPU: {cpu_pct}%")
            self.cpu_bar.setValue(cpu_pct)
            cpu_color = "#ef4444" if cpu_pct > 80 else "#38bdf8"
            self.cpu_bar.setStyleSheet(f"QProgressBar {{ background: #1a1a26; border-radius: 1px; }} QProgressBar::chunk {{ background: {cpu_color}; border-radius: 1px; }}")

            self.ram_lbl.setText(f"RAM: {ram_pct}% ({used_gb}G)")
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
        mode_keys = ["engineer", "research", "sysadmin", "superagent", "general"]
        for idx, key in enumerate(mode_keys):
            if name_lower in key or key in name_lower:
                return idx
        return -1

    def _on_top_model_changed(self, index: int):
        if index < 0 or index >= self.model_combo.count():
            return
        m_id = self.model_combo.itemData(index)
        if m_id and m_id != self.config.llm.model:
            self.config.llm.model = m_id
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
        mode_keys = ["ENGINEER", "RESEARCH", "SYSADMIN", "SUPERAGENT", "GENERAL"]
        if 0 <= index < len(mode_keys):
            self._operating_mode = mode_keys[index]
            if hasattr(self, "mode_combo") and self.mode_combo.currentIndex() != index:
                self.mode_combo.blockSignals(True)
                self.mode_combo.setCurrentIndex(index)
                self.mode_combo.blockSignals(False)
            mode_names = {
                "ENGINEER": "Senior Software Architect",
                "RESEARCH": "Deep Research Analyst",
                "SYSADMIN": "Windows System Administrator",
                "SUPERAGENT": "Autonomous Base44 SuperAgent",
                "GENERAL": "Executive General Assistant",
            }
            if self._operating_mode == "SUPERAGENT":
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
            self.show_toast(f"Mode: {mode_names[self._operating_mode]}", "SYSTEM")

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
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = Path(urls[0].toLocalFile())
                if file_path.exists():
                    self._attached_path = file_path
                    self.attachment_preview.setText(f"[Attached: {file_path.name}]")
                    self.attachment_preview.setVisible(True)
                    self.show_toast(f"Attached: {file_path.name}", "SUCCESS")
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
        start_w = max(self.config.ui.start_width, 1020)
        start_h = max(self.config.ui.start_height, 720)
        self.resize(start_w, start_h)
        self.setMinimumSize(880, 580)

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

        # ── LEFT SIDEBAR ─────────────────────────────────────────────
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(205)
        self.sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: #0c0c14;
                border-right: 1px solid {_BORDER};
            }}
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 14)
        sidebar_layout.setSpacing(6)

        # Brand / Logo Header
        brand_box = QHBoxLayout()
        brand_box.setSpacing(8)
        logo_lbl = QLabel("N")
        logo_lbl.setFixedSize(28, 28)
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("""
            background: #0284c7;
            color: #ffffff;
            font-weight: 900;
            font-size: 15px;
            border-radius: 6px;
        """)
        brand_box.addWidget(logo_lbl)

        brand_text_box = QVBoxLayout()
        brand_text_box.setSpacing(1)
        self.title_label = QLabel(self.config.ui.assistant_name.upper())
        self.title_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 800; letter-spacing: 1px;")
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

        # Separator line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1e293b; margin: 4px 0;")
        sidebar_layout.addWidget(sep)

        # Navigation Buttons
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

        # Backward compatibility aliases
        self.tasks_btn = self.nav_tasks
        self.conn_btn = self.nav_conn
        self.settings_btn = self.nav_settings

        sidebar_layout.addStretch()

        # Sidebar Bottom Controls (Voice, Vision)
        ctrl_title = QLabel("SYSTEM MODES")
        ctrl_title.setStyleSheet("color: #475569; font-size: 9px; font-weight: 800; letter-spacing: 0.6px;")
        sidebar_layout.addWidget(ctrl_title)

        # Screen Vision Toggle
        self.screen_vision_btn = QPushButton("Vision: OFF")
        self.screen_vision_btn.setCursor(Qt.PointingHandCursor)
        self.screen_vision_btn.setFixedHeight(26)
        self._style_quick_button(self.screen_vision_btn, active=self.config.ui.screen_observing)
        self.screen_vision_btn.clicked.connect(self._toggle_screen_vision)
        sidebar_layout.addWidget(self.screen_vision_btn)

        # Hands-Free Voice Mode Toggle
        self.hands_free_btn = QPushButton("Mic: OFF")
        self.hands_free_btn.setCursor(Qt.PointingHandCursor)
        self.hands_free_btn.setFixedHeight(26)
        self._style_quick_button(self.hands_free_btn, active=False)
        self.hands_free_btn.clicked.connect(self._toggle_hands_free_mode)
        sidebar_layout.addWidget(self.hands_free_btn)

        # Speech Toggle Button
        self.speak_toggle_btn = QPushButton("Speech: ON" if self.config.voice.auto_speak else "Speech: OFF")
        self.speak_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.speak_toggle_btn.setFixedHeight(26)
        self._style_quick_button(self.speak_toggle_btn, active=self.config.voice.auto_speak)
        self.speak_toggle_btn.clicked.connect(self._toggle_auto_speak)
        sidebar_layout.addWidget(self.speak_toggle_btn)

        # Real-time System Telemetry Card
        self.telemetry_card = QFrame()
        self.telemetry_card.setStyleSheet("""
            QFrame {
                background-color: #0c0c14;
                border: 1px solid #1c1c28;
                border-radius: 6px;
                padding: 6px 8px;
            }
        """)
        telem_layout = QVBoxLayout(self.telemetry_card)
        telem_layout.setContentsMargins(2, 2, 2, 2)
        telem_layout.setSpacing(4)

        telem_hdr = QHBoxLayout()
        telem_title = QLabel("TELEMETRY")
        telem_title.setStyleSheet("color: #475569; font-size: 8px; font-weight: 800; letter-spacing: 0.6px;")
        telem_hdr.addWidget(telem_title)
        telem_hdr.addStretch()
        self.telem_live_dot = QLabel("●")
        self.telem_live_dot.setStyleSheet("color: #10b981; font-size: 8px;")
        telem_hdr.addWidget(self.telem_live_dot)
        telem_layout.addLayout(telem_hdr)

        # CPU Row
        cpu_row = QHBoxLayout()
        self.cpu_lbl = QLabel("CPU: --%")
        self.cpu_lbl.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600; font-family: Consolas, monospace;")
        cpu_row.addWidget(self.cpu_lbl)
        telem_layout.addLayout(cpu_row)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFixedHeight(3)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        self.cpu_bar.setStyleSheet("QProgressBar { background: #1a1a26; border-radius: 1px; } QProgressBar::chunk { background: #38bdf8; border-radius: 1px; }")
        telem_layout.addWidget(self.cpu_bar)

        # RAM Row
        ram_row = QHBoxLayout()
        self.ram_lbl = QLabel("RAM: --%")
        self.ram_lbl.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 600; font-family: Consolas, monospace;")
        ram_row.addWidget(self.ram_lbl)
        telem_layout.addLayout(ram_row)

        self.ram_bar = QProgressBar()
        self.ram_bar.setFixedHeight(3)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        self.ram_bar.setStyleSheet("QProgressBar { background: #1a1a26; border-radius: 1px; } QProgressBar::chunk { background: #10b981; border-radius: 1px; }")
        telem_layout.addWidget(self.ram_bar)

        sidebar_layout.addWidget(self.telemetry_card)

        # Version Pill
        ver_lbl = QLabel("Nova AI • v2.5 Pro")
        ver_lbl.setStyleSheet("color: #475569; font-size: 10px; font-weight: 600; margin-top: 4px;")
        ver_lbl.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(ver_lbl)

        root.addWidget(self.sidebar)

        # ── RIGHT MAIN CONTAINER ─────────────────────────────────────
        main_content = QWidget()
        main_content.setStyleSheet("background-color: #07070a;")
        main_vbox = QVBoxLayout(main_content)
        main_vbox.setContentsMargins(14, 12, 14, 12)
        main_vbox.setSpacing(8)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.view_title = QLabel("Chat & Autonomous Code Console")
        self.view_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 700;")
        top_bar.addWidget(self.view_title)

        # Quick Command Palette Button
        self.palette_btn = QPushButton("Quick Command (Ctrl+K)")
        self.palette_btn.setToolTip("Open Command Palette (Ctrl+K)")
        self.palette_btn.setCursor(Qt.PointingHandCursor)
        self.palette_btn.setFixedHeight(24)
        self.palette_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #12121a;
                color: #64748b;
                border: 1px solid {_BORDER};
                border-radius: 5px;
                padding: 0 10px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT_CYAN};
                color: #cbd5e1;
                background-color: #181826;
            }}
        """)
        self.palette_btn.clicked.connect(self._open_command_palette)
        top_bar.addWidget(self.palette_btn)

        # Session Switcher Dropdown
        self.session_combo = QComboBox()
        self.session_combo.setCursor(Qt.PointingHandCursor)
        self.session_combo.setFixedHeight(24)
        self.session_combo.setMinimumWidth(125)
        self.session_combo.setMaximumWidth(190)
        self.session_combo.setToolTip("Active Chat Session / Thread")
        self.session_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #12121a;
                color: #e2e8f0;
                border: 1px solid {_BORDER};
                border-radius: 5px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: 600;
            }}
            QComboBox:hover {{
                border-color: {_ACCENT_CYAN};
                color: #ffffff;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 14px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #0b0b12;
                color: #e2e8f0;
                border: 1px solid {_BORDER};
                selection-background-color: {_ACCENT_BLUE};
                selection-color: #ffffff;
                outline: none;
                padding: 4px;
            }}
        """)
        self.session_combo.currentIndexChanged.connect(self._on_session_combo_changed)
        top_bar.addWidget(self.session_combo)

        # New Chat Session Button (Ctrl+N)
        new_chat_btn = QPushButton("+ New Chat")
        new_chat_btn.setToolTip("Start New Isolated Chat Session (Ctrl+N)")
        new_chat_btn.setCursor(Qt.PointingHandCursor)
        new_chat_btn.setFixedHeight(24)
        new_chat_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_ACCENT_BLUE};
                color: #ffffff;
                border: 1px solid #0369a1;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #0369a1;
            }}
        """)
        new_chat_btn.clicked.connect(self._create_new_session)
        top_bar.addWidget(new_chat_btn)

        top_bar.addStretch()

        # Interactive Model Switcher Dropdown
        self.model_combo = QComboBox()
        self.model_combo.setCursor(Qt.PointingHandCursor)
        self.model_combo.setFixedHeight(26)
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #0f172a;
                color: #38bdf8;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 700;
                font-family: Consolas, monospace;
            }
            QComboBox:hover {
                border-color: #38bdf8;
                background-color: #16243d;
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

        # Persona Operating Mode Switcher Dropdown
        self.mode_combo = QComboBox()
        self.mode_combo.setCursor(Qt.PointingHandCursor)
        self.mode_combo.setFixedHeight(26)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #0f172a;
                color: #38bdf8;
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 700;
                font-family: Consolas, monospace;
            }
            QComboBox:hover {
                border-color: #38bdf8;
                background-color: #16243d;
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
        mode_choices = [
            ("ENGINEER", "Mode: Engineer"),
            ("RESEARCH", "Mode: Research"),
            ("SYSADMIN", "Mode: SysAdmin"),
            ("SUPERAGENT", "Mode: SuperAgent"),
            ("GENERAL", "Mode: General"),
        ]
        for m_id, m_label in mode_choices:
            self.mode_combo.addItem(m_label, m_id)
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        top_bar.addWidget(self.mode_combo)

        self.status_pill = QLabel("READY")
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
        top_bar.addWidget(self.status_pill)

        # Find in Chat Button (Ctrl+F)
        find_btn = QPushButton("Find")
        find_btn.setToolTip("Find in conversation (Ctrl+F)")
        find_btn.setCursor(Qt.PointingHandCursor)
        find_btn.setFixedHeight(24)
        find_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #12121a;
                color: #94a3b8;
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 0 8px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #1e293b;
                color: #38bdf8;
                border-color: #38bdf8;
            }}
        """)
        find_btn.clicked.connect(self._toggle_search_bar)
        top_bar.addWidget(find_btn)

        # Export Button
        export_btn = QPushButton("Export")
        export_btn.setToolTip("Export conversation to Markdown (.md)")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setFixedHeight(24)
        export_btn.setStyleSheet(find_btn.styleSheet())
        export_btn.clicked.connect(self._export_conversation)
        top_bar.addWidget(export_btn)

        # Attach File Button (Ctrl+O)
        attach_btn = QPushButton("Attach")
        attach_btn.setToolTip("Attach File, Code, Logs, or Image Context (Ctrl+O)")
        attach_btn.setCursor(Qt.PointingHandCursor)
        attach_btn.setFixedHeight(24)
        attach_btn.setStyleSheet(find_btn.styleSheet())
        attach_btn.clicked.connect(self._on_attach_file)
        top_bar.addWidget(attach_btn)

        # Snip Button
        snip_btn = QPushButton("Snip Screen")
        snip_btn.setToolTip("Snip Screen (Ctrl+Shift+D)")
        snip_btn.setCursor(Qt.PointingHandCursor)
        snip_btn.setFixedHeight(24)
        snip_btn.setStyleSheet(find_btn.styleSheet())
        snip_btn.clicked.connect(self.snipper.start_snip)
        top_bar.addWidget(snip_btn)

        # Clear Chat Button
        clear_btn = QPushButton("Clear Chat")
        clear_btn.setToolTip("Clear conversation history")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setFixedHeight(24)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #12121a;
                color: #94a3b8;
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 0 8px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #450a0a;
                color: #fca5a5;
                border-color: #991b1b;
            }}
        """)
        clear_btn.clicked.connect(self._clear_conversation)
        top_bar.addWidget(clear_btn)

        # Shortcuts Guide Button (F1)
        help_btn = QPushButton("Shortcuts")
        help_btn.setToolTip("Keyboard shortcuts reference (F1)")
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.setFixedHeight(24)
        help_btn.setStyleSheet(find_btn.styleSheet())
        help_btn.clicked.connect(self._show_shortcuts_dialog)
        top_bar.addWidget(help_btn)

        # Prompts Library Button (Ctrl+P)
        prompts_btn = QPushButton("Prompts")
        prompts_btn.setToolTip("Prompt & Automation Library (Ctrl+P)")
        prompts_btn.setCursor(Qt.PointingHandCursor)
        prompts_btn.setFixedHeight(24)
        prompts_btn.setStyleSheet(find_btn.styleSheet())
        prompts_btn.clicked.connect(self._open_prompt_library)
        top_bar.addWidget(prompts_btn)

        # Code Artifacts Drawer Button (Ctrl+B)
        self.artifacts_btn = QPushButton("Artifacts (0)")
        self.artifacts_btn.setToolTip("Code Artifacts & Scripts Drawer (Ctrl+B)")
        self.artifacts_btn.setCursor(Qt.PointingHandCursor)
        self.artifacts_btn.setFixedHeight(24)
        self.artifacts_btn.setStyleSheet(find_btn.styleSheet())
        self.artifacts_btn.clicked.connect(self._open_artifacts_drawer)
        top_bar.addWidget(self.artifacts_btn)

        # Quick PowerShell Terminal Button (Ctrl+T)
        terminal_btn = QPushButton("Terminal")
        terminal_btn.setToolTip("Quick PowerShell Terminal Runner (Ctrl+T)")
        terminal_btn.setCursor(Qt.PointingHandCursor)
        terminal_btn.setFixedHeight(24)
        terminal_btn.setStyleSheet(find_btn.styleSheet())
        terminal_btn.clicked.connect(self._open_terminal_runner)
        top_bar.addWidget(terminal_btn)

        # Git Workspace Manager Button (Ctrl+G)
        git_btn = QPushButton("Git")
        git_btn.setToolTip("Git Workspace Manager (Ctrl+G)")
        git_btn.setCursor(Qt.PointingHandCursor)
        git_btn.setFixedHeight(24)
        git_btn.setStyleSheet(find_btn.styleSheet())
        git_btn.clicked.connect(self._open_git_manager)
        top_bar.addWidget(git_btn)

        # Antigravity Skills Manager Button (Ctrl+Shift+S)
        skills_btn = QPushButton("Skills")
        skills_btn.setToolTip("Antigravity Skills & Customizations Manager (Ctrl+Shift+S)")
        skills_btn.setCursor(Qt.PointingHandCursor)
        skills_btn.setFixedHeight(24)
        skills_btn.setStyleSheet(find_btn.styleSheet())
        skills_btn.clicked.connect(self._open_skills_manager)
        top_bar.addWidget(skills_btn)

        main_vbox.addLayout(top_bar)

        # Stacked Pages
        self.main_stack = QStackedWidget()

        # PAGE 0: Chat Console
        chat_page = QWidget()
        chat_vbox = QVBoxLayout(chat_page)
        chat_vbox.setContentsMargins(0, 0, 0, 0)
        chat_vbox.setSpacing(8)

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
        chat_vbox.addWidget(self.scroll, 1)

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
        strip_layout.setContentsMargins(2, 0, 2, 0)
        strip_layout.setSpacing(6)

        strip_pills = [
            ("Prompts Library", self._open_prompt_library),
            ("Deep Research", lambda: self._send_quick_prompt("[action:web_search:] ")),
            ("Run Code", lambda: self._send_quick_prompt("[action:run_code:python:] ")),
            ("Screen Vision", lambda: self._send_quick_prompt("Analyze active screen and ")),
            ("Daily Briefing", lambda: self._send_quick_prompt("Provide my daily executive briefing and system health overview.")),
            ("System Health", lambda: self._quick_action("system_stats")),
            ("Clean Temp", lambda: self._quick_action("clear_temp")),
        ]

        for pill_label, pill_callback in strip_pills:
            p_btn = QPushButton(pill_label)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.setFixedHeight(22)
            p_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #0d0d16;
                    color: #94a3b8;
                    border: 1px solid {_BORDER};
                    border-radius: 11px;
                    padding: 0 10px;
                    font-size: 10px;
                    font-weight: 600;
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
        chat_vbox.addWidget(action_strip)

        # Input Card
        input_card = QFrame()
        input_card.setStyleSheet(f"""
            QFrame {{
                background-color: {_BG_PANEL};
                border: 1px solid {_BORDER};
                border-radius: 10px;
            }}
        """)
        card_layout = QVBoxLayout(input_card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(4)

        # Text input field
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Ask Nova, /help for commands, Ctrl+K for palette... (Enter to send, Shift+Enter for newline)")
        self.input_edit.setMaximumHeight(85)
        self.input_edit.setMinimumHeight(40)
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                color: {_TEXT_MAIN};
                font-size: 13px;
                padding: 4px 6px;
            }}
        """)
        self.input_edit.installEventFilter(self)
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

        controls_row.addStretch()

        # Send Button
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedHeight(28)
        self.send_btn.setCursor(Qt.PointingHandCursor)
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
        self.send_btn.clicked.connect(self._send_message)
        controls_row.addWidget(self.send_btn)

        card_layout.addLayout(controls_row)
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

    def _refresh_session_combo(self, selected_id: str | None = None):
        if not hasattr(self, "session_combo"):
            return
        target_id = selected_id or getattr(self, "_active_session_id", "default")
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        sessions = db.get_all_sessions()
        active_index = 0
        for idx, sess in enumerate(sessions):
            self.session_combo.addItem(sess["title"], sess["id"])
            if sess["id"] == target_id:
                active_index = idx
        self.session_combo.setCurrentIndex(active_index)
        self.session_combo.blockSignals(False)

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
                self._add_bubble(msg["role"], msg["content"])
        else:
            if self.hero_widget:
                self.hero_widget.setVisible(True)

    def _add_bubble(self, role: str, content: str = "") -> _MessageBubble:
        if self.hero_widget:
            self.hero_widget.setVisible(False)
        bubble = _MessageBubble(
            role,
            content,
            on_speak_clicked=self._speak_text,
            on_enable_vision_clicked=self.enable_screen_vision
        )
        self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)
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

    def _speak_text(self, text: str):
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

        tts.speak(text, voice=voice, on_finished=on_speech_ended)

    def _on_region_snipped(self, image_path: str):
        self._attached_path = Path(image_path)
        self.attachment_preview.setText(f"[Attached: {self._attached_path.name}]")
        self.attachment_preview.setVisible(True)

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Attach Code, Logs, Data, or Image Context",
            "",
            "All Supported (*.py *.js *.ts *.html *.css *.json *.txt *.md *.log *.csv *.png *.jpg *.jpeg *.webp);;Code & Text (*.py *.js *.ts *.html *.css *.json *.txt *.md *.log *.csv *.bat *.ps1 *.sql);;Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*.*)"
        )
        if not file_path:
            return

        p = Path(file_path)
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

    def _send_message(self, prefix: str = ""):
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
        self.input_edit.clear()

        # Handle instant slash commands without external API delay
        if text.startswith("/") and not image_path_to_send:
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

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

        # Add User bubble
        bubble_text = text or "[Attached Screen Context]"
        if image_path_to_send:
            bubble_text = f"{bubble_text}\n[Image: {image_path_to_send}]"
        self._add_bubble("user", bubble_text)
        cur_sid = getattr(self, "_active_session_id", "default")
        db.add_message("user", bubble_text, session_id=cur_sid)

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

        # Operating Persona Steering
        mode = getattr(self, "_operating_mode", "ENGINEER")
        if mode == "ENGINEER":
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
            db.add_message("assistant", clean_text, session_id=cur_sid)

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

    def eventFilter(self, obj, event):
        if obj is self.input_edit and event.type() == QKeyEvent.KeyPress:
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