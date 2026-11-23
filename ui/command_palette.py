"""
ui/command_palette.py

Spotlight / Raycast-style Quick Command Palette for Nova AI (Ctrl+K).
Enables instant search and execution of all system actions, vision tools,
code runners, platform integrations, and navigation views.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class CommandPaletteDialog(QDialog):
    action_triggered = Signal(str, str)  # (action_type, payload)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(540, 380)

        self._commands = [
            ("system_stats", "System Diagnostics", "Inspect CPU load, RAM usage, and disk storage metrics", "SYSTEM"),
            ("clear_temp", "Clean Temporary Files & Cache", "Free up drive space by wiping Windows temp cache", "SYSTEM"),
            ("empty_recycle_bin", "Empty Recycle Bin", "Permanently delete files in Windows recycle bin", "SYSTEM"),
            ("lock", "Lock Workstation", "Immediately lock the current Windows desktop session", "SYSTEM"),
            ("snip_screen", "Snip Desktop Screen", "Select and capture a region of the screen (Ctrl+Shift+D)", "VISION"),
            ("toggle_vision", "Toggle Screen Vision Observer", "Enable/disable live foreground window monitoring", "VISION"),
            ("web_research", "Deep Web Research", "Search the internet autonomously and synthesize findings", "RESEARCH"),
            ("write_python", "Code Architect (Python)", "Generate modular Python script with robust error handling", "CODE"),
            ("run_py_file", "Run Python File...", "Select and execute a local Python script in the background", "CODE"),
            ("nav_tasks", "Open Tasks & Automations Hub", "Manage daily recurring routines and scheduled tasks", "NAV"),
            ("nav_conn", "Open Platform Connections", "Manage WhatsApp Baileys bridge and Discord Bot", "NAV"),
            ("nav_feed", "Open Central Admin Live Feed", "Monitor real-time events across all connected platforms", "NAV"),
            ("nav_settings", "Open Master Settings", "Configure AI models, voice parameters, and API keys", "NAV"),
            ("export_chat", "Export Chat History", "Save conversation log to a clean Markdown (.md) file", "CHAT"),
            ("clear_chat", "Clear Conversation History", "Reset active chat memory and start a fresh session", "CHAT"),
            ("new_chat", "Start New Chat Session (Ctrl+N)", "Create an isolated, parallel conversation thread", "CHAT"),
            ("attach_file", "Attach File Context (Ctrl+O)", "Inject local code, logs, or select image for vision", "TOOL"),
            ("find_chat", "Find in Conversation (Ctrl+F)", "Search keywords across message bubbles with instant highlights", "CHAT"),
            ("open_prompts", "Prompt & Automation Library (Ctrl+P)", "Browse curated code, system, and research templates", "NAV"),
            ("open_artifacts", "Code Artifacts & Scripts Drawer (Ctrl+B)", "Inspect, copy, and run all session scripts", "CODE"),
            ("open_terminal", "Quick PowerShell Terminal Runner (Ctrl+T)", "Run shell commands, git operations, and system probes", "TOOL"),
            ("show_shortcuts", "Keyboard Shortcuts Reference (F1)", "View complete cheat sheet of keys, shortcuts, and commands", "HELP"),
        ]

        self._build_ui()
        self._populate_list("")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        # Outer card frame
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #0b0b12;
                border: 1px solid #222230;
                border-radius: 10px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        # Top search bar row
        search_box = QHBoxLayout()
        search_box.setSpacing(8)

        search_icon = QLabel("N")
        search_icon.setFixedSize(22, 22)
        search_icon.setAlignment(Qt.AlignCenter)
        search_icon.setStyleSheet("background: #0284c7; color: #ffffff; font-weight: 800; font-size: 11px; border-radius: 4px;")
        search_box.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search actions or type a prompt... (Enter to run, Esc to close)")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #f8fafc;
                font-size: 13px;
                font-weight: 600;
                padding: 4px 0;
            }
        """)
        self.search_input.textChanged.connect(self._populate_list)
        search_box.addWidget(self.search_input)

        esc_hint = QLabel("ESC")
        esc_hint.setStyleSheet("background: #181824; color: #64748b; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 3px; border: 1px solid #272738;")
        search_box.addWidget(esc_hint)
        card_layout.addLayout(search_box)

        # Divider line
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #1c1c2a; margin: 2px 0;")
        card_layout.addWidget(div)

        # List Widget for Results
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-radius: 6px;
                padding: 6px 8px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background-color: #171724;
                border: 1px solid #38bdf8;
            }
            QListWidget::item:hover:!selected {
                background-color: #12121d;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._execute_selected)
        card_layout.addWidget(self.list_widget)

        root.addWidget(card)

    def _populate_list(self, filter_text: str):
        self.list_widget.clear()
        query = filter_text.strip().lower()

        matched = []
        for cmd_id, title, desc, tag in self._commands:
            if not query or query in title.lower() or query in desc.lower() or query in tag.lower():
                matched.append((cmd_id, title, desc, tag))

        if not matched and query:
            # Custom prompt execution option
            item = QListWidgetItem()
            item.setData(Qt.UserRole, ("custom_prompt", query))
            w = self._create_item_widget(f"Ask Nova: '{query}'", "Send as prompt to assistant", "PROMPT")
            item.setSizeHint(w.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, w)
            self.list_widget.setCurrentRow(0)
            return

        for cmd_id, title, desc, tag in matched:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, (cmd_id, title))
            w = self._create_item_widget(title, desc, tag)
            item.setSizeHint(w.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, w)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _create_item_widget(self, title: str, desc: str, tag: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(8)

        v = QVBoxLayout()
        v.setSpacing(1)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 700;")
        d_lbl = QLabel(desc)
        d_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        v.addWidget(t_lbl)
        v.addWidget(d_lbl)
        h.addLayout(v, 1)

        tag_lbl = QLabel(tag)
        tag_colors = {
            "SYSTEM": ("#082f49", "#38bdf8"),
            "VISION": ("#3b0764", "#c084fc"),
            "RESEARCH": ("#064e3b", "#34d399"),
            "CODE": ("#431407", "#fb923c"),
            "NAV": ("#1e1b4b", "#818cf8"),
            "CHAT": ("#1c1917", "#a8a29e"),
            "PROMPT": ("#0284c7", "#ffffff"),
        }
        bg, fg = tag_colors.get(tag, ("#1e293b", "#94a3b8"))
        tag_lbl.setStyleSheet(f"background: {bg}; color: {fg}; font-size: 9px; font-weight: 800; padding: 2px 7px; border-radius: 4px;")
        h.addWidget(tag_lbl)
        return w

    def _execute_selected(self):
        item = self.list_widget.currentItem()
        if item:
            data = item.data(Qt.UserRole)
            if data:
                cmd_id, payload = data
                self.action_triggered.emit(cmd_id, payload)
                self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._execute_selected()
        elif key == Qt.Key_Escape:
            self.reject()
        elif key == Qt.Key_Down:
            cur = self.list_widget.currentRow()
            if cur < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(cur + 1)
        elif key == Qt.Key_Up:
            cur = self.list_widget.currentRow()
            if cur > 0:
                self.list_widget.setCurrentRow(cur - 1)
        else:
            super().keyPressEvent(event)
