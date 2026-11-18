"""
ui/tasks_dialog.py

Supercharged Autonomous Task & Automation Manager for Nova AI.
Contains 3 powerful portions:
- Portion 1: ⏰ Daily Recurring Automations (Runs daily at set HH:MM, multi-channel alerts)
- Portion 2: 📅 Day Schedule Tasks (One-off scheduled tasks for today with completion notifications)
- Portion 3: 📋 Multi-Step Agent Goals (Active complex workflows & milestone step tracking)
"""

from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt, Signal, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

import memory.database as db

_BG_BLACK = "#08080c"
_BG_PANEL = "#0d0d14"
_BG_CARD = "#12121a"
_BORDER = "#1e293b"
_ACCENT_BLUE = "#0284c7"
_ACCENT_CYAN = "#38bdf8"
_ACCENT_GREEN = "#10b981"
_ACCENT_PURPLE = "#8b5cf6"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"


class TasksDialog(QDialog):
    resume_task_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nova AI — Autonomous Task & Schedule Engine")
        self.resize(650, 620)
        self.setMinimumSize(560, 520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {_BG_BLACK};
                color: {_TEXT_MAIN};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid {_BORDER};
                background: {_BG_PANEL};
                border-radius: 8px;
                top: -1px;
            }}
            QTabBar::tab {{
                background: #0a0a10;
                color: #94a3b8;
                padding: 9px 18px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid {_BORDER};
                border-bottom: none;
                font-weight: 600;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: {_BG_PANEL};
                color: {_ACCENT_CYAN};
                border-color: {_ACCENT_CYAN};
            }}
            QLineEdit, QTimeEdit {{
                background-color: #12121a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-size: 12px;
            }}
            QPushButton {{
                background-color: {_ACCENT_BLUE};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 700;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #0369a1;
            }}
        """)
        self._build_ui()
        self._load_all()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header Title
        title_box = QVBoxLayout()
        title_lbl = QLabel("⚡ NOVA AUTONOMOUS TASK SYSTEM")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px;")
        sub_lbl = QLabel("Schedule daily automations, manage day workflows, and track autonomous agent goals.")
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {_TEXT_MUTED};")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        root.addLayout(title_box)

        self.tabs = QTabWidget()

        # ── PORTION 1: ⏰ Daily Recurring Automations ────────────────
        tab_daily = QWidget()
        lay_daily = QVBoxLayout(tab_daily)
        lay_daily.setContentsMargins(14, 14, 14, 14)
        lay_daily.setSpacing(10)

        # Add Daily Form Card
        add_daily_card = QFrame()
        add_daily_card.setStyleSheet(f"background: {_BG_CARD}; border: 1px solid {_BORDER}; border-radius: 8px; padding: 10px;")
        d_form = QVBoxLayout(add_daily_card)
        d_form.setSpacing(8)

        lbl_form1 = QLabel("➕ Add New Daily Recurring Automation")
        lbl_form1.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 12px;")
        d_form.addWidget(lbl_form1)

        row_d1 = QHBoxLayout()
        self.d_prompt_input = QLineEdit()
        self.d_prompt_input.setPlaceholderText("E.g. Check unread emails and summarize, clean temp files...")
        row_d1.addWidget(self.d_prompt_input, 1)

        row_d1.addWidget(QLabel("Time:"))
        self.d_time_input = QTimeEdit()
        self.d_time_input.setTime(QTime(9, 0))
        self.d_time_input.setDisplayFormat("HH:mm")
        row_d1.addWidget(self.d_time_input)

        add_d_btn = QPushButton("Save Daily Task")
        add_d_btn.clicked.connect(self._save_daily_task)
        row_d1.addWidget(add_d_btn)
        d_form.addLayout(row_d1)

        row_d2 = QHBoxLayout()
        row_d2.addWidget(QLabel("Notify On:"))
        self.d_chk_app = QCheckBox("Desktop Toast")
        self.d_chk_app.setChecked(True)
        self.d_chk_wa = QCheckBox("WhatsApp (+92 334 7973707)")
        self.d_chk_wa.setChecked(True)
        self.d_chk_dc = QCheckBox("Discord DM")
        self.d_chk_dc.setChecked(True)
        row_d2.addWidget(self.d_chk_app)
        row_d2.addWidget(self.d_chk_wa)
        row_d2.addWidget(self.d_chk_dc)
        row_d2.addStretch()
        d_form.addLayout(row_d2)

        lay_daily.addWidget(add_daily_card)

        # Daily Tasks List
        self.scroll_daily = QScrollArea()
        self.scroll_daily.setWidgetResizable(True)
        self.scroll_daily.setStyleSheet(f"background: transparent; border: 1px solid {_BORDER}; border-radius: 8px;")
        self.cont_daily = QWidget()
        self.cont_daily.setStyleSheet("background: transparent;")
        self.lay_daily_list = QVBoxLayout(self.cont_daily)
        self.lay_daily_list.setSpacing(8)
        self.lay_daily_list.addStretch()
        self.scroll_daily.setWidget(self.cont_daily)
        lay_daily.addWidget(self.scroll_daily, 1)

        self.tabs.addTab(tab_daily, "⏰ Daily Automations")

        # ── PORTION 2: 📅 Day Schedule / One-Off Tasks ───────────────
        tab_sched = QWidget()
        lay_sched = QVBoxLayout(tab_sched)
        lay_sched.setContentsMargins(14, 14, 14, 14)
        lay_sched.setSpacing(10)

        add_sched_card = QFrame()
        add_sched_card.setStyleSheet(f"background: {_BG_CARD}; border: 1px solid {_BORDER}; border-radius: 8px; padding: 10px;")
        s_form = QVBoxLayout(add_sched_card)
        s_form.setSpacing(8)

        lbl_form2 = QLabel("➕ Schedule One-Off Task for Today")
        lbl_form2.setStyleSheet("font-weight: 700; color: #10b981; font-size: 12px;")
        s_form.addWidget(lbl_form2)

        row_s1 = QHBoxLayout()
        self.s_prompt_input = QLineEdit()
        self.s_prompt_input.setPlaceholderText("E.g. Web research quantum computing and email report, run python script...")
        row_s1.addWidget(self.s_prompt_input, 1)

        row_s1.addWidget(QLabel("Time:"))
        self.s_time_input = QTimeEdit()
        now_time = QTime.currentTime()
        self.s_time_input.setTime(now_time.addSecs(3600))
        self.s_time_input.setDisplayFormat("HH:mm")
        row_s1.addWidget(self.s_time_input)

        add_s_btn = QPushButton("Schedule Task")
        add_s_btn.setStyleSheet("background-color: #059669;")
        add_s_btn.clicked.connect(self._save_day_schedule_task)
        row_s1.addWidget(add_s_btn)
        s_form.addLayout(row_s1)

        lay_sched.addWidget(add_sched_card)

        # Scheduled Tasks List
        self.scroll_sched = QScrollArea()
        self.scroll_sched.setWidgetResizable(True)
        self.scroll_sched.setStyleSheet(f"background: transparent; border: 1px solid {_BORDER}; border-radius: 8px;")
        self.cont_sched = QWidget()
        self.cont_sched.setStyleSheet("background: transparent;")
        self.lay_sched_list = QVBoxLayout(self.cont_sched)
        self.lay_sched_list.setSpacing(8)
        self.lay_sched_list.addStretch()
        self.scroll_sched.setWidget(self.cont_sched)
        lay_sched.addWidget(self.scroll_sched, 1)

        self.tabs.addTab(tab_sched, "📅 Day Schedule")

        # ── PORTION 3: 📋 Multi-Step Agent Goals ────────────────────
        tab_goals = QWidget()
        lay_goals = QVBoxLayout(tab_goals)
        lay_goals.setContentsMargins(14, 14, 14, 14)
        lay_goals.setSpacing(10)

        self.scroll_goals = QScrollArea()
        self.scroll_goals.setWidgetResizable(True)
        self.scroll_goals.setStyleSheet(f"background: transparent; border: 1px solid {_BORDER}; border-radius: 8px;")
        self.cont_goals = QWidget()
        self.cont_goals.setStyleSheet("background: transparent;")
        self.lay_goals_list = QVBoxLayout(self.cont_goals)
        self.lay_goals_list.setSpacing(8)
        self.lay_goals_list.addStretch()
        self.scroll_goals.setWidget(self.cont_goals)
        lay_goals.addWidget(self.scroll_goals, 1)

        self.tabs.addTab(tab_goals, "📋 Multi-Step Agent Goals")

        root.addWidget(self.tabs)

        # Bottom Close Button
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background-color: #1e293b; color: #94a3b8;")
        btn_close.clicked.connect(self.accept)
        root.addWidget(btn_close)

    def _save_daily_task(self):
        prompt = self.d_prompt_input.text().strip()
        t_time = self.d_time_input.time().toString("HH:mm")
        if not prompt:
            QMessageBox.warning(self, "Prompt Required", "Please enter a task prompt to automate.")
            return

        db.save_scheduled_task(
            task_type="daily_recurring",
            prompt=prompt,
            target_time=t_time,
            notify_app=self.d_chk_app.isChecked(),
            notify_wa=self.d_chk_wa.isChecked(),
            notify_dc=self.d_chk_dc.isChecked()
        )
        self.d_prompt_input.clear()
        self._load_daily_tasks()
        QMessageBox.information(self, "Daily Task Saved", f"✅ Nova will run this daily at {t_time} and notify you!")

    def _save_day_schedule_task(self):
        prompt = self.s_prompt_input.text().strip()
        t_time = self.s_time_input.time().toString("HH:mm")
        if not prompt:
            QMessageBox.warning(self, "Prompt Required", "Please enter a task prompt.")
            return

        db.save_scheduled_task(
            task_type="day_schedule",
            prompt=prompt,
            target_time=t_time,
            notify_app=True,
            notify_wa=True,
            notify_dc=True
        )
        self.s_prompt_input.clear()
        self._load_scheduled_tasks()
        QMessageBox.information(self, "Task Scheduled", f"✅ Task scheduled for execution today at {t_time}!")

    def _load_all(self):
        self._load_daily_tasks()
        self._load_scheduled_tasks()
        self._load_agent_goals()

    def _load_daily_tasks(self):
        while self.lay_daily_list.count() > 1:
            child = self.lay_daily_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        tasks = db.get_scheduled_tasks("daily_recurring")
        if not tasks:
            empty = QLabel("No daily automations scheduled yet. Add one above!")
            empty.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 11px; padding: 20px;")
            empty.setAlignment(Qt.AlignCenter)
            self.lay_daily_list.insertWidget(0, empty)
            return

        for t in tasks:
            card = self._create_sched_card(t)
            self.lay_daily_list.insertWidget(self.lay_daily_list.count() - 1, card)

    def _load_scheduled_tasks(self):
        while self.lay_sched_list.count() > 1:
            child = self.lay_sched_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        tasks = db.get_scheduled_tasks("day_schedule")
        if not tasks:
            empty = QLabel("No tasks scheduled for today. Add one above!")
            empty.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 11px; padding: 20px;")
            empty.setAlignment(Qt.AlignCenter)
            self.lay_sched_list.insertWidget(0, empty)
            return

        for t in tasks:
            card = self._create_sched_card(t)
            self.lay_sched_list.insertWidget(self.lay_sched_list.count() - 1, card)

    def _create_sched_card(self, t: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background: {_BG_CARD}; border: 1px solid {_BORDER}; border-radius: 8px; padding: 10px;")
        lay = QHBoxLayout(card)
        lay.setSpacing(10)

        # Time pill
        time_pill = QLabel(t["target_time"])
        time_pill.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 12px; background: #0c2d48; padding: 4px 10px; border-radius: 6px;")
        lay.addWidget(time_pill)

        # Info
        info_lay = QVBoxLayout()
        prompt_lbl = QLabel(t["prompt"])
        prompt_lbl.setStyleSheet("font-weight: 700; color: #ffffff; font-size: 12px;")
        info_lay.addWidget(prompt_lbl)

        st_text = "✅ COMPLETED" if t["status"] == "completed" else "⏳ ACTIVE"
        st_color = "#10b981" if t["status"] == "completed" else "#f59e0b"
        status_lbl = QLabel(f"Status: {st_text} | Last Run: {t.get('last_run') or 'Pending'}")
        status_lbl.setStyleSheet(f"color: {st_color}; font-size: 10px;")
        info_lay.addWidget(status_lbl)
        lay.addLayout(info_lay, 1)

        # Delete btn
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; font-size: 10px; padding: 4px 10px;")
        del_btn.clicked.connect(lambda checked=False, tid=t["id"]: self._delete_sched(tid))
        lay.addWidget(del_btn)

        return card

    def _delete_sched(self, tid: str):
        db.delete_scheduled_task(tid)
        self._load_daily_tasks()
        self._load_scheduled_tasks()

    def _load_agent_goals(self):
        while self.lay_goals_list.count() > 1:
            child = self.lay_goals_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        tasks = db.get_all_agent_tasks(limit=15)
        if not tasks:
            empty = QLabel("No active agent goals. Give Nova a multi-step task to auto-save goals!")
            empty.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 11px; padding: 20px;")
            empty.setAlignment(Qt.AlignCenter)
            self.lay_goals_list.insertWidget(0, empty)
            return

        for t in tasks:
            card = self._create_goal_card(t)
            self.lay_goals_list.insertWidget(self.lay_goals_list.count() - 1, card)

    def _create_goal_card(self, t: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background: {_BG_CARD}; border: 1px solid {_BORDER}; border-radius: 8px; padding: 10px;")
        lay = QVBoxLayout(card)
        lay.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(t["title"])
        title.setStyleSheet("font-weight: 700; color: #ffffff; font-size: 12px;")
        header.addWidget(title)
        header.addStretch()

        st = t["status"].upper()
        badge = QLabel(st)
        badge_color = "#10b981" if st == "COMPLETED" else "#38bdf8"
        badge.setStyleSheet(f"color: {badge_color}; font-weight: 700; font-size: 10px;")
        header.addWidget(badge)
        lay.addLayout(header)

        # Step Progress
        steps = t.get("steps", [])
        cur = t.get("current_step", 0) + 1
        tot = len(steps)
        pbar = QProgressBar()
        pbar.setRange(0, max(tot, 1))
        pbar.setValue(min(cur, tot))
        pbar.setFixedHeight(6)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(f"QProgressBar {{ background: #1e293b; border-radius: 3px; }} QProgressBar::chunk {{ background: {_ACCENT_BLUE}; border-radius: 3px; }}")
        lay.addWidget(pbar)

        step_lbl = QLabel(f"Milestones: Step {cur} of {tot}")
        step_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px;")
        lay.addWidget(step_lbl)

        return card
