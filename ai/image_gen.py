"""
ai/image_gen.py

Free text-to-image generation via Pollinations.ai.
Saves images inside E:\\AI_Assistant\\data\\temp.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from pathlib import Path
import requests

from utils.app_paths import user_data_dir
from utils.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://image.pollinations.ai/prompt/"


def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> Path:
    """Generates an image from a text prompt and returns the saved file path."""
    encoded_prompt = urllib.parse.quote(prompt.strip())
    seed = int(time.time() * 1000) % 1_000_000
    url = f"{_BASE_URL}{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true"

    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.exception("Image generation request failed")
        raise RuntimeError(f"Could not reach image generator: {exc}") from exc

    if not resp.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError("Image generator returned non-image content.")

    temp_dir = user_data_dir() / "generated_images"
    temp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", prompt)[:30] or "image"
    path = temp_dir / f"gen_{safe_name}_{seed}.png"
    path.write_bytes(resp.content)
    log.info("Generated image saved to: {}", path)
    return path
