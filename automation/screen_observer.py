"""
automation/screen_observer.py

Real-time Screen Observation Engine for the AI Assistant.
Captures screen state, monitors active windows, and provides multimodal vision
context so the AI can see what the user is doing and make informed decisions.
"""

from __future__ import annotations

import ctypes
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PIL import Image, ImageGrab

from utils.app_paths import user_data_dir
from utils.logger import get_logger

log = get_logger(__name__)


def get_active_window_title() -> str:
    """Returns the title of the currently focused window on Windows."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "Desktop"
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return "Active Window"
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value.strip() or "Active Window"
    except Exception as e:
        log.warning("Could not get active window title: {}", e)
        return "Windows Desktop"


def get_open_windows() -> list[str]:
    """Returns a clean list of visible application window titles on Windows."""
    titles: list[str] = []
    try:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    val = buf.value.strip()
                    if val and val not in (
                        "Default IME", "MSCTFIME UI", "Program Manager", "Settings",
                        "Windows Shell Experience Host", "Search"
                    ):
                        if val not in titles:
                            titles.append(val)
            return True

        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception as exc:
        log.warning("Could not enumerate open windows: {}", exc)
    return titles[:12]


class ScreenObserver:
    """Provides instant and continuous screen capture context for the AI."""

    def __init__(self):
        self._temp_dir = user_data_dir() / "temp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._latest_shot: Path | None = None
        self._latest_window_title: str = "Desktop"
        self._is_enabled = False

    def set_enabled(self, enabled: bool) -> None:
        self._is_enabled = enabled
        log.info("Screen observer set to: {}", enabled)

    def is_enabled(self) -> bool:
        return self._is_enabled

    def capture_now(self, max_dim: int = 1280) -> tuple[Path | None, str]:
        """Captures the entire primary screen using Qt (with PIL fallback),
        resizes cleanly for LLM vision, and saves it to disk.
        Returns (image_path, active_window_title).
        """
        window_title = get_active_window_title()
        out_path = self._temp_dir / "screen_observe_latest.jpg"

        # 1. Primary method: Qt Screen Grab
        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0)
                if not pixmap.isNull():
                    if max(pixmap.width(), pixmap.height()) > max_dim:
                        pixmap = pixmap.scaled(
                            max_dim,
                            max_dim,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                    pixmap.save(str(out_path), "JPEG", 85)
                    self._latest_shot = out_path
                    self._latest_window_title = window_title
                    return out_path, window_title
        except Exception as e:
            log.warning("Qt screen grab fallback: {}", e)

        # 2. Secondary fallback: Robust Screen Capture (Qt / Windows GDI BitBlt)
        try:
            from automation.actions import _capture_screen_image
            screenshot = _capture_screen_image()
            w, h = screenshot.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                new_size = (int(w * scale), int(h * scale))
                screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)

            screenshot.convert("RGB").save(str(out_path), "JPEG", quality=85)
            self._latest_shot = out_path
            self._latest_window_title = window_title
            return out_path, window_title
        except Exception as exc:
            log.warning("Screen observation capture failed: {}", exc)
            return None, window_title

    def get_latest_context(self) -> tuple[Path | None, str]:
        """Returns the most recent screen context, or captures a fresh one if missing."""
        if not self._latest_shot or not self._latest_shot.exists():
            return self.capture_now()
        if (time.time() - self._latest_shot.stat().st_mtime) > 5.0:
            return self.capture_now()
        return self._latest_shot, self._latest_window_title


# Global singleton
screen_observer = ScreenObserver()
