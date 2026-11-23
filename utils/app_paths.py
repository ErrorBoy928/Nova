r"""
utils/app_paths.py

Resolves root and data folders with automatic frozen (PyInstaller) detection
so that database, config, and skills work seamlessly in both dev and standalone modes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).resolve().parent
else:
    _BASE_DIR = Path(__file__).resolve().parent.parent

_DATA_DIR = _BASE_DIR / "data"


def project_root() -> Path:
    """Returns the root directory of the application."""
    return _BASE_DIR


def user_data_dir() -> Path:
    """Returns the writable per-user data directory."""
    local_data = _BASE_DIR / "data"
    try:
        local_data.mkdir(parents=True, exist_ok=True)
        # Test writability
        test_file = local_data / ".write_test"
        test_file.touch()
        test_file.unlink()
        return local_data
    except Exception:
        app_data = Path(os.environ.get("APPDATA", "")) / "Nova_AI" / "data"
        app_data.mkdir(parents=True, exist_ok=True)
        return app_data

