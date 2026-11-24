"""
ai/llm_manager.py

Provider-agnostic LLM interface for the AI Desktop Assistant.
Primary ultra-fast engine: Groq (Llama 3.1 8B & Llama 3.3 70B).
Also supports Gemini, OpenAI, Anthropic, Ollama, and LM Studio.
Features dynamic model discovery, real-time token streaming (<200ms latency),
multi-model auto-fallback, and direct API key verification.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from typing import Generator, Iterable

from config.settings_schema import AppConfig, get_api_key, save_config
from utils.logger import get_logger

log = get_logger(__name__)

_THINK_BLOCK_RE = re.compile(
    r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_UNCLOSED_THINK_RE = re.compile(
    r"<(think|thinking|reasoning)>.*", re.DOTALL | re.IGNORECASE
)

# Groq production models prioritized for guaranteed access, speed & coding reasoning
GROQ_MODELS_PRIORITY = [
    "qwen/qwen3.8-27b",
    "allam-2-7b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-3.2-3b-preview",
    "llama-3.2-1b-preview",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

_GROQ_MODELS_CACHE: list[str] = []
_GROQ_MODELS_CACHE_TIME: float = 0.0


def clean_repetitive_patterns(text: str) -> str:
    """Detects and compresses degenerate repetitive loops like 'کیا کیا کیا کیا'."""
    if not text:
        return text
    # Clean any token repeated 3 or more times consecutively
    cleaned = re.sub(r'(\S+)(?:\s+\1){2,}', r'\1', text, flags=re.UNICODE)
    return cleaned

# Google Gemini fallback models
GEMINI_MODELS_PRIORITY = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-1.5-flash",
]


def _strip_thinking(text: str) -> str:
    text = _THINK_BLOCK_RE.sub("", text)
    text = _UNCLOSED_THINK_RE.sub("", text)
    return text.strip()


def verify_groq_key(api_key: str) -> tuple[bool, str, str]:
    """Tests an API key against Groq API with dynamic model discovery.
    Returns (is_valid: bool, message: str, working_model: str).
    """
    key = (api_key or "").strip().strip('"\'')
    if not key:
        return False, "Groq API key cannot be empty.", ""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1", timeout=12.0)

        # Discover live models available on this account
        live_models = []
        try:
            live_models = [m.id for m in client.models.list().data]
        except Exception as e:
            log.warning("Could not list remote models: {}", e)

        # Build prioritized test list
        candidates = []
        for p in GROQ_MODELS_PRIORITY:
            if not live_models or p in live_models:
                candidates.append(p)
        if not candidates and live_models:
            candidates = [m for m in live_models if "whisper" not in m]

        for mod_name in candidates:
            try:
                resp = client.chat.completions.create(
                    model=mod_name,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=5,
                )
                if resp and resp.choices:
                    return True, f"Groq key verified! Active model: {mod_name}", mod_name
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ["does not exist", "model_not_found", "not found", "404", "do not have access", "decommissioned", "deprecated", "unsupported"]):
                    continue
                if any(x in err for x in ["invalid_api_key", "unauthorized", "401", "forbidden"]):
                    return False, f"Invalid Groq API Key: {e}", ""
                if "rate_limit" in err or "quota" in err:
                    return True, f"Groq key recognized (Rate limited): {mod_name}", mod_name

        return False, "Could not find an accessible text model on this Groq account.", ""
    except Exception as exc:
        return False, f"Verification error: {exc}", ""


def verify_anthropic_key(api_key: str) -> tuple[bool, str, str]:
    """Tests an API key against Anthropic API."""
    key = (api_key or "").strip().strip('"\'')
    if not key:
        return False, "Anthropic API key cannot be empty.", ""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=12.0)
        resp = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}]
        )
        if resp and resp.content:
            return True, "Anthropic Claude key verified!", "claude-3-7-sonnet-20250219"
        return False, "Anthropic returned empty verification response.", ""
    except Exception as exc:
        return False, f"Verification error: {exc}", ""


def verify_openai_key(api_key: str) -> tuple[bool, str, str]:
    """Tests an API key against OpenAI API."""
    key = (api_key or "").strip().strip('"\'')
    if not key:
        return False, "OpenAI API key cannot be empty.", ""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, timeout=12.0)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        if resp and resp.choices:
            return True, "OpenAI ChatGPT key verified!", "gpt-4o"
        return False, "OpenAI returned empty verification response.", ""
    except Exception as exc:
        err = str(exc).lower()
        if "insufficient_quota" in err or "quota" in err:
            return True, "OpenAI key valid (Quota exceeded on account)", "gpt-4o"
        return False, f"Verification error: {exc}", ""


def verify_gemini_key(api_key: str) -> tuple[bool, str, str]:
    """Tests an API key against Google Gemini API."""
    key = (api_key or "").strip().strip('"\'')
    if not key:
        return False, "API key cannot be empty.", ""

    try:
        import google.generativeai as genai
        genai.configure(api_key=key)

        for mod_name in GEMINI_MODELS_PRIORITY:
            try:
                model = genai.GenerativeModel(mod_name)
                resp = model.generate_content("Ping", generation_config={"max_output_tokens": 5})
                if resp:
                    return True, f"Key verified! Active model: {mod_name}", mod_name
            except Exception as e:
                err = str(e).lower()
                if "no longer available" in err or "404" in err or "not found" in err or "deprecated" in err:
                    continue
                if "api_key_invalid" in err or "invalid api key" in err or "permission_denied" in err:
                    return False, f"Invalid API Key: {e}", ""
                if "quota" in err or "resource_exhausted" in err:
                    return True, f"Key recognized: {mod_name}", mod_name

        return False, "Key could not connect to Gemini models.", ""
    except Exception as exc:
        return False, f"Verification error: {exc}", ""


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "system"
    content: str
    image_path: str | None = None


class LLMError(RuntimeError):
    """Raised when an LLM provider call fails."""


class LLMManager:
    def __init__(self, config: AppConfig):
        self.config = config

    def chat_stream(self, messages: Iterable[ChatMessage], system_prompt: str = "") -> Generator[str, None, None]:
        """Streams text chunks in real-time for immediate UI display."""
        provider = self.config.llm.provider
        try:
            if provider == "groq":
                yield from self._chat_groq_stream(messages, system_prompt)
            elif provider == "anthropic":
                yield from self._chat_anthropic_stream(messages, system_prompt)
            elif provider == "gemini":
                yield from self._chat_gemini_stream(messages, system_prompt)
            elif provider == "openai":
                yield from self._chat_openai_stream(messages, system_prompt)
            else:
                full_reply = self.chat(messages, system_prompt)
                yield full_reply
        except LLMError:
            raise
        except Exception as exc:
            log.exception("LLM stream call failed for provider {}", provider)
            raise LLMError(f"Provider {provider} error: {exc}") from exc

    def chat(self, messages: Iterable[ChatMessage], system_prompt: str = "") -> str:
        """Send a conversation history to the configured provider and return the full response."""
        chunks = []
        for chunk in self.chat_stream(messages, system_prompt):
            chunks.append(chunk)
        cleaned = clean_repetitive_patterns(_strip_thinking("".join(chunks)))
        return cleaned

    def _chat_groq_stream(self, messages: Iterable[ChatMessage], system_prompt: str) -> Generator[str, None, None]:
        """Ultra-fast streaming via Groq LPU API (<200ms latency) with automatic model fallback."""
        from openai import OpenAI
        import time

        global _GROQ_MODELS_CACHE, _GROQ_MODELS_CACHE_TIME

        api_key = get_api_key(self.config)
        if not api_key:
            raise LLMError(
                "No Groq API key found. Please open Settings to enter your free key from console.groq.com."
            )
        api_key = api_key.strip().strip('"\'')
        base_url = "https://api.groq.com/openai/v1"
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=40.0)

        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.extend([{"role": m.role, "content": m.content} for m in messages])

        # Discover or use cached live models
        now = time.time()
        if not _GROQ_MODELS_CACHE or (now - _GROQ_MODELS_CACHE_TIME > 600):
            try:
                _GROQ_MODELS_CACHE = [m.id for m in client.models.list().data]
                _GROQ_MODELS_CACHE_TIME = now
            except Exception as e:
                log.warning("Could not query Groq models list: {}", e)

        live_models = _GROQ_MODELS_CACHE

        current_model = (self.config.llm.model or "").strip()
        if "gemini" in current_model or not current_model:
            current_model = "qwen/qwen3.8-27b"
            self.config.llm.model = current_model

        candidate_models = []
        if live_models:
            if current_model in live_models:
                candidate_models.append(current_model)
            for m in GROQ_MODELS_PRIORITY:
                if m in live_models and m not in candidate_models:
                    candidate_models.append(m)
            for m in live_models:
                if m not in candidate_models and "whisper" not in m:
                    candidate_models.append(m)

        if not candidate_models:
            if current_model:
                candidate_models.append(current_model)
            for m in GROQ_MODELS_PRIORITY:
                if m not in candidate_models:
                    candidate_models.append(m)

        temp = getattr(self.config.llm, "temperature", 0.6)
        if temp < 0.4:
            temp = 0.6

        last_exc = None
        for mod_name in candidate_models:
            try:
                stream = client.chat.completions.create(
                    model=mod_name,
                    messages=chat_messages,
                    temperature=temp,
                    frequency_penalty=0.5,
                    presence_penalty=0.3,
                    top_p=0.9,
                    max_tokens=4096,
                    stream=True,
                )
                yielded_any = False
                recent_words: list[str] = []
                loop_broken = False

                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else ""
                    if delta:
                        # Repetition loop guard: detect if same token repeats >= 4 times consecutively
                        for tk in delta.strip().split():
                            recent_words.append(tk)
                            if len(recent_words) > 8:
                                recent_words.pop(0)
                            if len(recent_words) >= 4 and len(set(recent_words[-4:])) == 1:
                                log.warning("Repetition loop detected on token '{}', cutting stream.", tk)
                                loop_broken = True
                                break
                        if loop_broken:
                            break
                        yield delta
                        yielded_any = True
                if yielded_any:
                    if mod_name != self.config.llm.model:
                        self.config.llm.model = mod_name
                        try:
                            save_config(self.config)
                        except Exception:
                            pass
                    return
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if any(term in err_str for term in ["invalid_api_key", "unauthorized", "401", "forbidden"]):
                    raise LLMError(f"Invalid Groq API Key: {exc}") from exc
                
                # Auto-fallback on rate limits, model unavailability, timeouts, or 503
                log.warning("Groq model '{}' issue ({}), auto-falling back to next model...", mod_name, exc)
                continue

        raise last_exc or LLMError("Failed to generate content with available Groq models.")

    def _chat_anthropic_stream(self, messages: Iterable[ChatMessage], system_prompt: str) -> Generator[str, None, None]:
        """Streams text chunks from Anthropic Claude (Claude 3.7 Sonnet, Claude 3.5 Sonnet, Claude 3.5 Haiku)."""
        import anthropic

        api_key = get_api_key(self.config)
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise LLMError(
                "No Anthropic API key found. Please open Settings to enter your key or set ANTHROPIC_API_KEY in .env."
            )

        api_key = api_key.strip().strip('"\'')
        client = anthropic.Anthropic(api_key=api_key, timeout=45.0)

        chat_messages = []
        for m in messages:
            role = "assistant" if m.role == "assistant" else "user"
            chat_messages.append({"role": role, "content": m.content})

        if not chat_messages:
            chat_messages.append({"role": "user", "content": "Hello"})
        while chat_messages and chat_messages[0]["role"] == "assistant":
            chat_messages.pop(0)

        model = self.config.llm.model
        if not model or "claude" not in model.lower():
            model = "claude-3-7-sonnet-20250219"

        candidate_models = [
            model,
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ]
        seen = set()
        ordered_models = []
        for m in candidate_models:
            if m not in seen:
                seen.add(m)
                ordered_models.append(m)

        last_exc = None
        for mod_name in ordered_models:
            try:
                with client.messages.stream(
                    model=mod_name,
                    max_tokens=4096,
                    temperature=0.6,
                    system=system_prompt or "You are Claude, an AI by Anthropic.",
                    messages=chat_messages,
                ) as stream:
                    yielded_any = False
                    for text in stream.text_stream:
                        if text:
                            yield text
                            yielded_any = True
                    if yielded_any:
                        if mod_name != self.config.llm.model:
                            self.config.llm.model = mod_name
                            try:
                                save_config(self.config)
                            except Exception:
                                pass
                        return
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if any(k in err_str for k in ["invalid_api_key", "authentication_error", "401"]):
                    raise LLMError(f"Invalid Anthropic API Key: {exc}") from exc
                log.warning("Anthropic model '{}' error: {}, trying next...", mod_name, exc)
                continue

        raise last_exc or LLMError("Anthropic Claude generation failed.")

    def _chat_gemini_stream(self, messages: Iterable[ChatMessage], system_prompt: str) -> Generator[str, None, None]:
        import google.generativeai as genai

        api_key = get_api_key(self.config)
        if not api_key:
            raise LLMError("No Google Gemini API key found.")
        api_key = api_key.strip().strip('"\'')
        genai.configure(api_key=api_key)

        from PIL import Image
        raw_history = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            parts = []
            if m.content:
                parts.append(m.content)
            if m.image_path:
                try:
                    img = Image.open(m.image_path)
                    parts.append(img)
                except Exception as e:
                    log.warning("Could not open image for Gemini: {}", e)
            if not parts:
                parts.append("")
            raw_history.append({"role": role, "parts": parts})

        while raw_history and raw_history[0]["role"] == "model":
            raw_history.pop(0)

        history = []
        for turn in raw_history:
            if not history:
                history.append({"role": turn["role"], "parts": list(turn["parts"])})
            elif history[-1]["role"] == turn["role"]:
                history[-1]["parts"].extend(turn["parts"])
            else:
                history.append({"role": turn["role"], "parts": list(turn["parts"])})

        candidate_models = GEMINI_MODELS_PRIORITY
        gen_config = genai.types.GenerationConfig(temperature=0.2, max_output_tokens=4096)

        last_exc = None
        for mod_name in candidate_models:
            try:
                cur_model = genai.GenerativeModel(mod_name, system_instruction=system_prompt or None)
                resp_stream = cur_model.generate_content(history, generation_config=gen_config, stream=True)
                yielded_any = False
                for chunk in resp_stream:
                    if chunk.text:
                        yield chunk.text
                        yielded_any = True
                if yielded_any:
                    return
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if any(x in err_str for x in ["not found", "404", "no longer available", "deprecated"]):
                    continue
                raise

        raise last_exc or LLMError("Failed to generate content with available Gemini models.")

    def _chat_openai_stream(self, messages: Iterable[ChatMessage], system_prompt: str) -> Generator[str, None, None]:
        from openai import OpenAI

        api_key = get_api_key(self.config)
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise LLMError("No API key found for OpenAI. Please configure your key in Settings or set OPENAI_API_KEY in .env.")
        base_url = self.config.llm.openai_base_url or None
        client = OpenAI(api_key=api_key.strip(), base_url=base_url, timeout=40.0)

        model = self.config.llm.model
        if not model or not any(k in model.lower() for k in ["gpt", "o1", "o3", "chatgpt"]):
            model = "gpt-4o"

        candidate_models = [
            model,
            "gpt-4o",
            "gpt-4o-mini",
            "o3-mini",
            "o1-mini",
        ]
        seen = set()
        ordered_models = []
        for m in candidate_models:
            if m not in seen:
                seen.add(m)
                ordered_models.append(m)

        last_exc = None
        for mod_name in ordered_models:
            is_reasoning = any(mod_name.startswith(p) for p in ["o1", "o3"])
            chat_messages = []
            if system_prompt:
                role = "developer" if is_reasoning else "system"
                chat_messages.append({"role": role, "content": system_prompt})
            chat_messages.extend([{"role": m.role, "content": m.content} for m in messages])

            call_kwargs = {
                "model": mod_name,
                "messages": chat_messages,
                "stream": True,
            }
            if is_reasoning:
                call_kwargs["max_completion_tokens"] = 4096
            else:
                call_kwargs["max_tokens"] = 4096
                call_kwargs["temperature"] = 0.6

            try:
                stream = client.chat.completions.create(**call_kwargs)
                yielded_any = False
                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else ""
                    if delta:
                        yield delta
                        yielded_any = True
                if yielded_any:
                    if mod_name != self.config.llm.model:
                        self.config.llm.model = mod_name
                        try:
                            save_config(self.config)
                        except Exception:
                            pass
                    return
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if any(k in err_str for k in ["invalid_api_key", "incorrect api key", "authentication_error", "401"]):
                    raise LLMError(f"Invalid OpenAI API Key: {exc}") from exc
                log.warning("OpenAI model '{}' error: {}, trying next...", mod_name, exc)
                continue

        raise last_exc or LLMError("OpenAI generation failed across all candidate models.")

    def describe_screen(self, image_path: str, question: str, system_prompt: str = "") -> str:
        """Sends a screenshot to the vision model and returns the response."""
        from openai import OpenAI

        api_key = get_api_key(self.config)
        if not api_key:
            raise LLMError("No API key available for vision.")

        with open(image_path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        # Try Groq vision first
        if self.config.llm.provider == "groq":
            try:
                client = OpenAI(api_key=api_key.strip(), base_url="https://api.groq.com/openai/v1")
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                    ]
                })
                resp = client.chat.completions.create(
                    model="llama-3.2-11b-vision-preview",
                    messages=messages,
                    max_tokens=2000,
                )
                return _strip_thinking(resp.choices[0].message.content or "")
            except Exception as e:
                log.warning("Groq vision failed ({}), attempting fallback...", e)

        # Fallback to Gemini if configured
        try:
            import google.generativeai as genai
            from PIL import Image
            gemini_key = os.environ.get("GOOGLE_API_KEY")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                img = Image.open(image_path)
                m = genai.GenerativeModel("gemini-1.5-flash")
                res = m.generate_content([question, img])
                return _strip_thinking(res.text)
        except Exception:
            pass

        return "Screen analysis requires a Vision-supported model."
