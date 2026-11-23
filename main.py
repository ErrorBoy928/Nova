"""
main.py

Entry point for the AI Desktop Assistant.
Initializes configuration, database, LLM manager, voice systems,
and the modern Assistant Desktop Window.

Run with:
    python main.py
"""

from __future__ import annotations

# Python 3.15 lazy_import safeguard for concurrent.futures and asyncio
import concurrent.futures
from concurrent.futures.thread import ThreadPoolExecutor
concurrent.futures.ThreadPoolExecutor = ThreadPoolExecutor
import asyncio.base_events
asyncio.base_events.concurrent.futures.ThreadPoolExecutor = ThreadPoolExecutor

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is always the first lookup in sys.path
_base_dir = Path(__file__).resolve().parent
if str(_base_dir) not in sys.path:
    sys.path.insert(0, str(_base_dir))
try:
    os.chdir(_base_dir)
except Exception:
    pass

# Load .env from project root
load_dotenv(_base_dir / ".env")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox

from ai.llm_manager import LLMManager
from config.settings_schema import load_config, save_config
from memory.database import init_db
from ui.main_window import MainWindow
from ui.settings_window import SettingsWindow
from utils.bridge_server import start_bridge_server
from utils.task_scheduler import start_scheduler
from utils.global_hotkey import GlobalHotkeyThread
from utils.logger import get_logger
from voice.tts import tts

log = get_logger(__name__)


def _create_app_icon() -> QIcon:
    """Generates a sleek, minimalist geometric monogram vector app icon."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Dark background circle
    painter.setBrush(QColor("#0a0a0a"))
    pen = QPen(QColor("#1e3a8a"), 2.0)
    painter.setPen(pen)
    painter.drawEllipse(3, 3, 58, 58)

    # Inner cyan accent ring
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor("#38bdf8"), 1.5))
    painter.drawEllipse(8, 8, 48, 48)

    # Monogram "N"
    painter.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI", 22, QFont.Bold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 1)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "N")
    painter.end()

    return QIcon(pixmap)


class AssistantApp:
    def __init__(self):
        self.config = load_config()
        init_db()

        # Start Nova Remote Bridge Server (127.0.0.1:5050) & Task Scheduler
        start_bridge_server()
        start_scheduler()

        self.llm_manager = LLMManager(self.config)
        self.main_window = MainWindow(self.config, self.llm_manager)

        icon = _create_app_icon()
        self.main_window.setWindowIcon(icon)

        # System tray icon
        self.tray = self._build_tray(icon)

    def _build_tray(self, icon: QIcon) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(icon)
        tray.setToolTip(f"{self.config.ui.assistant_name} — AI Desktop Assistant")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #0a0a0a;
                color: #f8fafc;
                border: 1px solid #222222;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: white;
            }
        """)
        open_action = menu.addAction("Open Assistant", self._show_main_window)
        menu.addSeparator()

        settings_action = menu.addAction("Settings", self._open_settings)
        menu.addSeparator()

        quit_action = menu.addAction("Quit", self._quit)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            self._show_main_window()

    def _show_main_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _open_settings(self):
        dlg = SettingsWindow(self.config, self.main_window)
        dlg.exec()
        save_config(self.config)

    def _quit(self):
        tts.stop()
        if hasattr(self.main_window, "hotkey_thread"):
            self.main_window.hotkey_thread.stop()
            self.main_window.hotkey_thread.wait()
        save_config(self.config)
        log.info("AI Desktop Assistant shutting down.")
        QApplication.quit()

    def start(self):
        self._show_main_window()
        log.info("AI Desktop Assistant started successfully on Drive E:.")


def main() -> int:
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setApplicationName("AI Desktop Assistant")

        assistant = AssistantApp()
        assistant.start()

        return app.exec()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            crash_file = _base_dir / "crash_log.txt"
            crash_file.write_text(err_msg, encoding="utf-8")
        except Exception:
            pass
        try:
            QMessageBox.critical(
                None,
                "Nova AI Fatal Startup Error",
                f"Failed to launch Nova AI:\n\n{str(e)}\n\nCheck crash_log.txt for full traceback details.",
            )
        except Exception:
            print(err_msg, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
