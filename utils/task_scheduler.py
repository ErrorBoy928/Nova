"""
utils/task_scheduler.py

Background Autonomous Task Scheduler for Nova AI.
Handles:
1. Daily Recurring Automations (triggers every day at set HH:MM)
2. Day Schedule / One-Off Tasks (triggers today at set HH:MM and completes)
Dispatches multi-channel alerts (Desktop Toast, WhatsApp DM, Discord DM).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from utils.logger import get_logger

log = get_logger(__name__)

_scheduler_running = False
_scheduler_thread: threading.Thread | None = None


def _scheduler_loop():
    from memory import database as db
    from utils.notifier import send_universal_notification
    from automation import executor

    log.info("Nova Autonomous Task Scheduler daemon started.")
    while _scheduler_running:
        try:
            now = datetime.now()
            current_hhmm = now.strftime("%H:%M")
            today_date = now.strftime("%Y-%m-%d")

            tasks = db.get_scheduled_tasks()
            for t in tasks:
                if t.get("status") != "active":
                    continue

                target_time = t.get("target_time", "").strip()
                last_run = t.get("last_run", "")

                # If current time matches target time and hasn't run today
                if target_time == current_hhmm and (not last_run or not last_run.startswith(today_date)):
                    prompt = t.get("prompt", "")
                    task_type = t.get("task_type", "daily_recurring")
                    log.info("Executing scheduled task [{}]: '{}'", t['id'], prompt)

                    # Mark task as run for today
                    is_one_off = (task_type == "day_schedule")
                    db.mark_scheduled_task_run(t['id'], f"{today_date} {current_hhmm}", mark_completed=is_one_off)

                    # Execute prompt via automation or background runner
                    clean_text, actions = executor.extract_actions(prompt)
                    action_reports = []
                    if actions:
                        for act_name, act_arg in actions:
                            ok, rep = executor.run_action(act_name, act_arg)
                            action_reports.append(rep)
                    else:
                        # Fallback quick action check
                        ok, rep = executor.run_action("run_cmd", prompt)
                        action_reports.append(rep)

                    result_summary = " | ".join(action_reports) if action_reports else "Task executed successfully."

                    # Universal Notification
                    alert_title = f"Nova Task Scheduled Alert ({target_time})"
                    alert_msg = f"Task: {prompt}\nResult: {result_summary}"
                    send_universal_notification(alert_title, alert_msg)

        except Exception as exc:
            log.warning("Task scheduler error: {}", exc)

        time.sleep(20)


def start_scheduler():
    """Starts the background task scheduler daemon."""
    global _scheduler_running, _scheduler_thread
    if _scheduler_running:
        return

    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="NovaTaskScheduler")
    _scheduler_thread.start()


def stop_scheduler():
    """Stops the scheduler daemon."""
    global _scheduler_running
    _scheduler_running = False
