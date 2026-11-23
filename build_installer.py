"""
build_installer.py

Packages the standalone Nova AI installer into a single, self-extracting
Windows Setup Wizard executable: dist/Nova_AI_Setup.exe.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build_installer"
PAYLOAD_ZIP = ROOT_DIR / "installer" / "payload.zip"
WIZARD_SCRIPT = ROOT_DIR / "installer" / "setup_wizard.py"

def build():
    if not PAYLOAD_ZIP.exists():
        print(f"[ERROR] payload.zip not found at {PAYLOAD_ZIP}. Run package_payload first!")
        sys.exit(1)

    print("=== Building Single-File Nova_AI_Setup.exe ===")
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "Nova_AI_Setup",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--add-data", f"{PAYLOAD_ZIP};.",
        "--exclude-module", "torch",
        "--exclude-module", "pyarrow",
        "--exclude-module", "googleapiclient",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "sympy",
        "--exclude-module", "matplotlib",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "win32com",
        "--hidden-import", "win32com.client",
        str(WIZARD_SCRIPT)
    ]

    print("Command:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        print(f"[FAIL] PyInstaller failed with code {res.returncode}")
        sys.exit(res.returncode)

    setup_exe = DIST_DIR / "Nova_AI_Setup.exe"
    print(f"\n[SUCCESS] Single-File Installer built at: {setup_exe}")

    # Copy to Desktop
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    if desktop.exists():
        desktop_setup = desktop / "Nova_AI_Setup.exe"
        print(f"Copying installer to Desktop: {desktop_setup} ...")
        shutil.copy2(setup_exe, desktop_setup)
        print(f"[SUCCESS] Installer is ready on Desktop: {desktop_setup}")

if __name__ == "__main__":
    build()
