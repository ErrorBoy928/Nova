"""
package_payload.py

Compresses dist/Nova_AI/ into installer/payload.zip for embedding into the setup installer wizard.
"""

import os
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DIST_APP = ROOT_DIR / "dist" / "Nova_AI"
PAYLOAD_ZIP = ROOT_DIR / "installer" / "payload.zip"

def main():
    if not DIST_APP.exists():
        print(f"[ERROR] {DIST_APP} does not exist. Run build_standalone.py first.")
        sys.exit(1)

    PAYLOAD_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if PAYLOAD_ZIP.exists():
        PAYLOAD_ZIP.unlink()

    print(f"Compressing {DIST_APP} -> {PAYLOAD_ZIP} ...")
    total_files = 0
    with zipfile.ZipFile(PAYLOAD_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(DIST_APP):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(DIST_APP)
                zf.write(full_path, arcname=str(rel_path))
                total_files += 1

    size_mb = PAYLOAD_ZIP.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Packaged {total_files} files into {PAYLOAD_ZIP} ({size_mb:.1f} MB)")

if __name__ == "__main__":
    main()
