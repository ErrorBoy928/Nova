"""
memory/database.py

SQLite-backed long-term memory: user preferences, conversation history,
custom commands, and learned user facts.
Stored in E:\\AI_Assistant\\data\\database\\memory.db.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from utils.app_paths import user_data_dir
from utils.logger import get_logger

log = get_logger(__name__)

DB_PATH = user_data_dir() / "database" / "memory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    session_id TEXT DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_pinned  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS custom_commands (
    trigger_phrase TEXT PRIMARY KEY,
    action         TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_facts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fact       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    steps_json   TEXT NOT NULL,
    current_step INTEGER DEFAULT 0,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id          TEXT PRIMARY KEY,
    task_type   TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    target_time TEXT NOT NULL,
    last_run    TEXT,
    status      TEXT DEFAULT 'active',
    notify_wa   INTEGER DEFAULT 1,
    notify_dc   INTEGER DEFAULT 1,
    notify_app  INTEGER DEFAULT 1,
    created_at  TEXT NOT NULL
);
"""


_initialized = False


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    global _initialized
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if not _initialized:
        conn.executescript(SCHEMA)
        _initialized = True
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist yet. Safe to call on every startup."""
    with _connection() as conn:
        conn.executescript(SCHEMA)
        try:
            conn.execute("ALTER TABLE scheduled_tasks ADD COLUMN title TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE conversation_history ADD COLUMN session_id TEXT DEFAULT 'default'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE chat_sessions ADD COLUMN is_pinned INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_sess ON conversation_history(session_id)")
        except Exception:
            pass
        try:
            cur = conn.execute("SELECT COUNT(*) as count FROM chat_sessions")
            if cur.fetchone()["count"] == 0:
                now = datetime.now().isoformat(timespec="seconds")
                conn.execute(
                    "INSERT INTO chat_sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    ("default", "Main Workspace", now, now)
                )
        except Exception:
            pass
    log.info("Memory database ready at {}", DB_PATH)


def set_preference(key: str, value: str) -> None:
    with _connection() as conn:
        conn.execute(
            "INSERT INTO preferences (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_preference(key: str, default: str | None = None) -> str | None:
    with _connection() as conn:
        row = conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


# ---------------------------------------------------------------------------
# Multi-Session Chat Threads
# ---------------------------------------------------------------------------

def create_session(title: str = "New Session", session_id: str | None = None) -> str:
    """Creates a new isolated chat session thread and returns its session_id."""
    import uuid
    sid = session_id or f"sess_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat(timespec="seconds")
    with _connection() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (sid, title.strip() or "New Session", now, now)
        )
    return sid


def get_all_sessions() -> list[dict[str, str]]:
    """Returns all chat sessions ordered by most recently updated."""
    with _connection() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at, COALESCE(is_pinned, 0) as is_pinned "
            "FROM chat_sessions ORDER BY is_pinned DESC, updated_at DESC"
        ).fetchall()
        sessions = [dict(r) for r in rows]
        if not sessions:
            now = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO chat_sessions (id, title, created_at, updated_at, is_pinned) VALUES (?, ?, ?, ?, ?)",
                ("default", "Main Workspace", now, now, 0)
            )
            return [{"id": "default", "title": "Main Workspace", "created_at": now, "updated_at": now, "is_pinned": 0}]
        return sessions


def get_session(session_id: str) -> dict[str, str] | None:
    """Fetches metadata for a single session."""
    with _connection() as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at, COALESCE(is_pinned, 0) as is_pinned "
            "FROM chat_sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None


def toggle_pin_session(session_id: str) -> bool:
    """Toggles pinning for a session. Pinned sessions anchor to the top of the sidebar."""
    with _connection() as conn:
        row = conn.execute("SELECT COALESCE(is_pinned, 0) as is_pinned FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return False
        cur = row["is_pinned"]
        new_val = 0 if cur else 1
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute("UPDATE chat_sessions SET is_pinned = ?, updated_at = ? WHERE id = ?", (new_val, now, session_id))
        return bool(new_val)


def rename_session(session_id: str, new_title: str) -> None:
    """Renames an existing chat session."""
    now = datetime.now().isoformat(timespec="seconds")
    with _connection() as conn:
        conn.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
            (new_title.strip() or "Untitled Session", now, session_id)
        )


def delete_session(session_id: str) -> None:
    """Permanently deletes a chat session and all messages within it."""
    with _connection() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        conn.execute("DELETE FROM conversation_history WHERE session_id = ?", (session_id,))


def delete_last_assistant_message(session_id: str = "default") -> bool:
    """Deletes the most recent assistant message from the session history."""
    sid = session_id or "default"
    with _connection() as conn:
        row = conn.execute(
            "SELECT id FROM conversation_history WHERE session_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
            (sid,)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM conversation_history WHERE id = ?", (row["id"],))
            return True
        return False


def search_all_sessions(query: str, limit: int = 25) -> list[dict[str, str]]:
    """Searches across all chat sessions for matching messages, returning matched turns with session title."""
    clean_q = (query or "").strip()
    if not clean_q:
        return []
    with _connection() as conn:
        rows = conn.execute(
            "SELECT c.id, c.session_id, c.role, c.content, c.timestamp, COALESCE(s.title, 'Main Workspace') as session_title "
            "FROM conversation_history c "
            "LEFT JOIN chat_sessions s ON c.session_id = s.id "
            "WHERE c.content LIKE ? "
            "ORDER BY c.id DESC LIMIT ?",
            (f"%{clean_q}%", limit)
        ).fetchall()
        return [dict(r) for r in rows]


def add_message(role: str, content: str, session_id: str = "default") -> None:
    # Sanitize repetitive loops before saving
    import re
    clean_content = re.sub(r'(\S+)(?:\s+\1){2,}', r'\1', (content or "").strip(), flags=re.UNICODE)
    now = datetime.now().isoformat(timespec="seconds")
    sid = session_id or "default"
    with _connection() as conn:
        conn.execute(
            "INSERT INTO conversation_history (role, content, timestamp, session_id) VALUES (?, ?, ?, ?)",
            (role, clean_content, now, sid),
        )
        try:
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (now, sid),
            )
        except Exception:
            pass


def get_recent_history(limit: int = 50, session_id: str = "default") -> list[dict[str, str]]:
    """Return the last `limit` messages for the given session, oldest first."""
    import re
    sid = session_id or "default"
    with _connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversation_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (sid, limit),
        ).fetchall()
        if not rows and sid == "default":
            rows = conn.execute(
                "SELECT role, content FROM conversation_history WHERE session_id IS NULL OR session_id = 'default' ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    history = []
    for r in reversed(rows):
        c = re.sub(r'(\S+)(?:\s+\1){2,}', r'\1', r["content"], flags=re.UNICODE)
        history.append({"role": r["role"], "content": c})
    return history


def clear_history(session_id: str = "default") -> None:
    sid = session_id or "default"
    with _connection() as conn:
        if sid == "default":
            conn.execute("DELETE FROM conversation_history WHERE session_id = 'default' OR session_id IS NULL")
        else:
            conn.execute("DELETE FROM conversation_history WHERE session_id = ?", (sid,))


_MAX_FACTS = 150


def add_fact(fact: str) -> None:
    fact = fact.strip()
    if not fact:
        return
    with _connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM user_facts WHERE fact = ?", (fact,)
        ).fetchone()
        if existing:
            return
        conn.execute(
            "INSERT INTO user_facts (fact, created_at) VALUES (?, ?)",
            (fact, datetime.now().isoformat(timespec="seconds")),
        )
        count = conn.execute("SELECT COUNT(*) AS c FROM user_facts").fetchone()["c"]
        if count > _MAX_FACTS:
            conn.execute(
                "DELETE FROM user_facts WHERE id = ("
                "SELECT id FROM user_facts ORDER BY id ASC LIMIT 1)"
            )


def get_all_facts() -> list[str]:
    with _connection() as conn:
        rows = conn.execute("SELECT fact FROM user_facts ORDER BY id ASC").fetchall()
        return [r["fact"] for r in rows]


def clear_facts() -> None:
    with _connection() as conn:
        conn.execute("DELETE FROM user_facts")


# Compatibility aliases for actions and tests
remember_fact = add_fact
get_facts = get_all_facts


# ── Agent Tasks / Multi-Step Goals (Persistent Planner) ──────────────────────
import json
import uuid


def save_agent_task(title: str, steps: list[str], task_id: str | None = None) -> dict:
    """Saves or updates a structured multi-step agent task."""
    tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat(timespec="seconds")
    steps_clean = [s.strip() for s in steps if s.strip()]
    steps_json = json.dumps(steps_clean, ensure_ascii=False)

    with _connection() as conn:
        conn.execute(
            """INSERT INTO agent_tasks (id, title, steps_json, current_step, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   title = excluded.title,
                   steps_json = excluded.steps_json,
                   updated_at = excluded.updated_at
            """,
            (tid, title.strip(), steps_json, 0, "in_progress", now, now)
        )
    return {
        "id": tid,
        "title": title.strip(),
        "steps": steps_clean,
        "current_step": 0,
        "status": "in_progress",
        "created_at": now,
        "updated_at": now,
    }


def update_agent_task_step(task_id: str, step_index: int, status: str = "in_progress") -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _connection() as conn:
        res = conn.execute(
            "UPDATE agent_tasks SET current_step = ?, status = ?, updated_at = ? WHERE id = ?",
            (step_index, status, now, task_id)
        )
        return res.rowcount > 0


def complete_agent_task(task_id: str) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _connection() as conn:
        res = conn.execute(
            "UPDATE agent_tasks SET status = 'completed', updated_at = ? WHERE id = ?",
            (now, task_id)
        )
        return res.rowcount > 0


def delete_agent_task(task_id: str) -> bool:
    with _connection() as conn:
        res = conn.execute("DELETE FROM agent_tasks WHERE id = ?", (task_id,))
        return res.rowcount > 0


def get_active_agent_task() -> dict | None:
    with _connection() as conn:
        row = conn.execute(
            "SELECT * FROM agent_tasks WHERE status = 'in_progress' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "steps": json.loads(row["steps_json"]),
            "current_step": row["current_step"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def get_all_agent_tasks(limit: int = 30) -> list[dict]:
    with _connection() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_tasks ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        tasks = []
        for r in rows:
            tasks.append({
                "id": r["id"],
                "title": r["title"],
                "steps": json.loads(r["steps_json"]),
                "current_step": r["current_step"],
                "status": r["status"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            })
        return tasks


# ── Scheduled Tasks (Daily Recurring & Day Schedule) ──────────────────────────
def save_scheduled_task(
    task_type: str,
    prompt: str,
    target_time: str = "",
    title: str = "",
    notify_wa: bool = True,
    notify_dc: bool = True,
    notify_app: bool = True,
    notify_channels: str = "",
    scheduled_time: str = "",
    task_id: str | None = None
) -> dict:
    """Saves a daily recurring or one-off scheduled task with universal compatibility."""
    final_time = (target_time or scheduled_time or "00:00").strip()
    if notify_channels:
        nc = notify_channels.lower()
        notify_wa = "whatsapp" in nc
        notify_dc = "discord" in nc
        notify_app = "desktop" in nc or "pc" in nc
    final_title = (title or prompt[:40]).strip()
    tid = task_id or f"sched_{int(datetime.now().timestamp())}_{abs(hash(prompt)) % 10000}"
    now = datetime.now().isoformat(timespec="seconds")
    with _connection() as conn:
        conn.execute(
            """INSERT INTO scheduled_tasks (id, task_type, prompt, target_time, title, status, notify_wa, notify_dc, notify_app, created_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   prompt = excluded.prompt,
                   target_time = excluded.target_time,
                   title = excluded.title,
                   notify_wa = excluded.notify_wa,
                   notify_dc = excluded.notify_dc,
                   notify_app = excluded.notify_app
            """,
            (tid, task_type, prompt.strip(), final_time, final_title, int(notify_wa), int(notify_dc), int(notify_app), now)
        )
    return {
        "id": tid,
        "task_type": task_type,
        "title": final_title,
        "prompt": prompt.strip(),
        "target_time": final_time,
        "scheduled_time": final_time,
        "notify_channels": f"{'whatsapp,' if notify_wa else ''}{'discord,' if notify_dc else ''}{'desktop' if notify_app else ''}".strip(','),
        "status": "active",
        "created_at": now
    }


def get_scheduled_tasks(task_type: str | None = None) -> list[dict]:
    """Returns active and completed scheduled tasks filtered optionally by type."""
    with _connection() as conn:
        if task_type:
            rows = conn.execute(
                "SELECT * FROM scheduled_tasks WHERE task_type = ? ORDER BY target_time ASC", (task_type,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scheduled_tasks ORDER BY target_time ASC"
            ).fetchall()
        tasks = []
        for r in rows:
            keys = r.keys()
            t_title = r["title"] if "title" in keys and r["title"] else r["prompt"][:40]
            n_wa = bool(r["notify_wa"]) if "notify_wa" in keys else True
            n_dc = bool(r["notify_dc"]) if "notify_dc" in keys else True
            n_app = bool(r["notify_app"]) if "notify_app" in keys else True
            ch_list = []
            if n_wa: ch_list.append("whatsapp")
            if n_dc: ch_list.append("discord")
            if n_app: ch_list.append("desktop")

            tasks.append({
                "id": r["id"],
                "task_type": r["task_type"],
                "title": t_title,
                "prompt": r["prompt"],
                "target_time": r["target_time"],
                "scheduled_time": r["target_time"],
                "last_run": r["last_run"],
                "status": r["status"],
                "notify_wa": n_wa,
                "notify_dc": n_dc,
                "notify_app": n_app,
                "notify_channels": ",".join(ch_list),
                "created_at": r["created_at"],
            })
        return tasks


def delete_scheduled_task(task_id: str) -> bool:
    """Deletes a scheduled task by ID."""
    with _connection() as conn:
        res = conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        return res.rowcount > 0


def update_scheduled_task_status(task_id: str, status: str) -> bool:
    """Updates status ('active', 'paused', 'completed')."""
    with _connection() as conn:
        res = conn.execute("UPDATE scheduled_tasks SET status = ? WHERE id = ?", (status, task_id))
        return res.rowcount > 0


def mark_scheduled_task_run(task_id: str, run_time: str, mark_completed: bool = False) -> bool:
    """Records execution timestamp."""
    status_clause = ", status = 'completed'" if mark_completed else ""
    with _connection() as conn:
        res = conn.execute(
            f"UPDATE scheduled_tasks SET last_run = ? {status_clause} WHERE id = ?",
            (run_time, task_id)
        )
        return res.rowcount > 0



