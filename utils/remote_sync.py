"""
utils/remote_sync.py

Desktop-Hybrid Cloud Sync Engine for Nova AI.
Manages the separation of concerns:
1. Online Data (Cloud-hosted):
   - Dynamic System Prompts (coding rules, Urdu fluency, vision instructions)
   - Dynamic Model Priority and Feature Flags
   - Remote Updates & Announcements
2. Local Data (User Private):
   - API Keys (Groq / Gemini / OpenAI)
   - Conversation History & Long-Term Memory (memory.db)
   - User Settings & Personal Preferences (user_config.json)
   - Desktop Screen Captures & Local Files

Runs non-blocking in background with instant offline caching fallback.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

from config.settings_schema import AppConfig, save_config
from utils.app_paths import user_data_dir
from utils.logger import get_logger

log = get_logger(__name__)

_CACHE_DIR = user_data_dir() / "cache"
_PROMPT_CACHE_FILE = _CACHE_DIR / "cloud_prompt_cache.json"

# In-memory prompt cache
_ACTIVE_PROMPT_OVERRIDE: str | None = None
_CLOUD_META: dict = {}


def get_active_system_prompt(fallback: str) -> str:
    """Returns the latest cloud-synced system prompt if available,
    otherwise returns cached prompt, otherwise returns the built-in fallback.
    """
    global _ACTIVE_PROMPT_OVERRIDE
    if _ACTIVE_PROMPT_OVERRIDE:
        return _ACTIVE_PROMPT_OVERRIDE

    # Try loading from local disk cache
    if _PROMPT_CACHE_FILE.exists():
        try:
            data = json.loads(_PROMPT_CACHE_FILE.read_text(encoding="utf-8"))
            prompt = data.get("system_prompt", "").strip()
            if prompt:
                _ACTIVE_PROMPT_OVERRIDE = prompt
                return prompt
        except Exception as e:
            log.warning("Could not read prompt cache: {}", e)

    return fallback


def get_cloud_metadata() -> dict:
    """Returns the latest cloud metadata (version, recommended model, announcement)."""
    return dict(_CLOUD_META)


def sync_cloud_config(cfg: AppConfig, timeout_sec: float = 3.0) -> tuple[bool, str]:
    """Fetches online configuration and system prompt from remote URL.
    Updates local cache on disk without blocking or overwriting private user keys.
    """
    global _ACTIVE_PROMPT_OVERRIDE, _CLOUD_META

    cloud_cfg = getattr(cfg, "cloud_sync", None)
    if not cloud_cfg or not getattr(cloud_cfg, "enabled", True):
        return False, "Cloud sync is disabled in settings."

    url = getattr(cloud_cfg, "remote_config_url", "").strip()
    if not url:
        return False, "No remote config URL specified."

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Nova-AI-Desktop-Hybrid/2.4 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            if resp.status != 200:
                return False, f"Remote server returned HTTP {resp.status}"
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw)

        # 1. Extract dynamic online prompt
        prompt = payload.get("system_prompt", "").strip()
        if prompt:
            _ACTIVE_PROMPT_OVERRIDE = prompt

        # 2. Extract metadata
        _CLOUD_META = {
            "version": payload.get("version", "2.4"),
            "recommended_model": payload.get("recommended_model", ""),
            "announcement": payload.get("announcement", ""),
            "features": payload.get("features", {}),
            "updated_at": payload.get("updated_at", ""),
        }

        # 3. Save to local disk cache for instant offline fallback
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "system_prompt": prompt,
            "metadata": _CLOUD_META,
            "cached_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _PROMPT_CACHE_FILE.write_text(
            json.dumps(cache_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        cloud_cfg.last_synced_at = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            save_config(cfg)
        except Exception:
            pass

        log.info("Cloud sync successful. System prompt and online config updated.")
        return True, "Online cloud config synchronized successfully."

    except Exception as exc:
        log.warning("Cloud sync skipped (offline or remote unreachable): {}", exc)
        return False, f"Cloud sync unavailable: {exc}"


def start_background_sync(cfg: AppConfig, delay_sec: float = 1.0) -> threading.Thread:
    """Launches non-blocking background thread to sync online config without slowing down startup."""
    def _worker():
        if delay_sec > 0:
            time.sleep(delay_sec)
        sync_cloud_config(cfg)

    thread = threading.Thread(target=_worker, name="CloudSyncWorker", daemon=True)
    thread.start()
    return thread
