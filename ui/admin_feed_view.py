"""
ui/admin_feed_view.py

Central Admin Activity Feed for Nova AI.
Displays real-time incoming & outgoing messages and commands across:
- WhatsApp (Baileys)
- Discord (Superbot)
- Desktop App (Local)
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

_BG_MAIN = "#08080c"
_BG_CARD = "#12121a"
_BORDER = "#1e293b"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"


class AdminFeedView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter = "ALL"
        self._events: list[dict] = []
        self._build_ui()

        # Polling timer for live feed updates
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1800)
        self._poll_timer.timeout.connect(self._fetch_feed)
        self._poll_timer.start()
        self._fetch_feed()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {_BG_MAIN};
                color: {_TEXT_MAIN};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            .card {{
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
            QPushButton {{
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #334155;
            }}
            QPushButton:checked {{
                background-color: #0284c7;
                border-color: #38bdf8;
                color: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header Title
        top_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_lbl = QLabel("CENTRAL ADMIN LIVE FEED")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px;")
        sub_lbl = QLabel("Live real-time feed of all conversations and commands occurring across WhatsApp, Discord, and Desktop.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        top_row.addLayout(title_box)
        top_row.addStretch()

        self.status_pill = QLabel("LIVE STREAM ONLINE")
        self.status_pill.setStyleSheet("color: #10b981; font-weight: 700; font-size: 10px; padding: 4px 10px; background: #064e3b; border-radius: 6px; border: 1px solid #059669;")
        top_row.addWidget(self.status_pill)
        layout.addLayout(top_row)

        # Controls & Filters Row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        lbl_filter = QLabel("Filter:")
        lbl_filter.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600;")
        ctrl_row.addWidget(lbl_filter)

        self.btn_all = QPushButton("All Activity")
        self.btn_all.setCheckable(True)
        self.btn_all.setChecked(True)
        self.btn_all.clicked.connect(lambda: self._set_filter("ALL"))
        ctrl_row.addWidget(self.btn_all)

        self.btn_wa = QPushButton("WhatsApp")
        self.btn_wa.setCheckable(True)
        self.btn_wa.clicked.connect(lambda: self._set_filter("WhatsApp"))
        ctrl_row.addWidget(self.btn_wa)

        self.btn_dc = QPushButton("Discord")
        self.btn_dc.setCheckable(True)
        self.btn_dc.clicked.connect(lambda: self._set_filter("Discord"))
        ctrl_row.addWidget(self.btn_dc)

        self.btn_pc = QPushButton("Desktop")
        self.btn_pc.setCheckable(True)
        self.btn_pc.clicked.connect(lambda: self._set_filter("Desktop"))
        ctrl_row.addWidget(self.btn_pc)

        ctrl_row.addStretch()

        btn_test = QPushButton("Test Event")
        btn_test.clicked.connect(self._send_test_event)
        ctrl_row.addWidget(btn_test)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._fetch_feed)
        ctrl_row.addWidget(btn_refresh)

        btn_clear = QPushButton("Clear Feed")
        btn_clear.clicked.connect(self._clear_feed)
        ctrl_row.addWidget(btn_clear)

        layout.addLayout(ctrl_row)

        # Scroll Area for Events
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: 1px solid #1e293b; border-radius: 8px; background: #0d0d14; }")

        self.events_container = QWidget()
        self.events_layout = QVBoxLayout(self.events_container)
        self.events_layout.setContentsMargins(12, 12, 12, 12)
        self.events_layout.setSpacing(8)
        self.events_layout.addStretch()

        self.scroll.setWidget(self.events_container)
        layout.addWidget(self.scroll)

    def _set_filter(self, flt: str):
        self._filter = flt
        self.btn_all.setChecked(flt == "ALL")
        self.btn_wa.setChecked(flt == "WhatsApp")
        self.btn_dc.setChecked(flt == "Discord")
        self.btn_pc.setChecked(flt == "Desktop")
        self._render_events()

    def _fetch_feed(self):
        try:
            req = urllib.request.Request("http://127.0.0.1:5050/feed", headers={"User-Agent": "NovaUI"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode())
                self._events = data.get("feed", [])
                self._render_events()
                self.status_pill.setText("LIVE STREAM ONLINE")
                self.status_pill.setStyleSheet("color: #10b981; font-weight: 700; font-size: 10px; padding: 4px 10px; background: #064e3b; border-radius: 6px; border: 1px solid #059669;")
        except Exception:
            self.status_pill.setText("BRIDGE OFFLINE (PORT 5050)")
            self.status_pill.setStyleSheet("color: #ef4444; font-weight: 700; font-size: 10px; padding: 4px 10px; background: #450a0a; border-radius: 6px; border: 1px solid #991b1b;")

    def _send_test_event(self):
        try:
            import datetime
            payload = {
                "platform": "Desktop",
                "sender": "Admin",
                "content": f"Test broadcast ping from Nova Admin Feed at {datetime.datetime.now().strftime('%H:%M:%S')}",
                "type": "in"
            }
            req = urllib.request.Request(
                "http://127.0.0.1:5050/feed",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=1.5)
            self._fetch_feed()
        except Exception:
            pass

    def _clear_feed(self):
        self._events.clear()
        self._render_events()

    def _render_events(self):
        # Clear existing items except bottom stretch
        while self.events_layout.count() > 1:
            item = self.events_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        filtered = [e for e in self._events if self._filter == "ALL" or e.get("platform", "").lower() == self._filter.lower()]

        if not filtered:
            empty_lbl = QLabel(f"No activity events recorded yet for '{self._filter}'. Live events will appear automatically.")
            empty_lbl.setStyleSheet("color: #64748b; font-size: 11px; padding: 30px; text-align: center;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self.events_layout.insertWidget(0, empty_lbl)
            return

        for ev in reversed(filtered[-60:]):
            card = self._build_event_card(ev)
            self.events_layout.insertWidget(self.events_layout.count() - 1, card)

    def _build_event_card(self, ev: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #12121a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px;
            }
            QFrame:hover {
                border-color: #38bdf8;
                background-color: #161622;
            }
        """)
        h = QHBoxLayout(card)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(10)

        # Platform Pill
        plt = ev.get("platform", "Platform")
        pill = QLabel(plt.upper())
        pill.setFixedHeight(22)
        if "whatsapp" in plt.lower():
            pill.setStyleSheet("background: #064e3b; color: #34d399; font-weight: 700; font-size: 9px; padding: 2px 8px; border-radius: 4px; border: 1px solid #059669;")
        elif "discord" in plt.lower():
            pill.setStyleSheet("background: #312e81; color: #a5b4fc; font-weight: 700; font-size: 9px; padding: 2px 8px; border-radius: 4px; border: 1px solid #4f46e5;")
        else:
            pill.setStyleSheet("background: #082f49; color: #38bdf8; font-weight: 700; font-size: 9px; padding: 2px 8px; border-radius: 4px; border: 1px solid #0284c7;")
        h.addWidget(pill)

        # Time
        t_str = ev.get("time") or datetime.now().strftime("%H:%M:%S")
        time_lbl = QLabel(t_str)
        time_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-family: Consolas, monospace;")
        h.addWidget(time_lbl)

        # Sender & Message
        sender = ev.get("sender", "User")
        sender_lbl = QLabel(f"<b>{sender}:</b>")
        sender_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        h.addWidget(sender_lbl)

        content = ev.get("content", "")
        msg_lbl = QLabel(content)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("color: #f1f5f9; font-size: 11px;")
        h.addWidget(msg_lbl, 1)

        return card
