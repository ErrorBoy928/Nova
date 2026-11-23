"""
automation/desktop_bridge.py

Queen AI - Desktop IPC & Remote Control HTTP Bridge.
Enables WhatsApp (index.js) and Discord (main.py) to interact directly with Error Boy's PC:
- Live Screen Captures (/api/screenshot)
- Desktop Action Execution (/api/action)
- PC System Status (/api/status)
- Cross-Platform Tasks Sync (/api/tasks)
"""

from __future__ import annotations

import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from PIL import ImageGrab

from automation.screen_observer import get_active_window_title, get_open_windows
from automation.executor import run_action
from memory.database import Database
from utils.logger import get_logger

log = get_logger(__name__)

_SERVER_INSTANCE: ThreadingHTTPServer | None = None
_START_TIME = time.time()
_DB = Database()


class DesktopBridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress verbose standard HTTP access logs
        pass

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # 1. Health & PC Status
        if path in ("", "/api/status"):
            active_win = get_active_window_title()
            open_wins = get_open_windows()[:8]
            tasks = _DB.list_tasks(status="pending")
            uptime_min = int((time.time() - _START_TIME) // 60)
            self._send_json(200, {
                "status": "online",
                "assistant": "Queen AI Desktop",
                "owner": "Error Boy (Mohib)",
                "active_window": active_win,
                "open_windows": open_wins,
                "screen_observing": True,
                "tasks_count": len(tasks),
                "uptime": f"{uptime_min} minutes",
            })
            return

        # 2. Live Screen Capture
        if path == "/api/screenshot":
            try:
                # Capture primary monitor screen
                img = ImageGrab.grab()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=80)
                img_bytes = buf.getvalue()

                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(img_bytes)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(img_bytes)
                return
            except Exception as e:
                log.exception("Screenshot capture failed in bridge: {}", e)
                self._send_json(500, {"status": "error", "message": str(e)})
                return

        # 3. Tasks List
        if path == "/api/tasks":
            try:
                tasks = _DB.list_tasks(status="pending")
                self._send_json(200, {"status": "ok", "tasks": tasks})
                return
            except Exception as e:
                self._send_json(500, {"status": "error", "message": str(e)})
                return

        self._send_json(404, {"status": "error", "message": f"Endpoint not found: {path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        # 1. Execute Desktop Action
        if path == "/api/action":
            raw_action = payload.get("action", "").strip()
            if not raw_action:
                self._send_json(400, {"status": "error", "message": "Missing 'action' field in JSON payload."})
                return

            # Parse action format: "open_app:notepad" or "system_stats"
            if ":" in raw_action:
                act_name, act_arg = raw_action.split(":", 1)
            else:
                act_name, act_arg = raw_action, ""

            try:
                success, msg = run_action(act_name.strip(), act_arg.strip())
                self._send_json(200, {
                    "status": "ok" if success else "failed",
                    "action": act_name,
                    "arg": act_arg,
                    "message": msg
                })
                return
            except Exception as e:
                log.exception("Action execution failed in bridge: {}", e)
                self._send_json(500, {"status": "error", "message": str(e)})
                return

        # 2. Add New Task
        if path == "/api/tasks":
            title = payload.get("title", "").strip()
            desc = payload.get("description", "").strip()
            steps = payload.get("steps", [])

            if not title:
                self._send_json(400, {"status": "error", "message": "Task 'title' is required."})
                return

            try:
                task_id = _DB.save_task(title=title, description=desc, steps=steps)
                self._send_json(200, {
                    "status": "ok",
                    "task_id": task_id,
                    "message": f"Task '{title}' successfully created on Error Boy's PC!"
                })
                return
            except Exception as e:
                self._send_json(500, {"status": "error", "message": str(e)})
                return

        self._send_json(404, {"status": "error", "message": f"Endpoint not found: {path}"})


def start_desktop_bridge(host: str = "127.0.0.1", port: int = 5050, daemon: bool = True) -> ThreadingHTTPServer:
    """Spawns the Desktop Bridge HTTP Server in a background thread."""
    global _SERVER_INSTANCE
    if _SERVER_INSTANCE is not None:
        return _SERVER_INSTANCE

    try:
        server = ThreadingHTTPServer((host, port), DesktopBridgeHandler)
        _SERVER_INSTANCE = server
        thread = threading.Thread(target=server.serve_forever, daemon=daemon, name="QueenDesktopBridgeThread")
        thread.start()
        log.info("Queen AI Desktop Bridge started on http://{}:{}", host, port)
        return server
    except Exception as e:
        log.warning("Could not start Desktop Bridge on {}:{}: {}", host, port, e)
        return None


if __name__ == "__main__":
    print("👑 Queen AI Desktop Bridge running on http://127.0.0.1:5050 (Press Ctrl+C to stop)")
    srv = start_desktop_bridge(daemon=False)
    try:
        if srv:
            srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Desktop Bridge...")
