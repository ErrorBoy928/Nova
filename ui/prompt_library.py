"""
ui/prompt_library.py

Interactive Prompt & Automation Library for Nova AI (Ctrl+P).
Provides categorized, production-grade templates for code architecture,
system administration, autonomous deep research, and recurring workflows.
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
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

_BG_MAIN = "#0b0b12"
_BG_CARD = "#12121c"
_BORDER = "#1e293b"
_ACCENT_BLUE = "#0284c7"
_ACCENT_CYAN = "#38bdf8"
_ACCENT_GREEN = "#10b981"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"

_PROMPT_TEMPLATES = [
    # ── Documents & Office Suites ──
    {
        "id": "pdf_report",
        "category": "DOCS",
        "title": "Executive PDF Intelligence Report",
        "desc": "Generate a beautifully styled, publication-grade PDF report with headers, metrics, and tables.",
        "prompt": "Generate a publication-grade executive PDF report saved directly to my Desktop covering: ",
    },
    {
        "id": "word_document",
        "category": "DOCS",
        "title": "Microsoft Word (.docx) Documentation",
        "desc": "Create a fully structured Word document with headers, bullet points, and styled tables.",
        "prompt": "Create a professional Microsoft Word (.docx) document saved directly to my Desktop for: ",
    },
    {
        "id": "pitch_presentation",
        "category": "DOCS",
        "title": "Widescreen PowerPoint (.pptx) Deck",
        "desc": "Create a high-impact slide presentation deck with title slides, bullet items, and key takeaways.",
        "prompt": "Create an executive PowerPoint presentation (.pptx) saved directly to my Desktop with structured slides for: ",
    },
    {
        "id": "financial_excel",
        "category": "DOCS",
        "title": "Financial & Operational Excel Model",
        "desc": "Generate a styled .xlsx spreadsheet with headers, calculations, formulas, and auto-fit columns.",
        "prompt": "Create a styled production Excel spreadsheet (.xlsx) with formulas and summary rows for: ",
    },
    # ── Creative & Media ──
    {
        "id": "ai_image",
        "category": "CREATIVE",
        "title": "High-Resolution AI Concept Art",
        "desc": "Generate a photorealistic or artistic 1024x1024 AI concept image delivered to Desktop.",
        "prompt": "Generate a high-resolution, photorealistic AI image of: ",
    },
    {
        "id": "qr_generator",
        "category": "CREATIVE",
        "title": "Branded Vector QR Code",
        "desc": "Generate a high-contrast, clean QR code for URLs, contact cards, or WiFi networks.",
        "prompt": "Generate a high-contrast QR code image saved to Desktop for: ",
    },
    {
        "id": "memory_anchor",
        "category": "CREATIVE",
        "title": "Permanent Long-Term Memory Anchor",
        "desc": "Store user preferences, project paths, and personal facts in persistent memory.",
        "prompt": "Remember this permanent fact about me and my project in your long-term memory: ",
    },
    # ── Code Engineering ──
    {
        "id": "fullstack_api",
        "category": "CODE",
        "title": "Full-Stack FastAPI & SQLite Engine",
        "desc": "Scaffold a modular, high-performance async REST API with JWT auth and SQLite models.",
        "prompt": "Write a complete, modular FastAPI application with SQLite database integration, JWT authentication endpoints, health telemetry routes, and clean Pydantic schemas.",
    },
    {
        "id": "code_refactor",
        "category": "CODE",
        "title": "Code Refactor & Bottleneck Optimizer",
        "desc": "Profile algorithms, eliminate quadratic complexity, and apply typing and clean architecture.",
        "prompt": "Analyze and optimize this code for sub-millisecond execution latency, vectorized operations, strict type hints, and robust exception safety: ",
    },
    {
        "id": "unit_test_suite",
        "category": "CODE",
        "title": "Exhaustive Pytest & Mocking Suite",
        "desc": "Generate thorough unit tests covering edge cases, network failures, and mocking.",
        "prompt": "Write an exhaustive pytest test suite with mocking for external I/O, edge case verification, fixtures, and parameterized test cases: ",
    },
    {
        "id": "cli_tool",
        "category": "CODE",
        "title": "Command-Line Tool Architecture",
        "desc": "Build an executive CLI utility using argparse or click with colored terminal output.",
        "prompt": "Write a professional Python command-line utility with rich argument parsing, colored progress outputs, subcommands, and graceful Ctrl+C handling: ",
    },
    # ── System Administration ──
    {
        "id": "win_audit",
        "category": "SYSTEM",
        "title": "Windows Deep System Health Audit",
        "desc": "Inspect CPU, memory load, disk partitions, running processes, and event logs.",
        "prompt": "Perform an exhaustive diagnostic audit of current machine hardware, memory pressure, active process tree, and disk health.",
    },
    {
        "id": "system_optimizer",
        "category": "SYSTEM",
        "title": "1-Click Windows Performance Optimizer",
        "desc": "Flush DNS, clean temporary caches, empty Recycle Bin, and optimize memory working set.",
        "prompt": "Run full system optimization: purge temporary files, flush DNS resolver cache, clean Recycle Bin, and report recovered space.",
    },
    {
        "id": "network_diagnostics",
        "category": "SYSTEM",
        "title": "Network Latency & Port Inspector",
        "desc": "Probe DNS resolution, socket connectivity, gateway ping, and listening local ports.",
        "prompt": "Inspect network stack connectivity, latency to primary gateways, and active listening sockets.",
    },
    # ── Autonomous Deep Research ──
    {
        "id": "deep_research",
        "category": "RESEARCH",
        "title": "Multi-Source Autonomous Deep Research",
        "desc": "Query search engines, fetch live article excerpts, and synthesize an intelligence dossier.",
        "prompt": "Conduct comprehensive autonomous deep research across multi-source web intelligence, extracting article excerpts and key takeaways on: ",
    },
    {
        "id": "competitive_matrix",
        "category": "RESEARCH",
        "title": "Technology & Framework Trade-Off Matrix",
        "desc": "Compare architecture alternatives across performance, developer experience, and scalability.",
        "prompt": "Perform an in-depth trade-off evaluation comparing frameworks, analyzing architecture, execution throughput, memory footprint, and production readiness for: ",
    },
    # ── Workflows & Automations ──
    {
        "id": "daily_briefing",
        "category": "WORKFLOW",
        "title": "Daily Executive Morning Briefing",
        "desc": "Generate a unified morning status covering pending tasks, machine telemetry, and news.",
        "prompt": "Provide my daily executive briefing: summarize today's scheduled routines, current system hardware status, and actionable priorities.",
    },
    {
        "id": "schedule_recurring",
        "category": "WORKFLOW",
        "title": "Schedule Daily Recurring Background Task",
        "desc": "Establish a daily scheduled automation routine with multi-channel alerts.",
        "prompt": "Schedule a daily recurring agent automation to run at 09:00 AM that executes: ",
    },
]


class PromptLibraryDialog(QDialog):
    prompt_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nova AI - Prompt & Automation Library")
        self.setFixedSize(680, 520)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._active_category = "ALL"
        self._filter_query = ""

        self._build_ui()
        self._render_cards()

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
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        # Header
        top_row = QHBoxLayout()
        title_box = QVBoxLayout()
        t_lbl = QLabel("PROMPT & AUTOMATION LIBRARY")
        t_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #38bdf8; letter-spacing: 0.8px; font-family: Consolas, monospace;")
        s_lbl = QLabel("Production-grade prompts and agent workflows. Click any template to insert into chat.")
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

        # Search Bar
        search_box = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter templates by title, keyword, or action... (Esc to close)")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #12121a;
                border: 1px solid {_BORDER};
                border-radius: 6px;
                padding: 7px 12px;
                color: #ffffff;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {_ACCENT_CYAN};
            }}
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_box.addWidget(self.search_input)
        card_layout.addLayout(search_box)

        # Category Filter Pills
        cat_row = QHBoxLayout()
        cat_row.setSpacing(6)
        categories = [
            ("ALL", "All Templates"),
            ("DOCS", "Docs & Office"),
            ("CREATIVE", "Creative & Media"),
            ("CODE", "Code & Architecture"),
            ("SYSTEM", "System Admin"),
            ("RESEARCH", "Deep Research"),
            ("WORKFLOW", "Workflows"),
        ]
        self.cat_buttons: list[QPushButton] = []
        for cat_id, cat_name in categories:
            b = QPushButton(cat_name)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(26)
            b.setCheckable(True)
            b.setChecked(cat_id == "ALL")
            b.setProperty("cat_id", cat_id)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: #12121a;
                    color: {_TEXT_MUTED};
                    border: 1px solid {_BORDER};
                    border-radius: 13px;
                    padding: 0 12px;
                    font-size: 10px;
                    font-weight: 700;
                }}
                QPushButton:checked {{
                    background-color: #0284c7;
                    border-color: #38bdf8;
                    color: #ffffff;
                }}
                QPushButton:hover:!checked {{
                    background-color: #1a1a26;
                    color: #ffffff;
                }}
            """)
            b.clicked.connect(lambda _, c=cat_id: self._set_category(c))
            cat_row.addWidget(b)
            self.cat_buttons.append(b)
        cat_row.addStretch()
        card_layout.addLayout(cat_row)

        # Scroll Area for Templates
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #1e293b; border-radius: 8px; background: #08080f; }")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(10, 10, 10, 10)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_container)
        card_layout.addWidget(scroll, 1)

        root.addWidget(card)

    def _set_category(self, cat: str):
        self._active_category = cat
        for btn in self.cat_buttons:
            btn.setChecked(btn.property("cat_id") == cat)
        self._render_cards()

    def _on_search_changed(self, text: str):
        self._filter_query = text.strip().lower()
        self._render_cards()

    def _render_cards(self):
        # Clear items except stretch
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tag_colors = {
            "CODE": ("#38bdf8", "#0369a1"),
            "SYSTEM": ("#10b981", "#059669"),
            "RESEARCH": ("#a855f7", "#7e22ce"),
            "WORKFLOW": ("#f59e0b", "#d97706"),
        }

        matching = []
        for t in _PROMPT_TEMPLATES:
            if self._active_category != "ALL" and t["category"] != self._active_category:
                continue
            if self._filter_query:
                combined = f"{t['title']} {t['desc']} {t['prompt']}".lower()
                if self._filter_query not in combined:
                    continue
            matching.append(t)

        for t in matching:
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background-color: #101018;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                }
                QFrame:hover {
                    border-color: #38bdf8;
                    background-color: #141420;
                }
            """)
            f_layout = QVBoxLayout(frame)
            f_layout.setContentsMargins(12, 10, 12, 10)
            f_layout.setSpacing(6)

            # Top row: Title + Category Pill + Use Button
            top_h = QHBoxLayout()
            cat_c, cat_bg = tag_colors.get(t["category"], ("#38bdf8", "#0284c7"))
            pill = QLabel(t["category"])
            pill.setStyleSheet(f"background: {cat_bg}30; color: {cat_c}; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; border: 1px solid {cat_c}40; font-family: Consolas, monospace;")
            top_h.addWidget(pill)

            title_lbl = QLabel(t["title"])
            title_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #ffffff;")
            top_h.addWidget(title_lbl)
            top_h.addStretch()

            use_btn = QPushButton("Use Prompt")
            use_btn.setFixedSize(86, 24)
            use_btn.setCursor(Qt.PointingHandCursor)
            use_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """)
            use_btn.clicked.connect(lambda _, p=t["prompt"]: self._select_prompt(p))
            top_h.addWidget(use_btn)
            f_layout.addLayout(top_h)

            # Description
            desc_lbl = QLabel(t["desc"])
            desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
            f_layout.addWidget(desc_lbl)

            # Code/Prompt snippet box
            preview = QLabel(t["prompt"])
            preview.setWordWrap(True)
            preview.setStyleSheet("color: #cbd5e1; font-family: Consolas, monospace; font-size: 10px; background: #08080d; padding: 6px; border-radius: 4px; border: 1px solid #1a1a24;")
            f_layout.addWidget(preview)

            self.cards_layout.insertWidget(self.cards_layout.count() - 1, frame)

        if not matching:
            empty = QLabel("No templates match your search filter.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #64748b; font-size: 11px; padding: 30px;")
            self.cards_layout.insertWidget(0, empty)

    def _select_prompt(self, prompt: str):
        self.prompt_selected.emit(prompt)
        self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
