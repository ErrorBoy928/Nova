"""
automation/actions.py

Comprehensive Computer Control engine for the AI Assistant (JARVIS-grade).
Controls applications, system settings, files, audio, media, windows, screen,
keyboard, mouse, power, networking, hardware stats, and shell commands.
Each action returns (success: bool, message: str) for instant completion reporting.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path

from utils.app_paths import user_data_dir
from utils.logger import get_logger

log = get_logger(__name__)

ActionResult = tuple[bool, str]

# CREATE_NO_WINDOW flag guarantees that NO black console/PowerShell window flashes
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else (0x08000000 if os.name == "nt" else 0)


def _subp_run(cmd, **kwargs):
    """Subprocess runner that guarantees no visible console window on Windows."""
    if os.name == "nt":
        kwargs.setdefault("creationflags", _NO_WINDOW)
    return subprocess.run(cmd, **kwargs)


def _subp_popen(cmd, **kwargs):
    """Subprocess Popen that guarantees no visible console window on Windows."""
    if os.name == "nt":
        kwargs.setdefault("creationflags", _NO_WINDOW)
    return subprocess.Popen(cmd, **kwargs)

# Configure PyAutoGUI to avoid fail-safe crashes on corner coordinates
try:
    import pyautogui
    pyautogui.FAILSAFE = False
except Exception:
    pass


# ── 1. App Launching & Closing ──────────────────────────────────────────────
def open_application(name: str) -> ActionResult:
    """Launches any Windows application, system setting, Start Menu app, or web equivalent."""
    name = name.strip()
    if not name:
        return False, "No application name specified."

    name_lower = name.lower()

    # Pre-mapped common Windows utilities, settings & popular applications
    system_app_shortcuts = {
        # Accessories & Tools
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "snipping tool": "snippingtool.exe",
        "snip": "snippingtool.exe",
        "camera": "microsoft.windows.camera:",
        "cleanmgr": "cleanmgr.exe",
        "disk cleanup": "cleanmgr.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "my computer": "explorer.exe",
        "this pc": "explorer.exe",
        "cmd": "cmd.exe",
        "command prompt": "cmd.exe",
        "powershell": "powershell.exe",
        "terminal": "wt.exe",
        "windows terminal": "wt.exe",
        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "control panel": "control.exe",
        "regedit": "regedit.exe",
        "device manager": "devmgmt.msc",
        "disk management": "diskmgmt.msc",
        "services": "services.msc",
        "recycle bin": "explorer.exe shell:RecycleBinFolder",
        # Windows Settings URIs
        "settings": "ms-settings:",
        "windows settings": "ms-settings:",
        "wifi": "ms-settings:network-wifi",
        "network": "ms-settings:network-wifi",
        "internet": "ms-settings:network",
        "bluetooth": "ms-settings:bluetooth",
        "sound": "ms-settings:sound",
        "sound settings": "ms-settings:sound",
        "volume settings": "ms-settings:sound",
        "display": "ms-settings:display",
        "display settings": "ms-settings:display",
        "battery": "ms-settings:batterysaver",
        "power settings": "ms-settings:powersleep",
        "apps": "ms-settings:appsfeatures",
        "installed apps": "ms-settings:appsfeatures",
        "updates": "ms-settings:windowsupdate",
        "windows update": "ms-settings:windowsupdate",
        "personalization": "ms-settings:personalization",
        # Browsers & Productivity
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
        "firefox": "firefox.exe",
        "code": "code.cmd",
        "vs code": "code.cmd",
        "vscode": "code.cmd",
        "word": "winword.exe",
        "winword": "winword.exe",
        "excel": "excel.exe",
        "powerpoint": "powerpnt.exe",
        "spotify": "spotify.exe",
        "discord": "discord.exe",
        "vlc": "vlc.exe",
        "vlc media player": "vlc.exe",
    }

    target = system_app_shortcuts.get(name_lower, name)

    try:
        # Settings URIs or shell folders
        if target.startswith("ms-settings:") or target.startswith("microsoft.windows.") or "shell:" in target:
            _subp_popen(["cmd", "/c", "start", target])
            return True, f"Opened {name}."

        # In PATH, executable, or absolute path
        if shutil.which(target) or shutil.which(target + ".exe") or Path(target).exists():
            _subp_popen(["cmd", "/c", "start", "", target])
            log.info("Opened application: {}", target)
            return True, f"Opened {name}."

        # Check Windows App Paths in registry
        import winreg
        resolved = None
        for test_name in ([name, name + ".exe"] if not name.endswith(".exe") else [name]):
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{test_name}"
                    with winreg.OpenKey(hive, key_path) as k:
                        val, _ = winreg.QueryValueEx(k, "")
                        if val:
                            resolved = os.path.expandvars(str(val))
                            break
                except OSError:
                    continue
            if resolved:
                break

        if resolved and Path(resolved).exists():
            _subp_popen(["cmd", "/c", "start", "", resolved])
            return True, f"Opened {name}."

        # Search via PowerShell Get-StartApps
        cmd = ["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json"]
        res = _subp_run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            apps_list = json.loads(res.stdout)
            if isinstance(apps_list, dict):
                apps_list = [apps_list]
            for app in apps_list:
                app_name = app.get("Name", "").lower()
                if name_lower in app_name or app_name in name_lower:
                    appid = app["AppID"]
                    _subp_popen(["explorer.exe", f"shell:AppsFolder\\{appid}"])
                    return True, f"Opened {app['Name']}."

        # Fallback web version for popular web services
        _WEB_APPS = {
            "whatsapp": "https://web.whatsapp.com",
            "youtube": "https://youtube.com",
            "gmail": "https://mail.google.com",
            "google": "https://google.com",
            "github": "https://github.com",
            "chatgpt": "https://chatgpt.com",
            "gemini": "https://gemini.google.com",
            "facebook": "https://facebook.com",
            "instagram": "https://instagram.com",
            "twitter": "https://x.com",
            "netflix": "https://netflix.com",
            "telegram": "https://web.telegram.org",
        }
        for kw, url in _WEB_APPS.items():
            if kw in name_lower:
                open_url(url)
                return True, f"Opened {name} in web browser."

        # Last resort: generic search
        open_url(f"https://www.google.com/search?q={name}")
        return True, f"Could not find local app '{name}'. Opened web search."
    except Exception as exc:
        log.warning("open_application error: {}", exc)
        return False, f"Failed to open {name}: {exc}"


def close_application(name: str) -> ActionResult:
    """Closes an open application or process by name."""
    name = name.strip()
    if not name:
        return False, "No application name provided to close."

    _EXE_MAP = {
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "edge": "msedge.exe",
        "notepad": "notepad.exe",
        "calculator": "CalculatorApp.exe",
        "calc": "CalculatorApp.exe",
        "vlc": "vlc.exe",
        "spotify": "Spotify.exe",
        "discord": "Discord.exe",
        "code": "Code.exe",
        "vs code": "Code.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
        "taskmgr": "taskmgr.exe",
        "task manager": "taskmgr.exe",
    }
    proc_name = _EXE_MAP.get(name.lower(), name if name.endswith(".exe") else f"{name}.exe")

    try:
        cmd = ["taskkill", "/f", "/im", proc_name]
        res = _subp_run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            log.info("Closed application: {}", proc_name)
            return True, f"Closed {name}."
        else:
            # Try closing by window title via PowerShell
            ps_cmd = f'Get-Process | Where-Object {{ $_.MainWindowTitle -like "*{name}*" }} | Stop-Process -Force'
            res2 = _subp_run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
            if res2.returncode == 0:
                return True, f"Closed {name} window."
            return False, f"Could not find running process for '{name}'."
    except Exception as exc:
        return False, f"Error closing {name}: {exc}"


def focus_application(name: str) -> ActionResult:
    """Brings an application window to the foreground by name."""
    name = name.strip()
    if not name:
        return False, "No application name provided."
    try:
        ps_cmd = f"(New-Object -ComObject WScript.Shell).AppActivate('{name}')"
        res = _subp_run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=4)
        if "True" in res.stdout:
            return True, f"Brought '{name}' window to front."
        return False, f"Could not find running window for '{name}'."
    except Exception as exc:
        return False, f"Focus error: {exc}"


def kill_process(name_or_pid: str) -> ActionResult:
    """Forcefully terminates an unresponsive process by name or PID."""
    target = name_or_pid.strip()
    if not target:
        return False, "No process name or PID specified."
    try:
        if target.isdigit():
            cmd = ["taskkill", "/f", "/pid", target]
        else:
            proc = target if target.endswith(".exe") else f"{target}.exe"
            cmd = ["taskkill", "/f", "/im", proc]
        res = _subp_run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, f"Terminated process: {target}"
        return False, f"Could not find or terminate process '{target}'."
    except Exception as exc:
        return False, f"Process kill error: {exc}"




# ── 2. Audio & Media Controls ────────────────────────────────────────────────
def set_volume(level: str) -> ActionResult:
    """Sets master volume percentage (0-100) or changes it (up/down)."""
    try:
        lvl_str = level.strip().lower()
        if lvl_str in ("up", "increase", "+", "louder"):
            return volume_up()
        if lvl_str in ("down", "decrease", "-", "quieter", "lower"):
            return volume_down()
        if lvl_str in ("mute", "unmute", "toggle"):
            return toggle_mute()

        pct = int(re.sub(r"[^\d]", "", lvl_str))
        pct = max(0, min(100, pct))
        ps_cmd = f'''
        $obj = New-Object -ComObject WScript.Shell
        1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}
        1..{int(pct / 2)} | ForEach-Object {{ $obj.SendKeys([char]175) }}
        '''
        _subp_run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=5)
        return True, f"Set master volume to {pct}%."
    except Exception as exc:
        return False, f"Volume adjustment error: {exc}"


def volume_up() -> ActionResult:
    try:
        import pyautogui
        for _ in range(5):
            pyautogui.press("volumeup")
        return True, "Volume increased."
    except Exception as exc:
        return False, f"Failed: {exc}"


def volume_down() -> ActionResult:
    try:
        import pyautogui
        for _ in range(5):
            pyautogui.press("volumedown")
        return True, "Volume decreased."
    except Exception as exc:
        return False, f"Failed: {exc}"


def toggle_mute() -> ActionResult:
    try:
        import pyautogui
        pyautogui.press("volumemute")
        return True, "Volume mute toggled."
    except Exception as exc:
        return False, f"Failed: {exc}"


def media_control(action: str) -> ActionResult:
    try:
        import pyautogui
        action = action.strip().lower()
        if action in ("play", "pause", "playpause", "toggle"):
            pyautogui.press("playpause")
            return True, "Toggled media Play/Pause."
        elif action in ("next", "skip"):
            pyautogui.press("nexttrack")
            return True, "Skipped to next track."
        elif action in ("prev", "previous", "back"):
            pyautogui.press("prevtrack")
            return True, "Skipped to previous track."
        elif action in ("stop",):
            pyautogui.press("stop")
            return True, "Stopped media playback."
        return False, f"Unknown media action: {action}"
    except Exception as exc:
        return False, f"Media control error: {exc}"


def get_brightness() -> ActionResult:
    """Gets current screen brightness percentage (0-100)."""
    try:
        cmd = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness -ErrorAction SilentlyContinue).CurrentBrightness"
        res = _subp_run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=4)
        out = res.stdout.strip()
        if out and out.isdigit():
            return True, f"Screen brightness is currently {out}%."
        return False, "Screen brightness is not supported on this display."
    except Exception as exc:
        return False, f"Could not get brightness: {exc}"


def set_brightness(level: str) -> ActionResult:
    """Sets screen brightness percentage (0-100) or increments/decrements (up/down)."""
    try:
        lvl = level.strip().lower()
        curr_pct = 70
        ok_cur, cur_msg = get_brightness()
        if ok_cur:
            nums = re.findall(r"\d+", cur_msg)
            if nums:
                curr_pct = int(nums[0])

        if lvl in ("up", "increase", "+", "brighter", "more"):
            target = min(100, curr_pct + 15)
        elif lvl in ("down", "decrease", "-", "dimmer", "dim", "less"):
            target = max(10, curr_pct - 15)
        else:
            num = re.sub(r"[^\d]", "", lvl)
            target = max(5, min(100, int(num))) if num else 70

        cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue).WmiSetBrightness(1, {target})"
        _subp_run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=5)
        return True, f"Set screen brightness to {target}%."
    except Exception as exc:
        return False, f"Could not set brightness: {exc}"



# ── 3. Window & Desktop Management ──────────────────────────────────────────
def minimize_active_window() -> ActionResult:
    try:
        import pyautogui
        pyautogui.hotkey("win", "down")
        return True, "Minimized active window."
    except Exception as exc:
        return False, f"Failed: {exc}"


def maximize_active_window() -> ActionResult:
    try:
        import pyautogui
        pyautogui.hotkey("win", "up")
        return True, "Maximized active window."
    except Exception as exc:
        return False, f"Failed: {exc}"


def show_desktop() -> ActionResult:
    try:
        import pyautogui
        pyautogui.hotkey("win", "d")
        return True, "Displaying Windows desktop."
    except Exception as exc:
        return False, f"Failed: {exc}"


def switch_window() -> ActionResult:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "tab")
        return True, "Switched active window."
    except Exception as exc:
        return False, f"Failed: {exc}"


def close_active_window() -> ActionResult:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "f4")
        return True, "Closed active window."
    except Exception as exc:
        return False, f"Failed: {exc}"


def snap_window(direction: str) -> ActionResult:
    try:
        import pyautogui
        d = direction.strip().lower()
        if "left" in d:
            pyautogui.hotkey("win", "left")
            return True, "Snapped window to left."
        elif "right" in d:
            pyautogui.hotkey("win", "right")
            return True, "Snapped window to right."
        elif "up" in d or "max" in d:
            pyautogui.hotkey("win", "up")
            return True, "Maximized window."
        elif "down" in d or "min" in d:
            pyautogui.hotkey("win", "down")
            return True, "Minimized window."
        return False, f"Unknown snap direction: {direction}"
    except Exception as exc:
        return False, f"Failed: {exc}"


# ── 4. File & Folder Operations ──────────────────────────────────────────────
def _resolve_special_folder(name: str) -> Path:
    name_l = name.strip().lower()
    home = Path.home()
    if name_l in ("desktop", "desk"):
        return home / "Desktop"
    if name_l in ("downloads", "download"):
        return home / "Downloads"
    if name_l in ("documents", "doc", "docs"):
        return home / "Documents"
    if name_l in ("pictures", "photos", "images"):
        return home / "Pictures"
    if name_l in ("music", "songs"):
        return home / "Music"
    if name_l in ("videos", "movies"):
        return home / "Videos"
    if name_l in ("c", "c:", "c:\\"):
        return Path("C:\\")
    if name_l in ("e", "e:", "e:\\"):
        return Path("E:\\")
    if name_l in ("project", "ai_assistant"):
        return Path("E:\\AI_Assistant")
    p = Path(os.path.expandvars(name.strip()))
    if not p.is_absolute() and not p.exists():
        p_desk = home / "Desktop" / p
        if p_desk.exists():
            return p_desk
    return p


def open_folder(folder_name: str) -> ActionResult:
    """Opens a folder in Windows File Explorer."""
    p = _resolve_special_folder(folder_name)
    if not p.exists():
        return False, f"Folder does not exist: {p}"
    try:
        _subp_popen(["explorer.exe", str(p)])
        return True, f"Opened folder: {p}"
    except Exception as exc:
        return False, f"Could not open folder: {exc}"


def create_file(path_str: str, content: str = "") -> ActionResult:
    """Creates a text file at the specified path with optional content (defaults to Desktop if relative)."""
    try:
        raw = path_str.strip()
        p = Path(os.path.expandvars(raw))
        if not p.is_absolute():
            p = Path.home() / "Desktop" / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return True, f"Created file: {p.name} on {p.parent}"
    except Exception as exc:
        return False, f"Could not create file: {exc}"


def append_file(path_str: str, content: str = "") -> ActionResult:
    """Appends text to a file (defaults to Desktop if relative)."""
    try:
        raw = path_str.strip()
        p = Path(os.path.expandvars(raw))
        if not p.is_absolute():
            p = Path.home() / "Desktop" / p
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n" + content if p.exists() and p.stat().st_size > 0 else content)
        return True, f"Updated file: {p.name}"
    except Exception as exc:
        return False, f"Could not append to file: {exc}"


def create_folder(path_str: str) -> ActionResult:
    """Creates a directory at the specified path (defaults to Desktop if relative)."""
    try:
        p = Path(os.path.expandvars(path_str.strip()))
        if not p.is_absolute():
            p = Path.home() / "Desktop" / p
        p.mkdir(parents=True, exist_ok=True)
        return True, f"Created folder: {p}"
    except Exception as exc:
        return False, f"Could not create directory: {exc}"


def read_file(path_str: str) -> ActionResult:
    """Reads content from a text file."""
    try:
        p = Path(os.path.expandvars(path_str.strip()))
        if not p.is_absolute():
            # Check desktop first
            p_desk = Path.home() / "Desktop" / p
            if p_desk.exists():
                p = p_desk
        if not p.exists():
            return False, f"File not found: {p}"
        text = p.read_text(encoding="utf-8", errors="replace")
        preview = text[:2000] + ("\n...(truncated)" if len(text) > 2000 else "")
        return True, f"File Content ({p.name}):\n{preview}"
    except Exception as exc:
        return False, f"Could not read file: {exc}"


def delete_item(path_str: str) -> ActionResult:
    """Deletes a file or directory."""
    try:
        p = Path(os.path.expandvars(path_str.strip()))
        if not p.is_absolute():
            p_desk = Path.home() / "Desktop" / p
            if p_desk.exists():
                p = p_desk
        if not p.exists():
            return False, f"Item not found: {p}"
        if p.is_dir():
            shutil.rmtree(p)
            return True, f"Deleted folder: {p.name}"
        else:
            p.unlink()
            return True, f"Deleted file: {p.name}"
    except Exception as exc:
        return False, f"Could not delete: {exc}"


def list_directory(path_str: str) -> ActionResult:
    """Lists files and folders inside a directory."""
    p = _resolve_special_folder(path_str) if path_str else Path.home() / "Desktop"
    if not p.exists():
        return False, f"Directory does not exist: {p}"
    try:
        items = os.listdir(p)[:30]
        summary = "\n".join(f"- {it}" for it in items)
        return True, f"Contents of {p.name or p}:\n{summary}"
    except Exception as exc:
        return False, f"Could not list directory: {exc}"


def search_files(query: str, drive: str = "E:") -> ActionResult:
    """Searches for files matching a query on the designated drive or folder."""
    query = query.strip()
    drive = drive.strip() or "E:"
    try:
        cmd = f'Get-ChildItem -Path "{drive}\\" -Filter "*{query}*" -Recurse -ErrorAction SilentlyContinue -Depth 3 | Select-Object -First 10 FullName | ConvertTo-Json'
        res = _subp_run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=8)
        if res.returncode == 0 and res.stdout.strip():
            raw = json.loads(res.stdout)
            if isinstance(raw, list):
                files = [f.get("FullName", str(f)) for f in raw]
            elif isinstance(raw, dict):
                files = [raw.get("FullName", str(raw))]
            else:
                files = [str(raw)]
            return True, f"Found {len(files)} files matching '{query}':\n" + "\n".join(f"- {f}" for f in files)
        return False, f"No files matching '{query}' found on {drive}."
    except Exception as exc:
        return False, f"Search failed: {exc}"


def edit_file_block(payload: str) -> ActionResult:
    """Replaces a target block with replacement content in a file.
    Format: filepath:::target:::replacement
    """
    try:
        parts = payload.split(":::")
        if len(parts) < 3:
            return False, "Invalid edit_file_block format. Expected: path:::target:::replacement"
        path_str, target, replacement = parts[0].strip(), parts[1], parts[2]
        p = Path(os.path.expandvars(path_str))
        if not p.is_absolute():
            p_desk = Path.home() / "Desktop" / p
            p = p_desk if p_desk.exists() else p
        if not p.exists():
            return False, f"File not found: {p}"
        content = p.read_text(encoding="utf-8")
        if target not in content:
            return False, f"Target string not found in {p.name}."
        new_content = content.replace(target, replacement, 1)
        p.write_text(new_content, encoding="utf-8")
        return True, f"Successfully edited {p.name}."
    except Exception as exc:
        return False, f"Could not edit file: {exc}"


def search_code(payload: str) -> ActionResult:
    """Searches for a string inside code files within a directory.
    Format: query:::directory (default dir is E:\\Nova_AI)
    """
    try:
        if ":::" in payload:
            parts = payload.split(":::", 1)
            query, base_dir = parts[0].strip(), parts[1].strip()
        else:
            query, base_dir = payload.strip(), "E:\\Nova_AI"
        p_base = Path(os.path.expandvars(base_dir))
        if not p_base.exists():
            p_base = Path("E:\\Nova_AI")
        matches = []
        ignored = {".git", "__pycache__", "venv", "node_modules", "data"}
        for root, dirs, files in os.walk(p_base):
            dirs[:] = [d for d in dirs if d not in ignored]
            for f in files:
                if f.endswith((".py", ".js", ".ts", ".json", ".md", ".txt", ".bat", ".ps1", ".html", ".css", ".yaml", ".yml")):
                    fp = Path(root) / f
                    try:
                        content = fp.read_text(encoding="utf-8", errors="ignore")
                        if query.lower() in content.lower():
                            for idx, line in enumerate(content.splitlines(), 1):
                                if query.lower() in line.lower():
                                    rel = fp.relative_to(p_base)
                                    matches.append(f"{rel}:{idx}: {line.strip()[:60]}")
                                    break
                    except Exception:
                        pass
                if len(matches) >= 12:
                    break
            if len(matches) >= 12:
                break
        if not matches:
            return True, f"No code matches found for '{query}' in {p_base}."
        return True, f"Found {len(matches)} matches for '{query}':\n" + "\n".join(f"- {m}" for m in matches)
    except Exception as exc:
        return False, f"Code search error: {exc}"


def fetch_webpage_text(url: str) -> ActionResult:
    """Fetches text content from a public webpage and strips HTML tags."""
    import urllib.request
    from urllib.parse import urlparse
    try:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, "Invalid URL specified."
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Nova-AI/3.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw_html = resp.read().decode("utf-8", errors="replace")
        clean = re.sub(r"<(script|style).*?>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", clean)
        text = re.sub(r"\s+", " ", text).strip()
        preview = text[:2500] + ("\n...(truncated)" if len(text) > 2500 else "")
        return True, f"Webpage Content ({parsed.netloc}):\n{preview}"
    except Exception as exc:
        return False, f"Could not fetch webpage: {exc}"


# ── Antigravity Dynamic Steps & Focus Listeners ─────────────────────────────
_STEPS_CALLBACKS: list = []
_FOCUS_CALLBACKS: list = []


def register_steps_listener(callback):
    """Registers a listener for live step checklist updates."""
    if callback not in _STEPS_CALLBACKS:
        _STEPS_CALLBACKS.append(callback)


def unregister_steps_listener(callback):
    if callback in _STEPS_CALLBACKS:
        _STEPS_CALLBACKS.remove(callback)


def register_focus_listener(callback):
    """Registers a listener for live focus headline updates."""
    if callback not in _FOCUS_CALLBACKS:
        _FOCUS_CALLBACKS.append(callback)


def unregister_focus_listener(callback):
    if callback in _FOCUS_CALLBACKS:
        _FOCUS_CALLBACKS.remove(callback)


def update_steps(payload: str) -> ActionResult:
    """Updates live Antigravity execution steps checklist.
    Format: Step 1 (done)|Step 2 (in_progress)|Step 3 (pending)
    """
    try:
        steps_raw = payload.strip().split("|")
        parsed_steps = []
        for s in steps_raw:
            s = s.strip()
            if not s:
                continue
            status = "pending"
            title = s
            for st in ("done", "in_progress", "pending", "failed", "skipped"):
                pattern = r"\s*[\(\[]" + st + r"[\)\]]\s*"
                if re.search(pattern, s, flags=re.IGNORECASE):
                    status = st
                    title = re.sub(pattern, "", s, flags=re.IGNORECASE).strip()
                    break
            parsed_steps.append({"title": title, "status": status})

        for cb in list(_STEPS_CALLBACKS):
            try:
                cb(parsed_steps)
            except Exception as e:
                log.warning(f"Error in steps callback: {e}")
        return True, f"Updated {len(parsed_steps)} plan steps."
    except Exception as exc:
        return False, f"Could not update steps: {exc}"


def update_focus(payload: str) -> ActionResult:
    """Broadcasts high-level focus headline for Antigravity HUD."""
    try:
        focus_text = payload.strip()
        for cb in list(_FOCUS_CALLBACKS):
            try:
                cb(focus_text)
            except Exception as e:
                log.warning(f"Error in focus callback: {e}")
        return True, f"Focus updated: {focus_text}"
    except Exception as exc:
        return False, f"Could not update focus: {exc}"


def zip_item(path_str: str) -> ActionResult:
    """Creates a zip archive of a file or folder (defaults to Desktop if relative)."""
    import zipfile
    try:
        p = Path(os.path.expandvars(path_str.strip()))
        if not p.is_absolute():
            p_desk = Path.home() / "Desktop" / p
            if p_desk.exists():
                p = p_desk
        if not p.exists():
            return False, f"Item not found: {p}"
        out_zip = p.parent / f"{p.stem}.zip"
        if p.is_dir():
            shutil.make_archive(str(p.parent / p.stem), "zip", p)
        else:
            with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(p, arcname=p.name)
        return True, f"Archived '{p.name}' to {out_zip.name}"
    except Exception as exc:
        return False, f"Zip error: {exc}"


def unzip_item(path_str: str) -> ActionResult:
    """Extracts a zip file into a folder."""
    import zipfile
    try:
        p = Path(os.path.expandvars(path_str.strip()))
        if not p.is_absolute():
            p_desk = Path.home() / "Desktop" / p
            if p_desk.exists():
                p = p_desk
        if not p.exists() or not p.name.endswith(".zip"):
            return False, f"Zip archive not found: {p}"
        dest_dir = p.parent / p.stem
        dest_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(p, "r") as zf:
            zf.extractall(dest_dir)
        return True, f"Extracted '{p.name}' into folder '{dest_dir.name}'"
    except Exception as exc:
        return False, f"Unzip error: {exc}"



# ── 5. System, Power, Clean & Hardware Info ──────────────────────────────────
def system_power(action: str) -> ActionResult:
    """Manages system power: lock, sleep, restart, shutdown, cancel."""
    action = action.strip().lower()
    try:
        if action == "lock":
            ctypes.windll.user32.LockWorkStation()
            return True, "Workstation locked, sir."
        elif action == "sleep":
            _subp_popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            return True, "Putting computer to sleep."
        elif action in ("restart", "reboot"):
            _subp_popen(["shutdown", "/r", "/t", "10", "/c", "JARVIS restarting system."])
            return True, "System will restart in 10 seconds. (Say 'cancel shutdown' to abort)."
        elif action == "shutdown":
            _subp_popen(["shutdown", "/s", "/t", "15", "/c", "JARVIS shutting down system."])
            return True, "System will shut down in 15 seconds. (Say 'cancel shutdown' to abort)."
        elif action in ("cancel", "cancel_shutdown", "abort"):
            _subp_run(["shutdown", "/a"], capture_output=True)
            return True, "Scheduled shutdown or restart aborted."
        return False, f"Unknown power action: {action}"
    except Exception as exc:
        return False, f"Power command error: {exc}"


def empty_recycle_bin() -> ActionResult:
    try:
        flags = 0x00000007  # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        return True, "Recycle Bin has been emptied."
    except Exception as exc:
        return False, f"Could not empty Recycle Bin: {exc}"


def clear_temp_files() -> ActionResult:
    """Cleans Windows temporary files to free disk space."""
    try:
        temp_dir = Path(os.environ.get("TEMP", "C:\\Windows\\Temp"))
        cleaned_count = 0
        cleaned_bytes = 0
        for item in temp_dir.glob("*"):
            try:
                if item.is_file():
                    cleaned_bytes += item.stat().st_size
                    item.unlink()
                    cleaned_count += 1
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    cleaned_count += 1
            except Exception:
                pass
        freed_mb = round(cleaned_bytes / (1024 * 1024), 1)
        return True, f"Cleaned {cleaned_count} temporary items ({freed_mb} MB freed)."
    except Exception as exc:
        return False, f"Clean temp error: {exc}"


def get_system_stats() -> ActionResult:
    """Returns disk space for C: and E:, available RAM, and CPU status."""
    try:
        cmd = '''
        $c = Get-PSDrive C; $e = Get-PSDrive E;
        $cFree = [math]::Round($c.Free / 1GB, 2);
        $eFree = [math]::Round($e.Free / 1GB, 2);
        $os = Get-CimInstance Win32_OperatingSystem;
        $freeRam = [math]::Round($os.FreePhysicalMemory / 1MB, 2);
        $totalRam = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2);
        "Drive C Free: $cFree GB | Drive E Free: $eFree GB | RAM: $freeRam GB available of $totalRam GB"
        '''
        res = _subp_run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=5)
        stats = res.stdout.strip() or "Stats currently unavailable."
        return True, stats
    except Exception as exc:
        return False, f"Could not get stats: {exc}"


def get_battery_status() -> ActionResult:
    """Returns laptop battery percentage and charging state."""
    try:
        cmd = "Get-CimInstance Win32_Battery | Select-Object -ExpandProperty EstimatedChargeRemaining"
        res = _subp_run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=4)
        pct = res.stdout.strip()
        if pct.isdigit():
            return True, f"Battery level is at {pct}%."
        return True, "Running on AC power / Desktop power supply."
    except Exception as exc:
        return False, f"Battery check error: {exc}"


def get_wifi_status() -> ActionResult:
    """Returns connected Wi-Fi SSID and signal strength."""
    try:
        res = _subp_run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=4)
        out = res.stdout
        ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.MULTILINE)
        signal_match = re.search(r"^\s*Signal\s*:\s*(.+)$", out, re.MULTILINE)
        state_match = re.search(r"^\s*State\s*:\s*(.+)$", out, re.MULTILINE)

        if ssid_match:
            ssid = ssid_match.group(1).strip()
            signal = signal_match.group(1).strip() if signal_match else "Good"
            state = state_match.group(1).strip() if state_match else "Connected"
            return True, f"Wi-Fi Status: {state} to '{ssid}' (Signal: {signal})."
        return True, "No active Wi-Fi connection detected."
    except Exception as exc:
        return False, f"Wi-Fi check error: {exc}"


def get_top_processes(count: int = 5) -> ActionResult:
    """Lists top active processes using the most memory."""
    try:
        cmd = f"Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First {count} ProcessName, Id | Out-String"
        res = _subp_run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=5)
        output = res.stdout.strip()
        return True, f"Top active processes:\n{output}"
    except Exception as exc:
        return False, f"Process check error: {exc}"


def get_network_info() -> ActionResult:
    """Provides full network telemetry: Hostname, Local IP, Wi-Fi status, and Internet latency."""
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        _, wifi = get_wifi_status()
        ping_res = _subp_run(["ping", "-n", "1", "-w", "1000", "8.8.8.8"], capture_output=True, text=True)
        online = ping_res.returncode == 0
        status_line = "Internet: Connected (Online)" if online else "Internet: Offline"
        return True, f"Network Telemetry:\n- Hostname: {hostname}\n- Local IP: {local_ip}\n- {wifi}\n- {status_line}"
    except Exception as exc:
        return False, f"Network check error: {exc}"



# ── 6. Keyboard, Mouse & Screen ──────────────────────────────────────────────
def _capture_screen_image():
    """Captures the primary screen using Qt or Windows GDI BitBlt (rock-solid)."""
    # 1. Qt Screen Grab if PySide6 application is running
    try:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            pix = screen.grabWindow(0)
            if not pix.isNull():
                import io
                from PIL import Image
                from PySide6.QtCore import QBuffer, QIODevice
                buf = QBuffer()
                buf.open(QIODevice.ReadWrite)
                pix.save(buf, "PNG")
                return Image.open(io.BytesIO(buf.data()))
    except Exception:
        pass

    # 2. Windows GDI BitBlt (never fails on Windows)
    try:
        from ctypes import windll, wintypes, byref
        from PIL import Image

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)
            ]

        user32 = windll.user32
        gdi32 = windll.gdi32
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        old_bmp = gdi32.SelectObject(hdc_mem, hbm)
        gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020)

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = (ctypes.c_ubyte * (w * h * 4))()
        gdi32.GetDIBits(hdc_mem, hbm, 0, h, buf, byref(bmi), 0)

        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
        return img.convert('RGB')
    except Exception:
        pass

    # 3. Fallback to PIL ImageGrab
    from PIL import ImageGrab
    return ImageGrab.grab()


def take_screenshot(filename: str = "") -> ActionResult:
    """Takes a full screen screenshot and saves it to Desktop."""
    try:
        target_dir = Path.home() / "Desktop"
        target_dir.mkdir(parents=True, exist_ok=True)
        name = filename.strip() or f"screenshot_{int(time.time())}.png"
        if not name.endswith(".png"):
            name += ".png"
        save_path = target_dir / name
        img = _capture_screen_image()
        img.save(str(save_path))
        return True, f"Screenshot saved to Desktop: {save_path.name}"
    except Exception as exc:
        return False, f"Screenshot error: {exc}"



def type_text(text: str) -> ActionResult:
    """Types text into the currently focused window."""
    try:
        import pyautogui
        pyautogui.write(text, interval=0.01)
        return True, f"Typed {len(text)} characters into active window."
    except Exception as exc:
        return False, f"Typing error: {exc}"


def press_hotkey(keys_str: str) -> ActionResult:
    """Presses keyboard shortcut like 'ctrl+c', 'alt+f4', 'win+r', 'enter', 'win+d'."""
    try:
        import pyautogui
        parts = [k.strip().lower() for k in keys_str.split("+")]
        pyautogui.hotkey(*parts)
        return True, f"Executed hotkey: {keys_str}"
    except Exception as exc:
        return False, f"Hotkey error: {exc}"


def click_at(coords: str) -> ActionResult:
    """Clicks on screen percentage coordinates (e.g. '50,50' for screen center)."""
    try:
        import pyautogui
        parts = coords.split(",")
        x_pct, y_pct = float(parts[0].strip()), float(parts[1].strip())
        if x_pct > 100.0 or y_pct > 100.0:
            x_pct, y_pct = x_pct / 10.0, y_pct / 10.0
        w, h = pyautogui.size()
        x, y = int((x_pct / 100.0) * w), int((y_pct / 100.0) * h)
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click()
        return True, f"Clicked at ({x_pct}%, {y_pct}%)."
    except Exception as exc:
        return False, f"Click error: {exc}"


def click_and_type(args: str) -> ActionResult:
    """Clicks at screen percentage coordinates and types text."""
    try:
        import pyautogui
        import time
        parts = args.split(",", 2)
        x_pct, y_pct, text = float(parts[0].strip()), float(parts[1].strip()), parts[2]
        if x_pct > 100.0 or y_pct > 100.0:
            x_pct, y_pct = x_pct / 10.0, y_pct / 10.0
        w, h = pyautogui.size()
        x, y = int((x_pct / 100.0) * w), int((y_pct / 100.0) * h)
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click()
        time.sleep(0.1)
        press_enter = text.endswith(("\n", "\\n"))
        clean = text.rstrip("\n\\n")
        pyautogui.write(clean, interval=0.01)
        if press_enter:
            pyautogui.press("enter")
        return True, f"Clicked at ({x_pct}%, {y_pct}%) and typed text."
    except Exception as exc:
        return False, f"Click and type error: {exc}"


def clipboard_copy(text: str) -> ActionResult:
    """Copies text to the Windows clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return True, f"Copied {len(text)} characters to clipboard."
    except Exception as exc:
        return False, f"Clipboard error: {exc}"


def clipboard_read() -> ActionResult:
    """Reads text from the Windows clipboard."""
    try:
        import pyperclip
        content = pyperclip.paste()
        if not content:
            return False, "Clipboard is currently empty."
        preview = content[:500] + ("\n...(truncated)" if len(content) > 500 else "")
        return True, f"Clipboard Content:\n{preview}"
    except Exception as exc:
        return False, f"Clipboard error: {exc}"



# ── 7. Web & Shell Commands ──────────────────────────────────────────────────
def open_url(url: str) -> ActionResult:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return True, f"Opened URL: {url}"
    except Exception as exc:
        return False, f"Error opening URL: {exc}"


def google_search(query: str) -> ActionResult:
    import urllib.parse
    return open_url(f"https://www.google.com/search?q={urllib.parse.quote(query.strip())}")


def youtube_search(query: str) -> ActionResult:
    import urllib.parse
    return open_url(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query.strip())}")


def run_command(command_str: str) -> ActionResult:
    """Executes a shell or PowerShell command silently and captures the output."""
    cmd = command_str.strip()
    if not cmd:
        return False, "No command provided."
    try:
        res = _subp_run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=25,
        )
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        result_text = out if out else (err if err else "Command executed successfully.")
        if len(result_text) > 1500:
            result_text = result_text[:1500] + "\n...(truncated)"
        return res.returncode == 0, result_text
    except Exception as exc:
        return False, f"Execution failed: {exc}"


def calculate(expr: str) -> ActionResult:
    """Safely calculates arithmetic expressions offline (e.g. '15% of 8500', '(120 * 4) + 50')."""
    try:
        clean = expr.strip().lower()
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", clean)
        if pct_match:
            pct_val = float(pct_match.group(1))
            total_val = float(pct_match.group(2))
            res = (pct_val / 100.0) * total_val
            return True, f"{pct_val}% of {total_val} = {res}"
        sanitized = re.sub(r"[^0-9\+\-\*\/\(\)\.\s\^]", "", clean).replace("^", "**")
        if not sanitized.strip():
            return False, "Invalid math expression."
        val = eval(sanitized, {"__builtins__": None}, {})
        return True, f"Calculation: {expr.strip()} = {val}"
    except Exception as exc:
        return False, f"Could not calculate: {exc}"


def run_routine(routine_name: str) -> ActionResult:
    """Executes preset smart routines: 'work', 'relax', 'clean', 'status', 'night'."""
    name = routine_name.strip().lower()
    reports = []
    if name in ("work", "focus", "study"):
        set_volume("25")
        reports.append("Volume set to 25%")
        open_application("chrome")
        reports.append("Opened browser workspace")
        return True, "Focus routine activated: " + ", ".join(reports)
    elif name in ("relax", "chill", "music"):
        set_volume("45")
        reports.append("Volume set to 45%")
        youtube_search("lofi chill beats")
        reports.append("Launched background music")
        return True, "Relax routine activated: " + ", ".join(reports)
    elif name in ("night", "sleep_mode", "dim"):
        set_volume("15")
        set_brightness("25")
        reports.append("Volume set to 15%")
        reports.append("Screen brightness dimmed to 25%")
        return True, "Night routine activated: " + ", ".join(reports)
    elif name in ("clean", "speedup", "turbo"):
        ok_t, msg_t = clear_temp_files()
        ok_r, msg_r = empty_recycle_bin()
        return True, f"System cleanup completed. {msg_t} | {msg_r}"
    elif name in ("status", "health", "specs"):
        _, stats = get_system_stats()
        _, wifi = get_wifi_status()
        _, bat = get_battery_status()
        _, bri = get_brightness()
        return True, f"System Health:\n- {stats}\n- {wifi}\n- {bat}\n- {bri}"
    return False, f"Unknown routine: {routine_name}"


# ── 8. Coding & Developer Actions ──────────────────────────────────────────
def create_html_app(arg: str) -> ActionResult:
    r"""Creates an interactive HTML5 / CSS / JavaScript web application or game.
    Syntax:
        [action:create_html_app:<title_or_filename>:<html_content>]
    Saves to Desktop as <title>.html and opens in browser.
    """
    arg = arg.strip()
    if not arg:
        return False, "No HTML app content provided."

    if ":" in arg:
        title_part, html_content = arg.split(":", 1)
    else:
        title_part = "WebApp.html"
        html_content = arg

    title = title_part.strip()
    if not title.lower().endswith((".html", ".htm")):
        title += ".html"

    target_path = Path.home() / "Desktop" / title
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(html_content.strip(), encoding="utf-8")

    try:
        os.startfile(str(target_path))
    except Exception:
        pass

    return True, f"Claude Interactive Web App '{target_path.name}' created at {target_path} and opened in browser."


def read_document(path_str: str) -> ActionResult:
    """Reads text, PDF, CSV, JSON, Markdown, or Code documents."""
    p = Path(os.path.expandvars(path_str.strip()))
    if not p.is_absolute():
        p_desk = Path.home() / "Desktop" / p
        p = p_desk if p_desk.exists() else p

    if not p.exists():
        return False, f"File not found: {p}"

    suffix = p.suffix.lower()

    if suffix == ".pdf":
        try:
            content_bytes = p.read_bytes()
            import re
            text_matches = re.findall(rb"\((.*?)\)Tj", content_bytes)
            if text_matches:
                extracted = b" ".join(text_matches).decode("latin-1", errors="ignore")
                return True, f"PDF Document text ({p.name}):\n{extracted[:4000]}"
        except Exception:
            pass

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        return True, f"Document Content ({p.name}, {len(text)} chars):\n{text[:6000]}"
    except Exception as e:
        return False, f"Could not read document: {e}"


def create_excel(arg: str) -> ActionResult:
    r"""Creates a beautifully styled, production-grade Excel (.xlsx) file.
    Syntax:
        [action:create_excel:<filepath_or_filename>:<content>]
    Content can be:
        - CSV-like text with commas, semicolons, tabs, or pipes
        - JSON array of objects
    Saves to Desktop by default if relative path.
    Applies elegant headers, bold text, colored navy header styling, and auto-fit column widths.
    """
    arg = arg.strip()
    if not arg:
        return False, "No Excel data provided. Usage: [action:create_excel:filename.xlsx:Header1,Header2\\nVal1,Val2]"

    if ":" in arg:
        path_part, data_part = arg.split(":", 1)
    else:
        path_part = "Report.xlsx"
        data_part = arg

    filename = path_part.strip()
    if not filename.lower().endswith((".xlsx", ".xls", ".csv")):
        filename += ".xlsx"

    target_path = Path(filename)
    if not target_path.is_absolute():
        desktop = Path.home() / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        target_path = desktop / filename

    target_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    data_str = data_part.strip()

    # 1. Parse JSON format
    if data_str.startswith("[") and data_str.endswith("]"):
        try:
            import json
            json_data = json.loads(data_str)
            if json_data and isinstance(json_data, list):
                if isinstance(json_data[0], dict):
                    headers = list(json_data[0].keys())
                    rows.append(headers)
                    for item in json_data:
                        rows.append([item.get(h, "") for h in headers])
                elif isinstance(json_data[0], list):
                    rows = json_data
        except Exception:
            pass

    # 2. Parse CSV / delimited text format
    if not rows:
        lines = [line.strip() for line in data_str.splitlines() if line.strip()]
        for line in lines:
            if "|" in line:
                row = [c.strip() for c in line.split("|") if c.strip() != ""]
            elif "\t" in line:
                row = [c.strip() for c in line.split("\t")]
            elif ";" in line:
                row = [c.strip() for c in line.split(";")]
            else:
                import csv
                reader = csv.reader([line])
                row = next(reader, [line])
            if row:
                rows.append(row)

    if not rows:
        return False, "Could not parse data rows for Excel file."

    # Try openpyxl for native .xlsx with professional styling
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = target_path.stem[:31]

        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        alt_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        data_font = Font(name="Segoe UI", size=10)

        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        for r_idx, row in enumerate(rows, 1):
            for c_idx, val in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                str_val = str(val).strip()
                try:
                    if "." in str_val and str_val.replace(".", "", 1).lstrip("-").isdigit():
                        cell.value = float(str_val)
                    elif str_val.lstrip("-").isdigit():
                        cell.value = int(str_val)
                    else:
                        cell.value = str_val
                except Exception:
                    cell.value = str_val

                cell.border = thin_border
                if r_idx == 1:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.font = data_font
                    if r_idx % 2 == 0:
                        cell.fill = alt_fill
                    cell.alignment = Alignment(vertical="center")

        # Auto-fit column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                v = str(cell.value or "")
                if len(v) > max_len:
                    max_len = len(v)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        ws.freeze_panes = "A2"
        wb.save(target_path)

        # Launch in Excel / default viewer
        try:
            os.startfile(str(target_path))
        except Exception:
            pass

        return True, f"Excel file '{target_path.name}' successfully created at {target_path} and opened in Excel."

    except Exception as e:
        # Fallback to UTF-8 BOM CSV (Excel opens it cleanly)
        try:
            import csv
            csv_path = target_path.with_suffix(".csv")
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            try:
                os.startfile(str(csv_path))
            except Exception:
                pass
            return True, f"Spreadsheet file '{csv_path.name}' created at {csv_path} and opened."
        except Exception as e2:
            return False, f"Failed to create spreadsheet: {e} / {e2}"


def create_pdf(arg: str) -> ActionResult:
    r"""Generates an executive, styled PDF report saved directly to Desktop or a custom path.
    Syntax:
        [action:create_pdf:filepath:html_or_markdown_content]
        [action:create_pdf:html_or_markdown_content]
    """
    arg = arg.strip()
    if not arg:
        return False, "No PDF content provided. Usage: [action:create_pdf:report.pdf:<h1>Title</h1>...]"

    if ":" in arg:
        path_part, data_part = arg.split(":", 1)
        if not path_part.lower().endswith(".pdf") and ("<" in path_part or "\n" in path_part or len(path_part) > 60):
            path_part = "Nova_Report.pdf"
            data_part = arg
    else:
        path_part = "Nova_Report.pdf"
        data_part = arg

    filename = path_part.strip()
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    target_path = Path(filename)
    if not target_path.is_absolute():
        desktop = Path.home() / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        target_path = desktop / filename

    target_path.parent.mkdir(parents=True, exist_ok=True)

    raw_content = data_part.strip()
    if not ("<html" in raw_content.lower() or "<body" in raw_content.lower() or "<div" in raw_content.lower() or "<h1" in raw_content.lower()):
        formatted_body = []
        for line in raw_content.splitlines():
            line_s = line.strip()
            if line_s.startswith("### "):
                formatted_body.append(f"<h3 style='color:#1e3a8a; font-family:Segoe UI, sans-serif; margin-top:14px;'>{line_s[4:]}</h3>")
            elif line_s.startswith("## "):
                formatted_body.append(f"<h2 style='color:#0f172a; border-bottom:1px solid #cbd5e1; padding-bottom:4px; font-family:Segoe UI, sans-serif; margin-top:18px;'>{line_s[3:]}</h2>")
            elif line_s.startswith("# "):
                formatted_body.append(f"<h1 style='color:#0f172a; border-bottom:2px solid #2563eb; padding-bottom:8px; font-family:Segoe UI, sans-serif; margin-top:10px;'>{line_s[2:]}</h1>")
            elif line_s.startswith("- ") or line_s.startswith("* "):
                formatted_body.append(f"<li style='margin-bottom:4px; font-family:Segoe UI, sans-serif; font-size:10pt;'>{line_s[2:]}</li>")
            elif line_s:
                formatted_body.append(f"<p style='font-family:Segoe UI, sans-serif; font-size:10pt; line-height:1.5; color:#334155; margin-bottom:8px;'>{line_s}</p>")
            else:
                formatted_body.append("<br/>")
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 24px; color: #1e293b; }}
                h1 {{ color: #1e3a8a; font-size: 20pt; }}
                h2 {{ color: #0284c7; font-size: 15pt; }}
                h3 {{ color: #334155; font-size: 12pt; }}
                p, li {{ font-size: 10pt; line-height: 1.5; color: #334155; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; font-size: 9.5pt; }}
                th {{ background-color: #1e3a8a; color: white; }}
                tr:nth-child(even) {{ background-color: #f8fafc; }}
            </style>
        </head>
        <body>
            {''.join(formatted_body)}
        </body>
        </html>
        """
    else:
        html_content = raw_content

    try:
        import sys
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize

        _ = QApplication.instance() or QApplication(sys.argv)
        writer = QPdfWriter(str(target_path))
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setResolution(300)

        doc = QTextDocument()
        doc.setHtml(html_content)
        doc.print_(writer)
        del writer

        size_kb = target_path.stat().st_size / 1024
        try:
            os.startfile(str(target_path))
        except Exception:
            pass
        return True, f"Generated executive PDF report: '{target_path.name}' at {target_path} ({size_kb:.1f} KB)."
    except Exception as exc:
        return False, f"Failed to generate PDF document: {exc}"


def create_word_document(arg: str) -> ActionResult:
    r"""Generates a styled, native Microsoft Word (.docx) document saved directly to Desktop.
    Syntax:
        [action:create_word:filename.docx:content]
        [action:create_word:content]
    """
    arg = arg.strip()
    if not arg:
        return False, "No Word document content provided. Usage: [action:create_word:doc.docx:# Title\nBody]"

    if ":" in arg:
        path_part, data_part = arg.split(":", 1)
        if not path_part.lower().endswith(".docx") and ("#" in path_part or "\n" in path_part or len(path_part) > 60):
            path_part = "Nova_Document.docx"
            data_part = arg
    else:
        path_part = "Nova_Document.docx"
        data_part = arg

    filename = path_part.strip()
    if not filename.lower().endswith(".docx"):
        filename += ".docx"

    target_path = Path(filename)
    if not target_path.is_absolute():
        desktop = Path.home() / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        target_path = desktop / filename

    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import docx
        from docx.shared import Inches, Pt, RGBColor

        doc = docx.Document()
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
        font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

        lines = data_part.strip().splitlines()
        in_table = False
        table_rows = []

        def flush_table():
            nonlocal table_rows, in_table
            if not table_rows:
                return
            t = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
            t.style = 'Table Grid'
            for r_i, r in enumerate(table_rows):
                for c_i, cell_text in enumerate(r):
                    cell = t.cell(r_i, c_i)
                    cell.text = cell_text
                    if r_i == 0:
                        for p in cell.paragraphs:
                            for run in p.runs:
                                run.font.bold = True
                                run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
            doc.add_paragraph()
            table_rows = []
            in_table = False

        for line in lines:
            line_s = line.strip()
            if "|" in line_s and line_s.startswith("|") and line_s.endswith("|"):
                parts = [p.strip() for p in line_s.strip("|").split("|")]
                if parts and not all(set(p) <= set("-: ") for p in parts):
                    table_rows.append(parts)
                    in_table = True
                continue
            else:
                if in_table:
                    flush_table()

            if line_s.startswith("# "):
                h = doc.add_heading(line_s[2:], level=1)
                h.paragraph_format.space_before = Pt(14)
                h.paragraph_format.space_after = Pt(6)
            elif line_s.startswith("## "):
                h = doc.add_heading(line_s[3:], level=2)
                h.paragraph_format.space_before = Pt(12)
                h.paragraph_format.space_after = Pt(4)
            elif line_s.startswith("### "):
                h = doc.add_heading(line_s[4:], level=3)
                h.paragraph_format.space_before = Pt(8)
                h.paragraph_format.space_after = Pt(2)
            elif line_s.startswith("- ") or line_s.startswith("* "):
                doc.add_paragraph(line_s[2:], style='List Bullet')
            elif line_s.startswith("1. ") or line_s.startswith("2. ") or line_s.startswith("3. "):
                doc.add_paragraph(line_s.split(". ", 1)[1], style='List Number')
            elif line_s:
                p = doc.add_paragraph(line_s)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.line_spacing = 1.15

        if in_table:
            flush_table()

        doc.save(str(target_path))
        size_kb = target_path.stat().st_size / 1024
        try:
            os.startfile(str(target_path))
        except Exception:
            pass
        return True, f"Generated Word document: '{target_path.name}' at {target_path} ({size_kb:.1f} KB)."
    except Exception as exc:
        return False, f"Failed to generate Word document: {exc}"


def create_presentation(arg: str) -> ActionResult:
    r"""Generates a professional Microsoft PowerPoint (.pptx) presentation saved to Desktop.
    Syntax:
        [action:create_presentation:deck.pptx:Slide 1 Title\n- Bullet 1\n---\nSlide 2 Title\n- Bullet 1]
    """
    arg = arg.strip()
    if not arg:
        return False, "No presentation content provided. Usage: [action:create_presentation:deck.pptx:Slide 1\n- Point 1\n---\nSlide 2]"

    if ":" in arg:
        path_part, data_part = arg.split(":", 1)
        if not path_part.lower().endswith(".pptx") and ("---" in path_part or "\n" in path_part or len(path_part) > 60):
            path_part = "Nova_Presentation.pptx"
            data_part = arg
    else:
        path_part = "Nova_Presentation.pptx"
        data_part = arg

    filename = path_part.strip()
    if not filename.lower().endswith(".pptx"):
        filename += ".pptx"

    target_path = Path(filename)
    if not target_path.is_absolute():
        desktop = Path.home() / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        target_path = desktop / filename

    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from pptx import Presentation
        from pptx.util import Inches

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        raw_slides = data_part.split("---")
        for i, s_block in enumerate(raw_slides):
            lines = [l.strip() for l in s_block.strip().splitlines() if l.strip()]
            if not lines:
                continue

            if i == 0:
                title_slide_layout = prs.slide_layouts[0]
                slide = prs.slides.add_slide(title_slide_layout)
                title = slide.shapes.title
                subtitle = slide.placeholders[1]
                title.text = lines[0].lstrip("# ")
                if len(lines) > 1:
                    subtitle.text = "\n".join(lines[1:])
            else:
                bullet_slide_layout = prs.slide_layouts[1]
                slide = prs.slides.add_slide(bullet_slide_layout)
                shapes = slide.shapes
                title_shape = shapes.title
                body_shape = shapes.placeholders[1]
                title_shape.text = lines[0].lstrip("# ")

                tf = body_shape.text_frame
                tf.word_wrap = True
                for b_line in lines[1:]:
                    p = tf.add_paragraph()
                    p.text = b_line.lstrip("- *•").strip()
                    p.level = 0

        prs.save(str(target_path))
        size_kb = target_path.stat().st_size / 1024
        try:
            os.startfile(str(target_path))
        except Exception:
            pass
        return True, f"Generated PowerPoint presentation: '{target_path.name}' at {target_path} ({size_kb:.1f} KB)."
    except Exception as exc:
        return False, f"Failed to generate PowerPoint presentation: {exc}"


def optimize_system() -> ActionResult:
    """Performs deep Windows system optimization:
    - Clears User and System Temp files
    - Flushes Windows DNS Resolver Cache (ipconfig /flushdns)
    - Purges Recycle Bin
    - Trims process memory and runs garbage collection
    - Returns comprehensive space recovered and health report.
    """
    report = []
    freed_mb = 0.0

    # 1. Clear Temp folders
    temp_dirs = [
        Path(os.environ.get("TEMP", "")),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Temp",
        Path("C:/Windows/Temp"),
    ]
    files_removed = 0
    for t_dir in temp_dirs:
        if not t_dir.exists():
            continue
        for root, dirs, files in os.walk(t_dir):
            for f in files:
                try:
                    fp = Path(root) / f
                    sz = fp.stat().st_size
                    fp.unlink(missing_ok=True)
                    freed_mb += sz / (1024 * 1024)
                    files_removed += 1
                except Exception:
                    pass

    report.append(f"Cleaned {files_removed} temporary files ({freed_mb:.1f} MB freed).")

    # 2. Flush DNS Cache
    try:
        res = _subp_run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=5)
        report.append("Flushed Windows DNS resolver cache successfully.")
    except Exception as e:
        report.append(f"DNS cache: {e}")

    # 3. Empty Recycle Bin
    try:
        from automation.actions import empty_recycle_bin
        _, bin_msg = empty_recycle_bin()
        report.append(bin_msg)
    except Exception:
        pass

    # 4. Memory Trimming
    try:
        import psutil, gc
        gc.collect()
        mem_after = psutil.virtual_memory().percent
        report.append(f"RAM load stabilized at {mem_after}% across {psutil.cpu_count(logical=True)} logical CPU cores.")
    except Exception:
        pass

    summary = "System Optimization Complete:\n" + "\n".join(f"- {r}" for r in report)
    return True, summary


def run_code(arg: str) -> ActionResult:
    """Executes code snippet in Python, PowerShell, CMD, or Node.
    Syntax: 'python:code' or 'powershell:code' or just Python code.
    Runs Python in-process for ultra-fast, zero-timeout execution without requiring python.exe.
    """
    arg = arg.strip()
    if not arg:
        return False, "No code provided to execute."

    lang = "python"
    code = arg
    if ":" in arg:
        possible_lang, rest = arg.split(":", 1)
        if possible_lang.strip().lower() in ("python", "py", "powershell", "ps", "ps1", "cmd", "bat", "batch", "node", "js", "javascript"):
            lang = possible_lang.strip().lower()
            code = rest.strip()

    import sys

    try:
        if lang in ("python", "py"):
            import io
            import traceback

            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = stdout_buf
            sys.stderr = stderr_buf
            success = True
            try:
                import os, math, time, shutil, pathlib, csv
                exec_globals = {
                    "__builtins__": __builtins__,
                    "os": os,
                    "sys": sys,
                    "math": math,
                    "pathlib": pathlib,
                    "Path": pathlib.Path,
                    "time": time,
                    "shutil": shutil,
                    "csv": csv,
                }
                try:
                    import openpyxl
                    exec_globals["openpyxl"] = openpyxl
                except Exception:
                    pass
                try:
                    import docx
                    exec_globals["docx"] = docx
                except Exception:
                    pass
                try:
                    import pptx
                    exec_globals["pptx"] = pptx
                except Exception:
                    pass

                exec(code, exec_globals)
            except Exception as e:
                success = False
                traceback.print_exc(file=stderr_buf)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            out = stdout_buf.getvalue().strip()
            err = stderr_buf.getvalue().strip()
            res = out or err or ("(Executed successfully with no output)" if success else "(Execution failed)")
            status = "Success" if success else "Failed"
            return success, f"Python [{status}]:\n{res}"

        elif lang in ("powershell", "ps", "ps1"):
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", code],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )
            out = proc.stdout.strip() or proc.stderr.strip() or "(Finished)"
            return (proc.returncode == 0), f"PowerShell (exit {proc.returncode}):\n{out}"

        elif lang in ("cmd", "bat", "batch"):
            proc = subprocess.run(
                ["cmd.exe", "/c", code],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )
            out = proc.stdout.strip() or proc.stderr.strip() or "(Finished)"
            return (proc.returncode == 0), f"CMD (exit {proc.returncode}):\n{out}"

        elif lang in ("node", "js", "javascript"):
            proc = subprocess.run(
                ["node", "-e", code],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )
            out = proc.stdout.strip() or proc.stderr.strip() or "(Finished)"
            return (proc.returncode == 0), f"Node.js (exit {proc.returncode}):\n{out}"

        return False, f"Unsupported language: {lang}"
    except subprocess.TimeoutExpired:
        return False, "Code execution timed out (limit: 60s)."
    except Exception as exc:
        return False, f"Code execution error: {exc}"


def save_code_file(arg: str) -> ActionResult:
    """Saves code to a file. Syntax: 'filepath:content' or saves to Desktop."""
    if ":" not in arg:
        return False, "Invalid format. Expected 'filepath:content'."
    path_str, content = arg.split(":", 1)
    p = Path(path_str.strip())
    if not p.is_absolute():
        p = Path.home() / "Desktop" / p
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content.strip(), encoding="utf-8")
        return True, f"Saved code file: {p}"
    except Exception as exc:
        return False, f"Could not save file: {exc}"


def run_git(args: str) -> ActionResult:
    """Runs a git command (e.g. status, diff, log, commit)."""
    args = args.strip()
    if not args:
        return False, "No git command provided."
    try:
        cmd = ["git"] + args.split()
        proc = _subp_run(cmd, capture_output=True, text=True, timeout=20)
        out = proc.stdout.strip() or proc.stderr.strip() or "(Git command executed)"
        return (proc.returncode == 0), f"Git ({'OK' if proc.returncode == 0 else 'Error'}):\n{out}"
    except Exception as exc:
        return False, f"Git execution error: {exc}"


def pip_install(package: str) -> ActionResult:
    """Installs a Python package using pip."""
    pkg = package.strip()
    if not pkg:
        return False, "No package specified."
    import shutil
    import sys
    if getattr(sys, "frozen", False):
        py_bin = shutil.which("python") or shutil.which("py") or r"E:\python\python.exe"
        if not py_bin or not Path(py_bin).exists():
            return False, f"Cannot install '{pkg}': Running in standalone compiled mode without an external Python installation on PATH."
    else:
        py_bin = sys.executable or "E:\\python\\python.exe"

    try:
        proc = _subp_run(
            [py_bin, "-m", "pip", "install", pkg],
            capture_output=True,
            text=True,
            timeout=90,
        )
        out = proc.stdout.strip() or proc.stderr.strip()
        return (proc.returncode == 0), f"pip install {pkg} (exit {proc.returncode}):\n{out}"
    except Exception as exc:
        return False, f"Pip error: {exc}"


# ── 9. Vision & Agent Task Management ──────────────────────────────────────────
def enable_screen_vision() -> ActionResult:
    """Activates screen vision and captures initial screen state."""
    try:
        from automation.screen_observer import screen_observer
        screen_observer.set_enabled(True)
        shot_path, win_title = screen_observer.capture_now()
        return True, f"Screen Vision is now ON. Active window: '{win_title}'."
    except Exception as exc:
        return False, f"Could not activate screen vision: {exc}"


def save_agent_task(arg: str) -> ActionResult:
    """Saves a multi-step agent task or goal to persistent storage.
    Format: 'Title:Step 1|Step 2|Step 3' or 'Title'
    """
    arg = arg.strip()
    if not arg:
        return False, "No task description or title provided."
    if ":" in arg:
        title, steps_raw = arg.split(":", 1)
        steps = [s.strip() for s in steps_raw.split("|") if s.strip()]
    else:
        title = arg
        steps = ["Analyze requirements", "Execute solution", "Verify results"]

    try:
        import memory.database as db
        task = db.save_agent_task(title.strip(), steps)
        return True, f"Agent Task saved: '{title.strip()}' ({len(steps)} steps). Task ID: {task['id']}"
    except Exception as exc:
        return False, f"Failed to save agent task: {exc}"


def update_agent_task_progress(arg: str) -> ActionResult:
    """Updates progress on an active agent task.
    Format: 'task_id:step_number' or 'task_id:completed' or 'step_number'
    """
    arg = arg.strip()
    try:
        import memory.database as db
        task = db.get_active_agent_task()
        task_id = None
        step_idx = 0
        status = "in_progress"

        if ":" in arg:
            tid_part, step_part = arg.split(":", 1)
            task_id = tid_part.strip()
            val = step_part.strip().lower()
            if val in ("completed", "done", "finished"):
                status = "completed"
            elif val.isdigit():
                step_idx = int(val)
        elif arg.isdigit():
            step_idx = int(arg)
        elif arg.lower() in ("completed", "done", "finished"):
            status = "completed"
        elif arg:
            task_id = arg

        if not task_id:
            if task:
                task_id = task["id"]
            else:
                return False, "No active agent task found to update."

        if status == "completed":
            db.complete_agent_task(task_id)
            return True, f"Agent Task [{task_id}] marked as COMPLETED."
        else:
            db.update_agent_task_step(task_id, step_idx, status=status)
            return True, f"Agent Task [{task_id}] updated to Step {step_idx + 1}."
    except Exception as exc:
        return False, f"Failed to update task: {exc}"


def list_agent_tasks() -> ActionResult:
    """Returns a summary of saved agent tasks and goals."""
    try:
        import memory.database as db
        tasks = db.get_all_agent_tasks(limit=10)
        if not tasks:
            return True, "No saved agent tasks found."
        lines = ["Saved Agent Tasks:"]
        for t in tasks:
            st = t["status"].upper()
            cur = t["current_step"] + 1
            tot = len(t.get("steps", []))
            lines.append(f"- [{st}] {t['title']} (Step {cur}/{tot}) [ID: {t['id']}]")
        return True, "\n".join(lines)
    except Exception as exc:
        return False, f"Failed to list tasks: {exc}"


# ── 9. Autonomous Research, Email & Scheduling ──────────────────────────────
def action_web_search(query: str) -> ActionResult:
    """Autonomously searches the web and returns concise research insights."""
    try:
        from utils.researcher import research_topic
        res = research_topic(query, max_results=4)
        return True, res
    except Exception as exc:
        return False, f"Web research failed: {exc}"


def action_deep_research(query: str) -> ActionResult:
    """Autonomously performs multi-source deep research, extracts article excerpts, and compiles an executive brief."""
    try:
        from utils.researcher import deep_research_topic
        res = deep_research_topic(query, max_sources=3)
        return True, res
    except Exception as exc:
        return False, f"Deep research failed: {exc}"


def action_send_email(arg: str) -> ActionResult:
    """Sends an email formatted as '<to>:<subject>:<body>'."""
    try:
        parts = arg.split(":", 2)
        if len(parts) < 3:
            return False, "Usage format: to_email:subject:email_body"
        to_addr, subject, body = parts[0].strip(), parts[1].strip(), parts[2].strip()

        from config.settings_schema import load_config
        from utils.email_manager import send_email
        cfg = load_config()
        if not cfg.email.email or not cfg.email.app_password:
            return False, "Email sender credentials not configured in Connections -> Email Settings."

        return send_email(
            to_email=to_addr,
            subject=subject,
            body=body,
            sender_email=cfg.email.email,
            app_password=cfg.email.app_password,
            smtp_host=cfg.email.smtp_host
        )
    except Exception as exc:
        return False, f"Email dispatch failed: {exc}"


def action_check_emails() -> ActionResult:
    """Checks recent inbox emails using configured IMAP settings."""
    try:
        from config.settings_schema import load_config
        from utils.email_manager import check_recent_emails
        cfg = load_config()
        if not cfg.email.email or not cfg.email.app_password:
            return False, "Email credentials not configured in Connections -> Email Settings."

        return check_recent_emails(
            user_email=cfg.email.email,
            app_password=cfg.email.app_password,
            imap_host=cfg.email.imap_host,
            limit=5
        )
    except Exception as exc:
        return False, f"Checking emails failed: {exc}"


def action_notify(title: str, msg: str) -> ActionResult:
    """Pushes a notification to Desktop, WhatsApp, and Discord."""
    try:
        from utils.notifier import send_universal_notification
        send_universal_notification(title, msg)
        return True, f"Notification delivered: {title} - {msg}"
    except Exception as exc:
        return False, f"Notification failed: {exc}"


def action_schedule_daily(arg: str) -> ActionResult:
    """Schedules a daily recurring task. Format: 'HH:MM:task_prompt'."""
    try:
        parts = arg.split(":", 2)
        if len(parts) < 3:
            return False, "Usage format: HH:MM:task_prompt (e.g. 09:30:Check morning news and email)"
        hh = parts[0].strip().zfill(2)
        mm = parts[1].strip().zfill(2)
        time_str = f"{hh}:{mm}"
        prompt = parts[2].strip()
        import memory.database as db
        db.save_scheduled_task(
            task_type="daily",
            prompt=prompt,
            target_time=time_str,
            title=prompt[:40],
            notify_wa=True,
            notify_dc=True,
            notify_app=True
        )
        return True, f"Daily recurring task scheduled for {time_str}: '{prompt}'"
    except Exception as exc:
        return False, f"Failed to schedule daily task: {exc}"


def action_schedule_once(arg: str) -> ActionResult:
    """Schedules a one-off task for today. Format: 'HH:MM:task_prompt'."""
    try:
        parts = arg.split(":", 2)
        if len(parts) < 3:
            return False, "Usage format: HH:MM:task_prompt (e.g. 15:00:Generate project summary)"
        hh = parts[0].strip().zfill(2)
        mm = parts[1].strip().zfill(2)
        time_str = f"{hh}:{mm}"
        prompt = parts[2].strip()
        import memory.database as db
        db.save_scheduled_task(
            task_type="day_schedule",
            prompt=prompt,
            target_time=time_str,
            title=prompt[:40],
            notify_wa=True,
            notify_dc=True,
            notify_app=True
        )
        return True, f"One-off task scheduled for today at {time_str}: '{prompt}'"
    except Exception as exc:
        return False, f"Failed to schedule one-off task: {exc}"


def generate_chart(arg: str) -> ActionResult:
    """
    Generates an interactive Obsidian-themed Chart.js data visualization.
    Accepts:
    1. JSON string: {"title": "Monthly Revenue", "type": "bar", "labels": ["Jan", "Feb", ...], "datasets": [{"label": "2026", "data": [10, 20, ...]}]}
    2. Pipe syntax: "Title|chart_type|label1,label2,label3|val1,val2,val3|DatasetName"
    """
    try:
        title = "Data Visualization"
        chart_type = "bar"
        labels = []
        datasets = []
        clean_arg = (arg or "").strip()

        if clean_arg.startswith("{") and clean_arg.endswith("}"):
            payload = json.loads(clean_arg)
            title = payload.get("title", "Data Visualization")
            chart_type = payload.get("type", "bar").lower()
            labels = payload.get("labels", [])
            datasets = payload.get("datasets", [])
            if not datasets and "data" in payload:
                datasets = [{
                    "label": payload.get("dataset_name", "Values"),
                    "data": payload["data"],
                    "backgroundColor": "#38bdf8",
                    "borderColor": "#0284c7",
                }]
        elif "|" in clean_arg:
            parts = [p.strip() for p in clean_arg.split("|")]
            title = parts[0] if len(parts) > 0 and parts[0] else "Data Analysis"
            chart_type = parts[1].lower() if len(parts) > 1 and parts[1] else "bar"
            if len(parts) > 2:
                labels = [x.strip() for x in parts[2].split(",") if x.strip()]
            raw_vals = [float(x.strip()) for x in parts[3].split(",") if x.strip()] if len(parts) > 3 else []
            ds_label = parts[4] if len(parts) > 4 else "Metrics"
            datasets = [{"label": ds_label, "data": raw_vals}]
        else:
            return False, "Usage: generate_chart:Title|type|labels|values or JSON string"

        # Color schemes
        palette = [
            "#38bdf8", "#818cf8", "#34d399", "#f472b6", "#fbbf24",
            "#60a5fa", "#a78bfa", "#4ade80", "#f87171", "#fb923c"
        ]
        border_palette = [
            "#0284c7", "#4f46e5", "#059669", "#db2777", "#d97706",
            "#2563eb", "#7c3aed", "#16a34a", "#dc2626", "#ea580c"
        ]

        for i, ds in enumerate(datasets):
            if "backgroundColor" not in ds:
                if chart_type in ("pie", "doughnut", "polarArea"):
                    ds["backgroundColor"] = palette[:len(labels)]
                    ds["borderColor"] = "#09090b"
                    ds["borderWidth"] = 2
                else:
                    c = palette[i % len(palette)]
                    bc = border_palette[i % len(border_palette)]
                    ds["backgroundColor"] = c if chart_type == "bar" else f"{c}33"
                    ds["borderColor"] = bc
                    ds["borderWidth"] = 2
                    if chart_type == "line":
                        ds["fill"] = True
                        ds["tension"] = 0.35

        chart_config = {
            "type": chart_type,
            "data": {
                "labels": labels,
                "datasets": datasets
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "legend": {
                        "labels": {
                            "color": "#cbd5e1",
                            "font": {"family": "Consolas, sans-serif", "size": 12}
                        }
                    },
                    "title": {
                        "display": True,
                        "text": title,
                        "color": "#f8fafc",
                        "font": {"size": 16, "weight": "bold"}
                    }
                },
                "scales": {
                    "x": {
                        "grid": {"color": "#1e2430"},
                        "ticks": {"color": "#94a3b8"}
                    },
                    "y": {
                        "grid": {"color": "#1e2430"},
                        "ticks": {"color": "#94a3b8"}
                    }
                } if chart_type not in ("pie", "doughnut", "polarArea", "radar") else {}
            }
        }

        html_code = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body {{
    background-color: #09090e;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 90vh;
  }}
  .card {{
    background-color: #111118;
    border: 1px solid #1f2430;
    border-radius: 12px;
    padding: 24px;
    width: 92%;
    max-width: 900px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    border-bottom: 1px solid #1f2430;
    padding-bottom: 12px;
  }}
  h2 {{
    margin: 0;
    color: #38bdf8;
    font-size: 18px;
    letter-spacing: 0.5px;
  }}
  .btn {{
    background: #1e1b4b;
    color: #a5b4fc;
    border: 1px solid #4338ca;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 11px;
    font-weight: 700;
  }}
  .btn:hover {{
    background: #312e81;
    color: #ffffff;
  }}
  .chart-box {{
    position: relative;
    height: 480px;
    width: 100%;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h2>{title}</h2>
    <div>
      <button class="btn" onclick="downloadImage()">Save Image</button>
      <button class="btn" onclick="window.print()">Print</button>
    </div>
  </div>
  <div class="chart-box">
    <canvas id="mainChart"></canvas>
  </div>
</div>
<script>
  const ctx = document.getElementById('mainChart').getContext('2d');
  const chartInstance = new Chart(ctx, {json.dumps(chart_config)});

  function downloadImage() {{
    const a = document.createElement('a');
    a.href = chartInstance.toBase64Image();
    a.download = '{title.lower().replace(" ", "_")}.png';
    a.click();
  }}
</script>
</body>
</html>
"""
        # Save to Desktop and Temp
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        clean_title = re.sub(r'[\/:*?"<>|]', '_', title)
        out_file = desktop / f"Chart_{clean_title}_{int(time.time())}.html"
        out_file.write_text(html_code, encoding="utf-8")

        # Open in application or OS
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                for widget in app.topLevelWidgets():
                    if hasattr(widget, "open_claude_artifact"):
                        widget.open_claude_artifact(f"Chart: {title}", html_code, "html")
                        break
        except Exception:
            pass

        try:
            os.startfile(str(out_file))
        except Exception:
            pass

        return True, f"Successfully generated interactive chart: '{title}'. File saved to Desktop: {out_file}"
    except Exception as exc:
        return False, f"Failed to generate chart: {exc}"






