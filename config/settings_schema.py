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
    owner_id: str = ""


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


def sync_to_env(cfg: AppConfig) -> None:
    """Synchronizes AppConfig state to E:/Nova_AI/.env and live os.environ."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    existing_lines = []
    if env_path.exists():
        try:
            existing_lines = env_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            pass

    env_map: dict[str, str] = {}
    for line in existing_lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            env_map[k.strip()] = v.strip()

    # Update keys from cfg
    if cfg.llm.api_key:
        if cfg.llm.provider == "groq":
            env_map["GROQ_API_KEY"] = cfg.llm.api_key
            os.environ["GROQ_API_KEY"] = cfg.llm.api_key
        elif cfg.llm.provider == "gemini":
            env_map["GEMINI_API_KEY"] = cfg.llm.api_key
            os.environ["GEMINI_API_KEY"] = cfg.llm.api_key
        elif cfg.llm.provider == "openai":
            env_map["OPENAI_API_KEY"] = cfg.llm.api_key
            os.environ["OPENAI_API_KEY"] = cfg.llm.api_key
        elif cfg.llm.provider == "anthropic":
            env_map["ANTHROPIC_API_KEY"] = cfg.llm.api_key
            os.environ["ANTHROPIC_API_KEY"] = cfg.llm.api_key

    if cfg.user_name is not None:
        env_map["OWNER_NAME"] = cfg.user_name.strip() or "Admin"
    else:
        env_map["OWNER_NAME"] = "Admin"
    os.environ["OWNER_NAME"] = env_map["OWNER_NAME"]

    clean_num = "".join(c for c in (cfg.whatsapp.owner_number or "") if c.isdigit())
    env_map["OWNER_NUMBERS"] = clean_num
    os.environ["OWNER_NUMBERS"] = clean_num

    env_map["DISCORD_BOT_TOKEN"] = (cfg.discord.bot_token or "").strip()
    os.environ["DISCORD_BOT_TOKEN"] = env_map["DISCORD_BOT_TOKEN"]

    env_map["OWNER_DISCORD_IDS"] = (cfg.discord.owner_id or "").strip()
    os.environ["OWNER_DISCORD_IDS"] = env_map["OWNER_DISCORD_IDS"]

    env_map["EMAIL_USER"] = (cfg.email.email or "").strip()
    os.environ["EMAIL_USER"] = env_map["EMAIL_USER"]

    env_map["EMAIL_PASS"] = (cfg.email.app_password or "").strip()
    os.environ["EMAIL_PASS"] = env_map["EMAIL_PASS"]

    env_map["EMAIL_SMTP"] = (cfg.email.smtp_host or "smtp.gmail.com").strip()
    os.environ["EMAIL_SMTP"] = env_map["EMAIL_SMTP"]

    lines = [
        "# Nova AI Environment Configuration",
        "# Auto-synced from Desktop App Settings & Connections Hub",
        "",
        "# AI API Keys:",
        f"GROQ_API_KEY={env_map.get('GROQ_API_KEY', '')}",
        f"GEMINI_API_KEY={env_map.get('GEMINI_API_KEY', '')}",
        f"OPENAI_API_KEY={env_map.get('OPENAI_API_KEY', '')}",
        f"ANTHROPIC_API_KEY={env_map.get('ANTHROPIC_API_KEY', '')}",
        "",
        "# User Profile & Service Owner:",
        f"OWNER_NAME={env_map.get('OWNER_NAME', 'Admin')}",
        f"OWNER_NUMBERS={env_map.get('OWNER_NUMBERS', '')}",
        f"OWNER_DISCORD_IDS={env_map.get('OWNER_DISCORD_IDS', '')}",
        "",
        "# Bot & Channel Credentials:",
        f"DISCORD_BOT_TOKEN={env_map.get('DISCORD_BOT_TOKEN', '')}",
        "",
        "# Email / SMTP Configuration:",
        f"EMAIL_USER={env_map.get('EMAIL_USER', '')}",
        f"EMAIL_PASS={env_map.get('EMAIL_PASS', '')}",
        f"EMAIL_SMTP={env_map.get('EMAIL_SMTP', 'smtp.gmail.com')}",
        f"EMAIL_PORT={env_map.get('EMAIL_PORT', '587')}",
        "",
        "# Cloud Server Port:",
        f"PORT={env_map.get('PORT', '3000')}",
        "",
    ]
    try:
        env_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass


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

    # Sync missing values from environment if available
    if not cfg.user_name and os.environ.get("OWNER_NAME"):
        cfg.user_name = os.environ.get("OWNER_NAME")
    if not cfg.whatsapp.owner_number and os.environ.get("OWNER_NUMBERS"):
        cfg.whatsapp.owner_number = os.environ.get("OWNER_NUMBERS")
    if not cfg.discord.bot_token and os.environ.get("DISCORD_BOT_TOKEN"):
        cfg.discord.bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not cfg.discord.owner_id and os.environ.get("OWNER_DISCORD_IDS"):
        cfg.discord.owner_id = os.environ.get("OWNER_DISCORD_IDS")
    if not cfg.llm.api_key and os.environ.get("GROQ_API_KEY"):
        cfg.llm.api_key = os.environ.get("GROQ_API_KEY")

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
    """Save configuration to disk as formatted JSON and sync with .env."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(asdict(cfg), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    sync_to_env(cfg)


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
