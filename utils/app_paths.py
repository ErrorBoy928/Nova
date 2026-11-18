r"""
utils/app_paths.py

Resolves data folders on Drive E: (E:\AI_Assistant\data)
so that logs, config, and database never fill up drive C:.
"""

from __future__ import annotations

from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _BASE_DIR / "data"


def user_data_dir() -> Path:
    """Returns the writable per-user data directory inside E:\\AI_Assistant\\data."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR


def project_root() -> Path:
    """Returns the root directory of the application on drive E:."""
    return _BASE_DIR
