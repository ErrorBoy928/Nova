"""
automation/executor.py

Dispatches [action:NAME:ARG] tags from the LLM response to matching actions.
Features:
- Instant execution without double-thinking or delay.
- Robust parsing of single or multiple action tags.
- Detailed result reporting for JARVIS-style completion notices.
"""

from __future__ import annotations

import re
from automation import actions
from utils.logger import get_logger

log = get_logger(__name__)

ACTION_TAG_RE = re.compile(r"\[action:\s*([\w\-]+)(?::(.*?))?\]", re.IGNORECASE | re.DOTALL)


def extract_actions(reply: str) -> tuple[str, list[tuple[str, str]]]:
    """Finds all [action:NAME:ARG] tags in the response and strips them from the visible reply text.
    Returns (cleaned_reply, [(action_name, arg), ...]).
    """
    found_actions = []
    for match in ACTION_TAG_RE.finditer(reply):
        name = match.group(1).lower()
        arg = (match.group(2) or "").strip()
        if name != "none":
            found_actions.append((name, arg))

    cleaned = ACTION_TAG_RE.sub("", reply).strip()
    return cleaned, found_actions


def run_action(name: str, arg: str) -> tuple[bool, str]:
    """Executes a single action immediately and returns (success: bool, report_message: str)."""
    name = name.lower().strip()
    arg = arg.strip()

    # 1. Apps & Settings
    if name in ("open_app", "launch_app", "open", "launch", "start"):
        return actions.open_application(arg)
    elif name in ("close_app", "kill_app", "close"):
        return actions.close_application(arg)
    elif name in ("kill_process", "kill", "force_close", "terminate"):
        return actions.kill_process(arg)
    elif name in ("focus_app", "focus_window", "bring_to_front"):
        return actions.focus_application(arg)
    elif name in ("close_window", "close_active_window"):
        return actions.close_active_window()
    elif name in ("snap_window", "snap"):
        return actions.snap_window(arg)
    elif name in ("routine", "mode", "preset"):
        return actions.run_routine(arg)

    # 2. Volume, Media & Display
    elif name in ("set_volume", "volume"):
        return actions.set_volume(arg)
    elif name in ("mute", "toggle_mute"):
        return actions.toggle_mute()
    elif name in ("volume_up", "louder", "increase_volume"):
        return actions.volume_up()
    elif name in ("volume_down", "quieter", "decrease_volume"):
        return actions.volume_down()
    elif name in ("set_brightness", "brightness"):
        return actions.set_brightness(arg)
    elif name in ("get_brightness", "brightness_status"):
        return actions.get_brightness()
    elif name in ("media", "media_control"):
        return actions.media_control(arg)

    # 3. Window & Desktop
    elif name in ("minimize_window", "minimize"):
        return actions.minimize_active_window()
    elif name in ("maximize_window", "maximize"):
        return actions.maximize_active_window()
    elif name in ("show_desktop", "desktop"):
        return actions.show_desktop()
    elif name in ("switch_window", "alt_tab"):
        return actions.switch_window()

    # 4. Files & Folders
    elif name in ("open_folder", "explorer", "folder"):
        return actions.open_folder(arg)
    elif name in ("create_file", "make_file", "write_file"):
        parts = arg.split(":", 1)
        path_str = parts[0]
        content = parts[1] if len(parts) > 1 else ""
        return actions.create_file(path_str, content)
    elif name in ("append_file", "add_to_file"):
        parts = arg.split(":", 1)
        path_str = parts[0]
        content = parts[1] if len(parts) > 1 else ""
        return actions.append_file(path_str, content)
    elif name in ("create_folder", "make_folder", "mkdir"):
        return actions.create_folder(arg)
    elif name in ("read_file", "cat", "view_file"):
        return actions.read_file(arg)
    elif name in ("delete", "delete_file", "delete_folder", "remove", "rm"):
        return actions.delete_item(arg)
    elif name in ("list_dir", "list_files", "ls", "dir"):
        return actions.list_directory(arg)
    elif name in ("search_files", "find_file", "find"):
        parts = arg.split(",", 1)
        q = parts[0]
        d = parts[1] if len(parts) > 1 else "E:"
        return actions.search_files(q, d)
    elif name in ("zip", "zip_item", "compress"):
        return actions.zip_item(arg)
    elif name in ("unzip", "unzip_item", "extract"):
        return actions.unzip_item(arg)

    # 5. System, Power & Hardware Info
    elif name in ("power", "system_power"):
        return actions.system_power(arg)
    elif name in ("lock", "lock_pc"):
        return actions.system_power("lock")
    elif name in ("sleep", "sleep_pc"):
        return actions.system_power("sleep")
    elif name in ("restart", "restart_pc", "reboot"):
        return actions.system_power("restart")
    elif name in ("shutdown", "shutdown_pc"):
        return actions.system_power("shutdown")
    elif name in ("cancel_shutdown", "abort_shutdown"):
        return actions.system_power("cancel")
    elif name in ("empty_recycle_bin", "clean_recycle_bin"):
        return actions.empty_recycle_bin()
    elif name in ("clear_temp", "clean_temp", "clean_disk"):
        return actions.clear_temp_files()
    elif name in ("system_stats", "stats", "specs"):
        return actions.get_system_stats()
    elif name in ("battery", "battery_status"):
        return actions.get_battery_status()
    elif name in ("wifi", "wifi_status", "network_status"):
        return actions.get_wifi_status()
    elif name in ("network_info", "network", "ip", "ip_address"):
        return actions.get_network_info()
    elif name in ("top_processes", "processes", "process_list"):
        count = int(arg) if arg.isdigit() else 5
        return actions.get_top_processes(count)

    # 6. Keyboard, Mouse & Screen
    elif name in ("screenshot", "take_screenshot"):
        return actions.take_screenshot(arg)
    elif name in ("clipboard_copy", "copy_to_clipboard", "copy"):
        return actions.clipboard_copy(arg)
    elif name in ("clipboard_read", "get_clipboard", "paste"):
        return actions.clipboard_read()
    elif name in ("type_text", "type", "write"):
        return actions.type_text(arg)
    elif name in ("hotkey", "press_hotkey", "press_key"):
        return actions.press_hotkey(arg)
    elif name in ("click_at", "click"):
        return actions.click_at(arg)
    elif name in ("click_and_type",):
        return actions.click_and_type(arg)

    # 7. Shell, Math & Web
    elif name in ("calc", "calculate", "math"):
        return actions.calculate(arg)
    elif name in ("run_cmd", "cmd", "run_command", "shell", "powershell"):
        return actions.run_command(arg)
    elif name in ("open_url", "browse", "website"):
        return actions.open_url(arg)
    elif name in ("google_search", "search"):
        return actions.google_search(arg)
    elif name in ("youtube_search", "youtube", "play_song"):
        return actions.youtube_search(arg)
    elif name in ("generate_image",):
        return True, f"Image generation requested: {arg}"

    # 8. Coding & Developer Actions
    elif name in ("run_code", "execute_code", "run_python", "run_script"):
        return actions.run_code(arg)
    elif name in ("save_code_file", "save_code", "write_code"):
        return actions.save_code_file(arg)
    elif name in ("run_git", "git"):
        return actions.run_git(arg)
    elif name in ("pip_install", "install_package", "pip"):
        return actions.pip_install(arg)

    # 9. Vision & Agent Tasks
    elif name in ("enable_vision", "screen_vision", "start_vision"):
        return actions.enable_screen_vision()
    elif name in ("save_task", "create_task", "save_goal", "plan_task"):
        return actions.save_agent_task(arg)
    elif name in ("update_task", "update_task_step", "task_progress", "complete_task"):
        return actions.update_agent_task_progress(arg)
    elif name in ("list_tasks", "saved_tasks", "get_tasks"):
        return actions.list_agent_tasks()
    # 10. Autonomous Research, Email & Notifications
    elif name in ("web_search", "research", "search_web", "deep_search"):
        return actions.action_web_search(arg)
    elif name in ("send_email", "email", "mail"):
        return actions.action_send_email(arg)
    elif name in ("check_emails", "read_emails", "unread_emails", "inbox"):
        return actions.action_check_emails()
    elif name in ("notify", "send_notification", "alert"):
        parts = arg.split(":", 1)
        t = parts[0].strip() if len(parts) > 1 else "Nova AI Alert"
        m = parts[1].strip() if len(parts) > 1 else arg
        return actions.action_notify(t, m)
    elif name in ("schedule_daily", "daily_task", "add_daily"):
        return actions.action_schedule_daily(arg)
    elif name in ("schedule_once", "schedule_task", "add_schedule"):
        return actions.action_schedule_once(arg)
    else:
        log.warning("Unknown action requested: {}", name)
        # Fallback: try opening as an application or executing command
        if arg:
            return actions.open_application(arg)
        return False, f"Action '{name}' is not recognized."
