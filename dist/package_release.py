"""
dist/package_release.py

Packages the complete, clean Windows distribution for Nova AI - Groq Coding Edition.
Generates:
    dist/Nova_AI_Groq_Edition_Setup.zip
and copies it to Desktop for convenient access.
Safe, clean, transparent installer with zero antivirus false positives.
"""

import os
import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
DIST_DIR.mkdir(parents=True, exist_ok=True)

ZIP_PATH = DIST_DIR / "Nova_AI_Groq_Edition_Setup.zip"

INCLUDE_DIRS = [
    "ai",
    "automation",
    "config",
    "installer",
    "memory",
    "ui",
    "utils",
    "voice",
]

INCLUDE_ROOT_FILES = [
    "main.py",
    "requirements.txt",
    "Install_Nova_AI.bat",
    "Run_Nova_AI.bat",
    "Run_Nova_AI_Background.vbs",
    "README.md",
    ".env",
    "data/user_config.json",
]


def create_setup_zip():
    print(f"Creating Windows Setup Zip: {ZIP_PATH} ...")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    file_count = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in INCLUDE_ROOT_FILES:
            fpath = PROJECT_ROOT / fname
            if fpath.exists():
                zf.write(fpath, arcname=f"Nova_AI/{fname}")
                file_count += 1
                print(f"  + Nova_AI/{fname}")

        for folder in INCLUDE_DIRS:
            dir_path = PROJECT_ROOT / folder
            if not dir_path.exists():
                continue
            for root, dirs, files in os.walk(dir_path):
                dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
                for f in files:
                    if f.endswith(".pyc") or f.endswith(".tmp") or f.startswith("."):
                        continue
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(PROJECT_ROOT)
                    zf.write(full_p, arcname=f"Nova_AI/{rel_p.as_posix()}")
                    file_count += 1

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"\n[OK] Release Zip created successfully! {file_count} files ({size_mb:.2f} MB)")
    print(f"Location: {ZIP_PATH}")

    # Copy to Desktop
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    if desktop.exists():
        desktop_zip = desktop / "Nova_AI_Groq_Edition_Setup.zip"
        shutil.copy2(ZIP_PATH, desktop_zip)
        print(f"[OK] Copied installer package to Desktop: {desktop_zip}")


if __name__ == "__main__":
    create_setup_zip()
