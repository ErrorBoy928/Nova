"""
config/settings_schema.py

Defines the typed configuration schema for the AI Desktop Assistant.
Persists settings to E:\\AI_Assistant\\data\\user_config.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from utils.app_paths import user_data_dir

CONFIG_DIR = user_data_dir()
CONFIG_FILE = CONFIG_DIR / "user_config.json"

LLMProvider = Literal["groq", "gemini", "openai", "anthropic", "ollama", "lmstudio"]
Language = Literal["auto", "en", "ur"]
Theme = Literal["dark", "light"]


@dataclass
class LLMConfig:
    provider: LLMProvider = "groq"
    model: str = "qwen/qwen3.8-27b"
    api_key_env_var: str = "GROQ_API_KEY"
    api_key: str = ""
    license_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    openai_base_url: str = ""
    ollama_base_url: str = "http://localhost:11434"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    temperature: float = 0.6
    frequency_penalty: float = 0.5
    presence_penalty: float = 0.3
    max_tokens: int = 4096
    critical_thinking: bool = False


@dataclass
class VoiceConfig:
    enabled: bool = True
    auto_speak: bool = True
    tts_voice_en: str = "en-US-AriaNeural"
    tts_voice_ur: str = "ur-PK-UzmaNeural"
    speech_rate: str = "+0%"
    volume: str = "+0%"
    stt_language: Language = "auto"  # auto-detects Urdu or English
    wake_word_enabled: bool = False
    wake_word: str = "Nova"


@dataclass
class UIConfig:
    theme: Theme = "dark"
    assistant_name: str = "Nova"
    always_on_top: bool = False
    window_opacity: float = 1.0
    start_width: int = 500
    start_height: int = 720
    screen_observing: bool = False


@dataclass
class SafetyConfig:
    confirm_before_destructive: bool = False
    recheck_decisions: bool = False


@dataclass
class CloudSyncConfig:
    enabled: bool = True
    remote_config_url: str = "https://raw.githubusercontent.com/Nova-AI-Assistant/cloud-config/main/config.json"
    auto_update_prompts: bool = True
    last_synced_at: str = ""


@dataclass
class EmailConfig:
    enabled: bool = False
    email: str = ""
    app_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    imap_host: str = "imap.gmail.com"


@dataclass
class DiscordConfig:
    enabled: bool = False
    bot_token: str = ""


@dataclass
class WhatsAppConfig:
    enabled: bool = True
    owner_number: str = ""


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    cloud_sync: CloudSyncConfig = field(default_factory=CloudSyncConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    whatsapp: WhatsAppConfig = field(default_factory=WhatsAppConfig)
    user_name: str | None = None
    language: Language = "auto"


def load_config() -> AppConfig:
    """Load configuration from disk, filling in any missing fields with defaults."""
    if not CONFIG_FILE.exists():
        cfg = AppConfig()
        save_config(cfg)
        return cfg

    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AppConfig()

    def _filter(cls, d):
        if not isinstance(d, dict):
            return {}
        import inspect
        valid = inspect.signature(cls).parameters.keys()
        return {k: v for k, v in d.items() if k in valid}

    cfg = AppConfig(
        llm=LLMConfig(**_filter(LLMConfig, raw.get("llm", {}))),
        voice=VoiceConfig(**_filter(VoiceConfig, raw.get("voice", {}))),
        ui=UIConfig(**_filter(UIConfig, raw.get("ui", {}))),
        safety=SafetyConfig(**_filter(SafetyConfig, raw.get("safety", {}))),
        cloud_sync=CloudSyncConfig(**_filter(CloudSyncConfig, raw.get("cloud_sync", {}))),
        email=EmailConfig(**_filter(EmailConfig, raw.get("email", {}))),
        discord=DiscordConfig(**_filter(DiscordConfig, raw.get("discord", {}))),
        whatsapp=WhatsAppConfig(**_filter(WhatsAppConfig, raw.get("whatsapp", {}))),
        user_name=raw.get("user_name"),
        language=raw.get("language", "auto"),
    )
    # Ensure Groq is default if provider unset or legacy gemini
    if not cfg.llm.provider or cfg.llm.provider == "gemini":
        cfg.llm.provider = "groq"
        cfg.llm.model = "qwen/qwen3.8-27b"
        cfg.llm.api_key_env_var = "GROQ_API_KEY"
    if "gemini" in (cfg.llm.model or "") or cfg.llm.model in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b"):
        cfg.llm.model = "qwen/qwen3.8-27b"
    if getattr(cfg.llm, "temperature", 0.2) < 0.4:
        cfg.llm.temperature = 0.6
    if cfg.llm.max_tokens < 1000:
        cfg.llm.max_tokens = 4096
    return cfg


def save_config(cfg: AppConfig) -> None:
    """Save configuration to disk as formatted JSON."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(asdict(cfg), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_api_key(cfg: AppConfig) -> str | None:
    """Fetch the active provider's API key from config or environment."""
    if cfg.llm.provider in ("ollama", "lmstudio"):
        return None
    val = (cfg.llm.api_key or "").strip().strip('"\'')
    if val:
        return val
    env_val = (os.environ.get(cfg.llm.api_key_env_var) or "").strip().strip('"\'')
    if env_val:
        return env_val
    return None
