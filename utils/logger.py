"""
utils/logger.py

Single place that configures logging for the entire application.
Logs are written to E:\\AI_Assistant\\data\\logs\\assistant.log.
"""

from __future__ import annotations

import sys
from loguru import logger
from utils.app_paths import user_data_dir

LOG_DIR = user_data_dir() / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return

    logger.remove()

    if sys.stderr is not None:
        logger.add(
            sys.stderr,
            level="INFO",
            colorize=True,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan> - <level>{message}</level>",
        )
    logger.add(
        LOG_DIR / "assistant.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
    )
    _configured = True


def get_logger(name: str):
    """Return a logger bound with the calling module's name."""
    _configure()
    return logger.bind(module=name)
