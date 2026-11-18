"""
utils/global_hotkey.py

Registers global Windows Hotkeys:
- Ctrl + Shift + D: Trigger Screen Snipping
- Ctrl + Shift + N: Summon / Toggle NOVA Assistant Window
"""

from __future__ import annotations

import ctypes
import sys
from PySide6.QtCore import QThread, Signal
from utils.logger import get_logger

log = get_logger(__name__)

MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_D = 0x44
VK_N = 0x4E


class GlobalHotkeyThread(QThread):
    hotkey_triggered = Signal()  # For screen snip
    summon_triggered = Signal()  # For toggle Nova window

    def __init__(self):
        super().__init__()
        self.running = True
        self.win32_thread_id = 0

    def run(self) -> None:
        if sys.platform != "win32":
            return

        self.win32_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        user32 = ctypes.windll.user32
        hotkey_snip = 101
        hotkey_summon = 102

        user32.RegisterHotKey(0, hotkey_snip, MOD_CONTROL | MOD_SHIFT, VK_D)
        user32.RegisterHotKey(0, hotkey_summon, MOD_CONTROL | MOD_SHIFT, VK_N)

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", ctypes.c_void_p),
                ("lParam", ctypes.c_void_p),
                ("time", ctypes.c_uint),
                ("pt", ctypes.c_long * 2),
            ]

        msg = MSG()
        while self.running:
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret > 0:
                if msg.message == WM_HOTKEY:
                    if msg.wParam == hotkey_snip:
                        self.hotkey_triggered.emit()
                    elif msg.wParam == hotkey_summon:
                        self.summon_triggered.emit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                break

        user32.UnregisterHotKey(0, hotkey_snip)
        user32.UnregisterHotKey(0, hotkey_summon)


    def stop(self) -> None:
        self.running = False
        if sys.platform == "win32" and self.win32_thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.win32_thread_id, WM_QUIT, 0, 0)
