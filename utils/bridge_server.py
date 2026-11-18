"""
utils/bridge_server.py

Embedded Local HTTP Bridge Server for Nova AI Ecosystem.
Runs on 127.0.0.1:5050 in a daemon thread.
Enables WhatsApp (index.js) and Discord (main.py) to:
- Capture live desktop screenshots (/screenshot)
- Execute desktop actions (/action)
- Sync tasks (/tasks)
- Check PC stats (/stats, /health)
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from automation import actions, executor
from automation.screen_observer import screen_observer
from memory import database
from utils.logger import get_logger

log = get_logger(__name__)

_activity_feed: list[dict] = []

PORT = 5050
HOST = "127.0.0.1"


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress verbose HTTP access logs
        pass

    def _send_json(self, data: dict | list, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/health", "/status"):
            self._send_json({
                "status": "online",
                "service": "Nova AI Desktop Bridge",
                "owner": "Admin",
                "version": "2.0-master",
                "port": PORT
            })

        elif path == "/feed":
            self._send_json({"feed": _activity_feed[-50:]})

        elif path == "/screenshot":
            try:
                shot_path, win_title = screen_observer.capture_now(max_dim=1280)
                if shot_path and Path(shot_path).exists():
                    img_data = Path(shot_path).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(img_data)))
                    clean_title = (win_title or "Desktop").encode("ascii", "ignore").decode("ascii")
                    self.send_header("X-Window-Title", clean_title)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(img_data)
                else:
                    self._send_json({"error": "Failed to capture screenshot"}, 500)
            except Exception as e:
                log.exception("Bridge /screenshot failed: {}", e)
                self._send_json({"error": str(e)}, 500)

        elif path == "/tasks":
            try:
                tasks = database.get_all_agent_tasks()
                self._send_json({"tasks": tasks})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/stats":
            try:
                success, report = actions.get_system_stats()
                self._send_json({"success": success, "stats": report})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/feed":
            # Add live event from WhatsApp or Discord to feed
            import datetime
            entry = {
                "platform": body.get("platform", "Platform"),
                "sender": body.get("sender", "User"),
                "content": body.get("content", ""),
                "type": body.get("type", "in"),
                "time": datetime.datetime.now().strftime("%H:%M:%S")
            }
            _activity_feed.append(entry)
            if len(_activity_feed) > 100:
                del _activity_feed[:50]
            self._send_json({"success": True})

        else:
            self._send_json({"error": "Endpoint not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        if path == "/action":
            action_name = body.get("name") or body.get("action") or ""
            action_arg = body.get("arg") or ""

            # Check if passed as single string e.g. "open_app:chrome"
            if ":" in action_name and not action_arg:
                parts = action_name.split(":", 1)
                action_name, action_arg = parts[0], parts[1]

            if not action_name:
                self._send_json({"error": "Action name is required"}, 400)
                return

            try:
                success, report = executor.run_action(action_name, action_arg)
                self._send_json({
                    "success": success,
                    "report": report,
                    "action": action_name,
                    "arg": action_arg
                })
            except Exception as e:
                log.exception("Bridge /action failed: {}", e)
                self._send_json({"error": str(e)}, 500)

        elif path == "/tasks":
            title = body.get("title", "New Task")
            steps = body.get("steps", [])
            try:
                task_id = database.save_agent_task(title=title, steps=steps)
                self._send_json({"success": True, "task_id": task_id, "title": title})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/feed":
            # Add live event from WhatsApp or Discord to feed
            import datetime
            entry = {
                "platform": body.get("platform", "Platform"),
                "sender": body.get("sender", "User"),
                "content": body.get("content", ""),
                "type": body.get("type", "in"),
                "time": datetime.datetime.now().strftime("%H:%M:%S")
            }
            _activity_feed.append(entry)
            if len(_activity_feed) > 100:
                del _activity_feed[:50]
            self._send_json({"success": True})

        else:
            self._send_json({"error": "Endpoint not found"}, 404)


_server: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None


def start_bridge_server(port: int = PORT) -> bool:
    """Starts the Bridge HTTP server in a background daemon thread."""
    global _server, _server_thread
    if _server is not None:
        return True

    try:
        _server = ThreadingHTTPServer((HOST, port), BridgeHandler)
        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True, name="QueenBridgeServer")
        _server_thread.start()
        log.info("Nova AI Desktop Bridge started on http://{}:{}", HOST, port)
        return True
    except Exception as exc:
        log.warning("Could not start Nova Desktop Bridge on port {}: {}", port, exc)
        return False


def stop_bridge_server():
    """Stops the Bridge HTTP server gracefully."""
    global _server
    if _server:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass
        _server = None
