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
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QClipboard, QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.tasks_view import TasksView
from ui.connections_view import ConnectionsView
from ui.admin_feed_view import AdminFeedView
from ui.settings_view import SettingsView

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
    reply_ready = Signal(str)
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
        try:
            chunks = []
            for chunk in self.manager.chat_stream(self.history, system_prompt=self.system_prompt):
                if self._cancelled:
                    break
                chunks.append(chunk)
                self.chunk_received.emit(chunk)
            full_reply = "".join(chunks)
            if not self._cancelled:
                self.reply_ready.emit(full_reply)
        except LLMError as exc:
            if not self._cancelled:
                self.failed.emit(str(exc))
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(f"Error: {exc}")


class BackgroundTaskWorker(QThread):
    progress = Signal(str)
    finished_report = Signal(list)  # list of tuples (success: bool, act_name: str, msg: str)

    def __init__(self, actions_list: list[tuple[str, str]]):
        super().__init__()
        self.actions_list = actions_list

    def run(self):
        results = []
        total = len(self.actions_list)
        for idx, (act_name, act_arg) in enumerate(self.actions_list, 1):
            step_lbl = f"Step {idx}/{total}: {act_name}" if total > 1 else f"Executing: {act_name}"
            self.progress.emit(step_lbl)
            if act_name == "generate_image":
                try:
                    img_path = generate_image(act_arg)
                    results.append((True, act_name, f"Image generated: {img_path}"))
                except Exception as e:
                    results.append((False, act_name, f"Image error: {e}"))
            else:
                success, msg = automation_executor.run_action(act_name, act_arg)
                results.append((success, act_name, msg))
        self.finished_report.emit(results)


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
            self.card.setStyleSheet(f"""
                QFrame {{
                    background-color: {_BG_USER};
                    color: {_TEXT_MAIN};
                    border-radius: 10px;
                    border: 1px solid #2b2b38;
                }}
            """)
        else:
            self.card.setStyleSheet(f"""
                QFrame {{
                    background-color: {_BG_CARD};
                    color: {_TEXT_MAIN};
                    border-radius: 10px;
                    border: 1px solid {_BORDER};
                }}
            """)

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
            self.card_layout.addLayout(self.action_bar)

        if self.is_user:
            self.layout.addStretch()
            self.layout.addWidget(self.card, 0)
        else:
            self.layout.addWidget(self.card, 0)
            self.layout.addStretch()

        if content:
            self.finalize_content(content)

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

        # Global Hotkey Thread (Ctrl+Shift+D for Snip, Ctrl+Shift+N to Toggle Nova)
        self.hotkey_thread = GlobalHotkeyThread()
        self.hotkey_thread.hotkey_triggered.connect(self.snipper.start_snip)
        self.hotkey_thread.summon_triggered.connect(self._toggle_window_visibility)
        self.hotkey_thread.start()

        self._setup_window()
        self._build_ui()
        self._load_history()
        self._update_tasks_btn_badge()

        # Start non-blocking Desktop-Hybrid cloud sync in background
        remote_sync.start_background_sync(self.config, delay_sec=1.2)

        # Check API key seamlessly on startup
        QTimer.singleShot(600, self._check_api_key_on_startup)

    def _check_api_key_on_startup(self):
        key = get_api_key(self.config)
        if hasattr(self, "model_badge"):
            self.model_badge.setText(f"ENGINE: {self.config.llm.provider.upper()} ({self.config.llm.model})")
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
                if hasattr(self, "model_badge"):
                    self.model_badge.setText(f"ENGINE: {self.config.llm.provider.upper()} ({self.config.llm.model})")
                if self.config.user_name:
                    self.title_label.setText(self.config.ui.assistant_name.upper())
                    self.setWindowTitle(f"{self.config.ui.assistant_name} - Autonomous Desktop Studio")
                    if self.hero_widget:
                        self.hero_widget.update_user_name(self.config.user_name)
        else:
            self.status_pill.setText("READY")

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
        top_bar.addStretch()

        self.model_badge = QLabel(f"ENGINE: {self.config.llm.provider.upper()} ({self.config.llm.model})")
        self.model_badge.setStyleSheet("""
            color: #38bdf8;
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding: 3px 10px;
            border-radius: 9px;
            background: #0f172a;
            border: 1px solid #1e3a5f;
            font-family: Consolas, monospace;
        """)
        top_bar.addWidget(self.model_badge)

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

        # Snip Button
        snip_btn = QPushButton("Snip Screen")
        snip_btn.setToolTip("Snip Screen (Ctrl+Shift+D)")
        snip_btn.setCursor(Qt.PointingHandCursor)
        snip_btn.setFixedHeight(24)
        snip_btn.setStyleSheet(f"""
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
                color: #ffffff;
            }}
        """)
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

        main_vbox.addLayout(top_bar)

        # Stacked Pages
        self.main_stack = QStackedWidget()

        # PAGE 0: Chat Console
        chat_page = QWidget()
        chat_vbox = QVBoxLayout(chat_page)
        chat_vbox.setContentsMargins(0, 0, 0, 0)
        chat_vbox.setSpacing(8)

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
        self.input_edit.setPlaceholderText("Ask Nova, write code, run scripts, or speak… (Enter to send, Shift+Enter for newline)")
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

    def _load_history(self):
        recent = db.get_recent_history(limit=30)
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
            self._start_continuous_listener()
        else:
            self.hands_free_btn.setText("Hands-Free: OFF")
            self.hands_free_btn.setIcon(create_mic_icon("#94a3b8", size=14))
            self._style_header_button(self.hands_free_btn, active=False)
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
        if self._continuous_worker and self._hands_free_active:
            self._continuous_worker.pause()

        voice = self.config.voice.tts_voice_ur if is_urdu_text(text) else self.config.voice.tts_voice_en

        def on_speech_ended():
            self.status_pill.setText("READY")
            if self._continuous_worker and self._hands_free_active:
                self._continuous_worker.resume()

        tts.speak(text, voice=voice, on_finished=on_speech_ended)

    def _on_region_snipped(self, image_path: str):
        self._attached_path = Path(image_path)
        self.attachment_preview.setText(f"[Attached: {self._attached_path.name}]")
        self.attachment_preview.setVisible(True)

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Attach File or Code", "", "Source Code & Images (*.py *.js *.html *.css *.json *.txt *.png *.jpg);;All Files (*.*)"
        )
        if file_path:
            self._attached_path = Path(file_path)
            self.attachment_preview.setText(f"[Attached: {self._attached_path.name}]")
            self.attachment_preview.setVisible(True)

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
        # If currently streaming, clicking Stop aborts generation cleanly
        if self._llm_thread and self._llm_thread.isRunning():
            self._llm_thread.cancel()
            self._reset_send_button()
            self.status_pill.setText("READY")
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

        # Add User bubble
        bubble_text = text or "[Attached Screen Context]"
        if image_path_to_send:
            bubble_text = f"{bubble_text}\n[Image: {image_path_to_send}]"
        self._add_bubble("user", bubble_text)
        db.add_message("user", bubble_text)

        # Prepare Chat Messages
        history: list[ChatMessage] = []
        for msg in db.get_recent_history(limit=10):
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

    def _on_llm_replied(self, full_reply: str):
        self._reset_send_button()
        full_reply = clean_repetitive_patterns(full_reply)
        clean_text, actions_list = automation_executor.extract_actions(full_reply)
        clean_text = clean_repetitive_patterns(clean_text)

        if self._current_assistant_bubble:
            self._current_assistant_bubble.finalize_content(clean_text or "(Task acknowledged)")
        else:
            self._add_bubble("assistant", clean_text or "(Task acknowledged)")

        if clean_text:
            db.add_message("assistant", clean_text)

        if not actions_list:
            self.status_pill.setText("READY")
            if self.config.voice.auto_speak and clean_text:
                self._speak_text(clean_text)
            elif self._continuous_worker and self._hands_free_active:
                self._continuous_worker.resume()
            return

        if self.config.voice.auto_speak and clean_text:
            self._speak_text(clean_text)

        # Run tasks in background thread
        total = len(actions_list)
        self.status_pill.setText(f"EXECUTING 1/{total}...")
        self._task_worker = BackgroundTaskWorker(actions_list)
        self._task_worker.progress.connect(lambda s: self.status_pill.setText(s.upper()))
        self._task_worker.finished_report.connect(self._on_background_tasks_completed)
        self._task_worker.start()

    def _on_background_tasks_completed(self, results: list[tuple[bool, str, str]]):
        total = len(results)
        for idx, (success, act_name, msg) in enumerate(results, 1):
            prefix = f"Step {idx}/{total} [{act_name}]" if total > 1 else f"[{act_name}]"
            self._add_action_badge(success, f"{prefix}: {msg}")
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
        return super().eventFilter(obj, event)