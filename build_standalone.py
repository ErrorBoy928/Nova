"""
build_standalone.py

Automates PyInstaller standalone executable generation for Nova AI.
Produces a self-contained, no-python-required application in dist/Nova_AI/.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
APP_DIR = DIST_DIR / "Nova_AI"

def run_build():
    print("=== Step 1: Running PyInstaller ===")
    pyinstaller_cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name", "Nova_AI",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--exclude-module", "torch",
        "--exclude-module", "pyarrow",
        "--exclude-module", "googleapiclient",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "sympy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "IPython",
        "--exclude-module", "notebook",
        "--hidden-import", "groq",
        "--hidden-import", "dotenv",
        "--hidden-import", "loguru",
        "--hidden-import", "sqlite3",
        "--hidden-import", "win32com",
        "--hidden-import", "win32com.client",
        "--hidden-import", "comtypes",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        str(ROOT_DIR / "main.py")
    ]
    
    print("Executing command:", " ".join(pyinstaller_cmd))
    res = subprocess.run(pyinstaller_cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        print(f"PyInstaller failed with return code {res.returncode}")
        sys.exit(res.returncode)

    print("\n=== Step 2: Synchronizing Resource Folders ===")
    # Copy essential resource folders into dist/Nova_AI/
    resources_to_copy = ["skills", "config"]
    for res_name in resources_to_copy:
        src = ROOT_DIR / res_name
        dst = APP_DIR / res_name
        if src.exists():
            print(f"Copying {res_name} -> {dst}")
            shutil.copytree(src, dst, dirs_exist_ok=True)

    # Ensure data subdirectories exist
    data_dir = APP_DIR / "data"
    for sub in ["database", "logs", "temp", "temp_audio"]:
        (data_dir / sub).mkdir(parents=True, exist_ok=True)

    # Copy template .env or clean .env
    env_dst = APP_DIR / ".env"
    if not env_dst.exists():
        env_content = """# Nova AI Environment Configuration
GROQ_API_KEY=
NOVA_MODEL=qwen/qwen3.8-27b
"""
        env_dst.write_text(env_content, encoding="utf-8")
        print("Generated clean .env template in dist/Nova_AI/.env")

    print(f"\n[SUCCESS] Standalone binary created at: {APP_DIR / 'Nova_AI.exe'}")

if __name__ == "__main__":
    run_build()
