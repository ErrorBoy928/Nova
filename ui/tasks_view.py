"""
ui/tasks_view.py

Supercharged Autonomous Task & Automation View for Nova AI.
Contains 3 powerful portions:
- Portion 1: Daily Recurring Automations (Runs daily at set HH:MM, multi-channel alerts to Desktop, WhatsApp, Discord)
- Portion 2: Day Schedule Tasks (One-off scheduled tasks for today with auto notifications)
- Portion 3: Multi-Step Agent Goals (Active complex workflows & sequential pipeline)
"""

from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt, Signal, QTime
from PySide6.QtWidgets import (
    QCheckBox,
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

_BG_MAIN = "#08080c"
_BG_CARD = "#12121a"
_BORDER = "#1e293b"
_ACCENT_BLUE = "#0284c7"
_ACCENT_CYAN = "#38bdf8"
_ACCENT_GREEN = "#10b981"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"


class TasksView(QWidget):
    resume_task_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_theme()
        self._build_ui()
        self._refresh_all()

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {_BG_MAIN};
                color: {_TEXT_MAIN};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid {_BORDER};
                background: #0d0d14;
                border-radius: 8px;
                top: -1px;
            }}
            QTabBar::tab {{
                background: #0a0a10;
                color: {_TEXT_MUTED};
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid {_BORDER};
                border-bottom: none;
                font-weight: 700;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: #0d0d14;
                color: {_ACCENT_CYAN};
                border-color: {_ACCENT_CYAN};
            }}
            QTabBar::tab:hover:!selected {{
                background: #141420;
                color: #ffffff;
            }}
            QLineEdit, QTimeEdit {{
                background-color: #12121a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 7px 10px;
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

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header Title
        title_box = QVBoxLayout()
        title_lbl = QLabel("AUTONOMOUS TASKS & AUTOMATION HUB")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px;")
        sub_lbl = QLabel("Schedule daily recurring routines, organize today's scheduled tasks, or monitor compound sequential pipelines.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        root.addLayout(title_box)

        tabs = QTabWidget()

        # ── PORTION 1: Daily Recurring Automations ────────────────────
        tab_daily = QWidget()
        layout_daily = QVBoxLayout(tab_daily)
        layout_daily.setContentsMargins(14, 14, 14, 14)
        layout_daily.setSpacing(10)

        daily_header = QLabel("<b>Daily Recurring Automations</b> — Executes automatically every day at your set time and alerts your accounts.")
        daily_header.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        layout_daily.addWidget(daily_header)

        # Add Daily Task Box
        add_daily_card = QFrame()
        add_daily_card.setStyleSheet(f"background: #111118; border: 1px solid {_BORDER}; border-radius: 8px; padding: 10px;")
        add_daily_layout = QVBoxLayout(add_daily_card)

        row1 = QHBoxLayout()
        self.input_daily_title = QLineEdit()
        self.input_daily_title.setPlaceholderText("e.g. Morning Tech Briefing & Email Check")
        row1.addWidget(QLabel("Task Name:"))
        row1.addWidget(self.input_daily_title, 2)

        self.time_daily = QTimeEdit()
        self.time_daily.setDisplayFormat("HH:mm")
        self.time_daily.setTime(QTime.currentTime())
        row1.addWidget(QLabel("Time:"))
        row1.addWidget(self.time_daily)
        add_daily_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.input_daily_prompt = QLineEdit()
        self.input_daily_prompt.setPlaceholderText("Command/Prompt: Research latest news and alert WhatsApp & Discord")
        row2.addWidget(QLabel("Command:"))
        row2.addWidget(self.input_daily_prompt, 3)

        self.chk_daily_wa = QCheckBox("WhatsApp")
        self.chk_daily_wa.setChecked(True)
        self.chk_daily_dc = QCheckBox("Discord")
        self.chk_daily_dc.setChecked(True)
        self.chk_daily_pc = QCheckBox("Desktop")
        self.chk_daily_pc.setChecked(True)
        row2.addWidget(self.chk_daily_wa)
        row2.addWidget(self.chk_daily_dc)
        row2.addWidget(self.chk_daily_pc)

        btn_add_daily = QPushButton("+ Add Daily Routine")
        btn_add_daily.clicked.connect(self._add_daily_task)
        row2.addWidget(btn_add_daily)
        add_daily_layout.addLayout(row2)

        layout_daily.addWidget(add_daily_card)

        # List of Daily Tasks
        self.scroll_daily = QScrollArea()
        self.scroll_daily.setWidgetResizable(True)
        self.scroll_daily.setStyleSheet(f"QScrollArea {{ border: 1px solid {_BORDER}; background: #08080c; border-radius: 6px; }}")
        self.daily_container = QWidget()
        self.daily_layout = QVBoxLayout(self.daily_container)
        self.daily_layout.setContentsMargins(8, 8, 8, 8)
        self.daily_layout.setSpacing(6)
        self.daily_layout.addStretch()
        self.scroll_daily.setWidget(self.daily_container)
        layout_daily.addWidget(self.scroll_daily)

        tabs.addTab(tab_daily, "Daily Automations")

        # ── PORTION 2: Day Schedule Tasks ─────────────────────────────
        tab_day = QWidget()
        layout_day = QVBoxLayout(tab_day)
        layout_day.setContentsMargins(14, 14, 14, 14)
        layout_day.setSpacing(10)

        day_header = QLabel("<b>Today's Scheduled Tasks</b> — Pre-schedule one-off tasks for today; Nova will execute them at the exact time.")
        day_header.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        layout_day.addWidget(day_header)

        # Add Day Task Box
        add_day_card = QFrame()
        add_day_card.setStyleSheet(f"background: #111118; border: 1px solid {_BORDER}; border-radius: 8px; padding: 10px;")
        add_day_layout = QVBoxLayout(add_day_card)

        d_row1 = QHBoxLayout()
        self.input_day_title = QLineEdit()
        self.input_day_title.setPlaceholderText("e.g. Run deep project backup & send summary")
        d_row1.addWidget(QLabel("Task:"))
        d_row1.addWidget(self.input_day_title, 2)

        self.time_day = QTimeEdit()
        self.time_day.setDisplayFormat("HH:mm")
        self.time_day.setTime(QTime.currentTime())
        d_row1.addWidget(QLabel("Schedule For:"))
        d_row1.addWidget(self.time_day)
        add_day_layout.addLayout(d_row1)

        d_row2 = QHBoxLayout()
        self.input_day_prompt = QLineEdit()
        self.input_day_prompt.setPlaceholderText("Prompt to execute at schedule time...")
        d_row2.addWidget(QLabel("Prompt:"))
        d_row2.addWidget(self.input_day_prompt, 3)

        btn_add_day = QPushButton("+ Schedule for Today")
        btn_add_day.clicked.connect(self._add_day_task)
        d_row2.addWidget(btn_add_day)
        add_day_layout.addLayout(d_row2)

        layout_day.addWidget(add_day_card)

        # List of Day Tasks
        self.scroll_day = QScrollArea()
        self.scroll_day.setWidgetResizable(True)
        self.scroll_day.setStyleSheet(f"QScrollArea {{ border: 1px solid {_BORDER}; background: #08080c; border-radius: 6px; }}")
        self.day_container = QWidget()
        self.day_layout = QVBoxLayout(self.day_container)
        self.day_layout.setContentsMargins(8, 8, 8, 8)
        self.day_layout.setSpacing(6)
        self.day_layout.addStretch()
        self.scroll_day.setWidget(self.day_container)
        layout_day.addWidget(self.scroll_day)

        tabs.addTab(tab_day, "Day Schedule")

        # ── PORTION 3: Multi-Step Agent Goals ─────────────────────────
        tab_goals = QWidget()
        layout_goals = QVBoxLayout(tab_goals)
        layout_goals.setContentsMargins(14, 14, 14, 14)
        layout_goals.setSpacing(10)

        goals_header = QLabel("<b>Multi-Step Agent Goals</b> — Complex goals executed sequentially across multiple autonomous steps.")
        goals_header.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        layout_goals.addWidget(goals_header)

        self.scroll_goals = QScrollArea()
        self.scroll_goals.setWidgetResizable(True)
        self.scroll_goals.setStyleSheet(f"QScrollArea {{ border: 1px solid {_BORDER}; background: #08080c; border-radius: 6px; }}")
        self.goals_container = QWidget()
        self.goals_layout = QVBoxLayout(self.goals_container)
        self.goals_layout.setContentsMargins(8, 8, 8, 8)
        self.goals_layout.setSpacing(8)
        self.goals_layout.addStretch()
        self.scroll_goals.setWidget(self.goals_container)
        layout_goals.addWidget(self.scroll_goals)

        tabs.addTab(tab_goals, "Compound Goals")

        root.addWidget(tabs)

    def _refresh_all(self):
        self._refresh_daily_tasks()
        self._refresh_day_tasks()
        self._refresh_goals()

    def _add_daily_task(self):
        title = self.input_daily_title.text().strip()
        prompt = self.input_daily_prompt.text().strip()
        time_str = self.time_daily.time().toString("HH:mm")

        if not title or not prompt:
            QMessageBox.warning(self, "Missing Fields", "Please provide both task title and prompt.")
            return

        channels = []
        if self.chk_daily_wa.isChecked(): channels.append("whatsapp")
        if self.chk_daily_dc.isChecked(): channels.append("discord")
        if self.chk_daily_pc.isChecked(): channels.append("desktop")

        db.save_scheduled_task(
            task_type="daily",
            title=title,
            prompt=prompt,
            scheduled_time=time_str,
            notify_channels=",".join(channels)
        )
        self.input_daily_title.clear()
        self.input_daily_prompt.clear()
        self._refresh_daily_tasks()

    def _add_day_task(self):
        title = self.input_day_title.text().strip()
        prompt = self.input_day_prompt.text().strip()
        time_str = self.time_day.time().toString("HH:mm")

        if not title or not prompt:
            QMessageBox.warning(self, "Missing Fields", "Please provide both task title and prompt.")
            return

        db.save_scheduled_task(
            task_type="day_schedule",
            title=title,
            prompt=prompt,
            scheduled_time=time_str,
            notify_channels="desktop,whatsapp,discord"
        )
        self.input_day_title.clear()
        self.input_day_prompt.clear()
        self._refresh_day_tasks()

    def _refresh_daily_tasks(self):
        while self.daily_layout.count() > 1:
            item = self.daily_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tasks = db.get_scheduled_tasks(task_type="daily")
        if not tasks:
            empty = QLabel("No daily automations configured yet. Add your first routine above!")
            empty.setStyleSheet("color: #64748b; font-size: 11px; padding: 20px; text-align: center;")
            empty.setAlignment(Qt.AlignCenter)
            self.daily_layout.insertWidget(0, empty)
            return

        for t in tasks:
            card = self._build_scheduled_card(t, is_daily=True)
            self.daily_layout.insertWidget(self.daily_layout.count() - 1, card)

    def _refresh_day_tasks(self):
        while self.day_layout.count() > 1:
            item = self.day_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tasks = db.get_scheduled_tasks(task_type="day_schedule")
        if not tasks:
            empty = QLabel("No tasks scheduled for today yet. Schedule tasks above!")
            empty.setStyleSheet("color: #64748b; font-size: 11px; padding: 20px; text-align: center;")
            empty.setAlignment(Qt.AlignCenter)
            self.day_layout.insertWidget(0, empty)
            return

        for t in tasks:
            card = self._build_scheduled_card(t, is_daily=False)
            self.day_layout.insertWidget(self.day_layout.count() - 1, card)

    def _build_scheduled_card(self, t: dict, is_daily: bool) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background: #111118; border: 1px solid {_BORDER}; border-radius: 6px; padding: 8px;")
        h = QHBoxLayout(card)
        h.setContentsMargins(6, 4, 6, 4)
        h.setSpacing(10)

        # Time Badge
        time_badge = QLabel(f"{t.get('scheduled_time', '00:00')}")
        time_badge.setStyleSheet(f"background: #082f49; color: {_ACCENT_CYAN}; font-weight: 700; font-size: 10px; padding: 3px 8px; border-radius: 4px;")
        h.addWidget(time_badge)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        lbl_title = QLabel(t.get("title", ""))
        lbl_title.setStyleSheet("font-weight: 700; font-size: 12px; color: #ffffff;")
        lbl_prompt = QLabel(f"Prompt: {t.get('prompt', '')}")
        lbl_prompt.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px;")
        info_box.addWidget(lbl_title)
        info_box.addWidget(lbl_prompt)
        h.addLayout(info_box, 1)

        # Channels Pill
        channels = t.get("notify_channels", "")
        if channels:
            ch_pill = QLabel(f"Alerts: {channels}")
            ch_pill.setStyleSheet("color: #10b981; font-size: 9px; font-weight: 600;")
            h.addWidget(ch_pill)

        # Run Now Button
        btn_run = QPushButton("Run")
        btn_run.setStyleSheet("background: #065f46; color: #6ee7b7; font-size: 10px; padding: 4px 10px; font-weight: 700;")
        btn_run.clicked.connect(lambda: self._execute_now(t))
        h.addWidget(btn_run)

        # Delete Button
        btn_del = QPushButton("Delete")
        btn_del.setFixedHeight(24)
        btn_del.setStyleSheet("background: #450a0a; color: #fca5a5; border-radius: 4px; font-weight: 700; font-size: 10px; padding: 2px 8px;")
        btn_del.clicked.connect(lambda: self._delete_scheduled_task(t.get("id"), is_daily))
        h.addWidget(btn_del)

        return card

    def _execute_now(self, t: dict):
        from utils.task_scheduler import _execute_scheduled_task
        import threading
        threading.Thread(target=_execute_scheduled_task, args=(t,), daemon=True).start()
        QMessageBox.information(self, "Executed", f"Task '{t.get('title')}' is executing in background!")

    def _delete_scheduled_task(self, task_id: int, is_daily: bool):
        db.delete_scheduled_task(task_id)
        if is_daily:
            self._refresh_daily_tasks()
        else:
            self._refresh_day_tasks()

    def _refresh_goals(self):
        while self.goals_layout.count() > 1:
            item = self.goals_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tasks = db.get_all_agent_tasks(limit=30)
        if not tasks:
            empty = QLabel("No active multi-step goals found. Give Nova a multi-step prompt in chat!")
            empty.setStyleSheet("color: #64748b; font-size: 11px; padding: 20px; text-align: center;")
            empty.setAlignment(Qt.AlignCenter)
            self.goals_layout.insertWidget(0, empty)
            return

        for t in tasks:
            card = self._build_goal_card(t)
            self.goals_layout.insertWidget(self.goals_layout.count() - 1, card)

    def _build_goal_card(self, t: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background: #111118; border: 1px solid {_BORDER}; border-radius: 6px; padding: 8px;")
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(4)

        top = QHBoxLayout()
        title = QLabel(t.get("title", "Goal"))
        title.setStyleSheet("font-weight: 700; font-size: 12px; color: #ffffff;")
        top.addWidget(title)
        top.addStretch()

        cur = t.get("current_step", 0)
        tot = t.get("total_steps", 1)
        p_lbl = QLabel(f"{cur}/{tot} Steps")
        p_lbl.setStyleSheet(f"color: {_ACCENT_CYAN}; font-size: 10px; font-weight: 700;")
        top.addWidget(p_lbl)
        v.addLayout(top)

        pbar = QProgressBar()
        pbar.setFixedHeight(5)
        pbar.setTextVisible(False)
        pbar.setRange(0, max(tot, 1))
        pbar.setValue(cur)
        pbar.setStyleSheet(f"QProgressBar {{ background: #1e293b; border-radius: 2px; }} QProgressBar::chunk {{ background: {_ACCENT_CYAN}; border-radius: 2px; }}")
        v.addWidget(pbar)

        return card
