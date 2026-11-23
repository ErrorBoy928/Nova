"""
installer/setup_wizard.py

Professional, Modern Setup Wizard for Nova AI Desktop Assistant.
Features:
- Pure OLED Dark Black theme matching the Nova AI Assistant design.
- Folder picker (defaults to E:\\AI_Assistant).
- Desktop Shortcut, Start Menu Shortcut, and Windows Auto-start registration.
- Directory and memory database setup.
- Headless launcher creation.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# Root directory of source files
_SOURCE_DIR = Path(__file__).resolve().parent.parent

# OLED Deep Black Styling
_BG_BLACK = "#000000"
_BG_PANEL = "#0a0a0a"
_BG_CARD = "#121212"
_BORDER = "#1f1f1f"
_ACCENT_BLUE = "#2563eb"
_ACCENT_CYAN = "#38bdf8"
_ACCENT_GREEN = "#10b981"
_TEXT_MAIN = "#f8fafc"
_TEXT_MUTED = "#94a3b8"


def _create_setup_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Dark background circle
    painter.setBrush(QColor("#0a0a0a"))
    painter.setPen(QColor("#1e3a8a"))
    painter.drawEllipse(3, 3, 58, 58)

    # Inner cyan accent ring
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QColor("#38bdf8"))
    painter.drawEllipse(8, 8, 48, 48)

    # Monogram "N"
    painter.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI", 22, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "N")
    painter.end()

    return QIcon(pixmap)


def create_windows_shortcut(
    target_path: str,
    shortcut_path: str,
    arguments: str = "",
    working_dir: str = "",
    icon_path: str = "shell32.dll,14",
    description: str = "Nova AI Desktop Assistant",
) -> bool:
    """Creates a Windows .lnk shortcut using WScript.Shell COM object."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target_path
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = working_dir
        if icon_path:
            shortcut.IconLocation = icon_path
        shortcut.Description = description
        shortcut.save()
        return True
    except Exception:
        # Fallback to PowerShell script
        import subprocess
        ps = f'''
        $ws = New-Object -ComObject WScript.Shell
        $s = $ws.CreateShortcut("{shortcut_path}")
        $s.TargetPath = "{target_path}"
        $s.Arguments = "{arguments}"
        $s.WorkingDirectory = "{working_dir}"
        $s.IconLocation = "{icon_path}"
        $s.Description = "{description}"
        $s.Save()
        '''
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
        return res.returncode == 0


class InstallWorker(QThread):
    progress_changed = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, target_dir: str, create_desktop: bool, create_start_menu: bool, auto_start: bool):
        super().__init__()
        self.target_dir = Path(target_dir)
        self.create_desktop = create_desktop
        self.create_start_menu = create_start_menu
        self.auto_start = auto_start

    def run(self):
        try:
            self.progress_changed.emit(10, "Verifying target directory...")
            time.sleep(0.3)
            self.target_dir.mkdir(parents=True, exist_ok=True)

            # Ensure data subdirectories
            for sub in ["data", "data/database", "data/logs", "data/temp", "data/temp_audio", "installer"]:
                (self.target_dir / sub).mkdir(parents=True, exist_ok=True)

            self.progress_changed.emit(25, "Synchronizing application modules...")
            time.sleep(0.3)

            # Core files and folders to ensure in target
            core_folders = ["ai", "automation", "config", "memory", "ui", "utils", "voice", "installer"]
            for f in core_folders:
                src_path = _SOURCE_DIR / f
                dst_path = self.target_dir / f
                if src_path.exists() and src_path.resolve() != dst_path.resolve():
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

            # Core files
            for fname in ["main.py", ".env", "requirements.txt", "README.md"]:
                src_file = _SOURCE_DIR / fname
                dst_file = self.target_dir / fname
                if src_file.exists() and src_file.resolve() != dst_file.resolve():
                    shutil.copy2(src_file, dst_file)

            self.progress_changed.emit(50, "Generating headless Windows launcher...")
            time.sleep(0.3)

            # Find pythonw.exe
            pythonw_candidates = [
                r"E:\python\pythonw.exe",
                shutil.which("pythonw.exe"),
                Path(sys.executable).parent / "pythonw.exe",
            ]
            pythonw_path = None
            for cand in pythonw_candidates:
                if cand and Path(cand).exists():
                    pythonw_path = str(Path(cand).resolve())
                    break

            if not pythonw_path:
                pythonw_path = sys.executable

            # Generate AI_Assistant.vbs in target
            vbs_file = self.target_dir / "AI_Assistant.vbs"
            vbs_content = f'CreateObject("Wscript.Shell").Run """{pythonw_path}"" """{self.target_dir / "main.py"}""", 0, False\n'
            vbs_file.write_text(vbs_content, encoding="utf-8")

            # Generate run.bat
            bat_file = self.target_dir / "run.bat"
            bat_content = f'@echo off\nstart "" "{pythonw_path}" "{self.target_dir / "main.py"}"\n'
            bat_file.write_text(bat_content, encoding="utf-8")

            self.progress_changed.emit(75, "Registering Windows shortcuts & system entries...")
            time.sleep(0.3)

            # Desktop Shortcut
            if self.create_desktop:
                desktop_dir = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
                if desktop_dir.exists():
                    create_windows_shortcut(
                        target_path=pythonw_path,
                        shortcut_path=str(desktop_dir / "Nova AI Assistant.lnk"),
                        arguments=f'"{self.target_dir / "main.py"}"',
                        working_dir=str(self.target_dir),
                        icon_path="shell32.dll,14",
                        description="Nova AI Desktop Assistant"
                    )

            # Start Menu Shortcut
            if self.create_start_menu:
                start_menu_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                if start_menu_dir.exists():
                    create_windows_shortcut(
                        target_path=pythonw_path,
                        shortcut_path=str(start_menu_dir / "Nova AI Assistant.lnk"),
                        arguments=f'"{self.target_dir / "main.py"}"',
                        working_dir=str(self.target_dir),
                        icon_path="shell32.dll,14",
                        description="Nova AI Desktop Assistant"
                    )

            # Auto Start on Windows boot
            if self.auto_start:
                startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
                if startup_dir.exists():
                    create_windows_shortcut(
                        target_path=pythonw_path,
                        shortcut_path=str(startup_dir / "Nova AI Assistant.lnk"),
                        arguments=f'"{self.target_dir / "main.py"}"',
                        working_dir=str(self.target_dir),
                        icon_path="shell32.dll,14",
                        description="Nova AI Desktop Assistant (Startup)"
                    )

            # Create uninstaller script
            uninstaller_bat = self.target_dir / "installer" / "uninstall.bat"
            uninstaller_content = f'''@echo off
echo ===================================================
echo     Uninstalling Nova AI Desktop Assistant
echo ===================================================
echo Removing Desktop shortcut...
del /f /q "%USERPROFILE%\\Desktop\\Nova AI Assistant.lnk" >nul 2>&1
echo Removing Start Menu shortcut...
del /f /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Nova AI Assistant.lnk" >nul 2>&1
echo Removing Startup shortcut...
del /f /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\Nova AI Assistant.lnk" >nul 2>&1
echo.
echo Shortcuts removed successfully!
echo The project folder at {self.target_dir} is preserved.
echo To delete all data, you can delete this folder manually.
pause
'''
            uninstaller_bat.write_text(uninstaller_content, encoding="utf-8")

            self.progress_changed.emit(100, "Setup finalized successfully!")
            time.sleep(0.4)
            self.finished.emit(True, "Installation completed successfully.")
        except Exception as exc:
            self.finished.emit(False, str(exc))


class SetupWizardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nova AI Assistant Setup")
        self.resize(520, 480)
        self.setWindowIcon(_create_setup_icon())
        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {_BG_BLACK};
                color: {_TEXT_MAIN};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            QFrame#card {{
                background-color: {_BG_PANEL};
                border: 1px solid {_BORDER};
                border-radius: 8px;
            }}
            QLineEdit {{
                background-color: {_BG_CARD};
                color: {_TEXT_MAIN};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {_ACCENT_CYAN};
            }}
            QCheckBox {{
                color: {_TEXT_MAIN};
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {_BORDER};
                border-radius: 3px;
                background: {_BG_CARD};
            }}
            QCheckBox::indicator:checked {{
                background: {_ACCENT_BLUE};
                border-color: {_ACCENT_CYAN};
            }}
            QPushButton#primary {{
                background-color: {_ACCENT_BLUE};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                padding: 8px 18px;
                font-size: 12px;
            }}
            QPushButton#primary:hover {{
                background-color: #1d4ed8;
            }}
            QPushButton#secondary {{
                background-color: {_BG_CARD};
                color: {_TEXT_MUTED};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }}
            QPushButton#secondary:hover {{
                color: white;
                border-color: {_BORDER};
            }}
            QProgressBar {{
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                height: 10px;
                text-align: center;
                font-size: 10px;
            }}
            QProgressBar::chunk {{
                background-color: {_ACCENT_CYAN};
                border-radius: 3px;
            }}
        """)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # Header Banner
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(_create_setup_icon().pixmap(48, 48))
        header.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("NOVA AI ASSISTANT")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; letter-spacing: 0.5px; color: #ffffff;")
        sub_lbl = QLabel("Professional Windows Desktop AI Assistant • Setup Wizard")
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {_TEXT_MUTED};")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)
        header.addStretch()

        root.addLayout(header)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {_BORDER};")
        root.addWidget(sep)

        # Stack Pages
        self.stack = QStackedWidget()

        # Page 0: Configuration
        p0 = QWidget()
        p0_layout = QVBoxLayout(p0)
        p0_layout.setContentsMargins(0, 4, 0, 0)
        p0_layout.setSpacing(12)

        desc = QLabel(
            "This installer will configure Nova AI Assistant on your computer with:\n"
            "• Continuous Hands-Free Voice Conversation (Urdu & English)\n"
            "• Real-Time Multimodal Screen Observation\n"
            "• Full Computer Control & Safe Decision Rechecking\n"
            "• Direct desktop shortcut with zero command prompt window"
        )
        desc.setStyleSheet(f"color: #cbd5e1; font-size: 12px; line-height: 1.5;")
        p0_layout.addWidget(desc)

        # Install Directory
        card_dir = QFrame()
        card_dir.setObjectName("card")
        card_dir_l = QVBoxLayout(card_dir)
        card_dir_l.setContentsMargins(12, 10, 12, 10)
        card_dir_l.setSpacing(6)

        dir_lbl = QLabel("Installation Directory (Drive E: Recommended):")
        dir_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #e2e8f0;")
        card_dir_l.addWidget(dir_lbl)

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(str(_SOURCE_DIR if str(_SOURCE_DIR).startswith("E:") else Path("E:/AI_Assistant")))
        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("secondary")
        browse_btn.setFixedHeight(30)
        browse_btn.clicked.connect(self._browse_folder)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(browse_btn)
        card_dir_l.addLayout(dir_row)
        p0_layout.addWidget(card_dir)

        # Options Card
        card_opt = QFrame()
        card_opt.setObjectName("card")
        card_opt_l = QVBoxLayout(card_opt)
        card_opt_l.setContentsMargins(12, 10, 12, 10)
        card_opt_l.setSpacing(8)

        opt_lbl = QLabel("Shortcut & Startup Options:")
        opt_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #e2e8f0;")
        card_opt_l.addWidget(opt_lbl)

        self.chk_desktop = QCheckBox("Create Desktop Shortcut (Nova AI Assistant)")
        self.chk_desktop.setChecked(True)
        card_opt_l.addWidget(self.chk_desktop)

        self.chk_start_menu = QCheckBox("Create Start Menu Entry")
        self.chk_start_menu.setChecked(True)
        card_opt_l.addWidget(self.chk_start_menu)

        self.chk_startup = QCheckBox("Launch Nova AI Assistant automatically when Windows boots")
        self.chk_startup.setChecked(False)
        card_opt_l.addWidget(self.chk_startup)

        p0_layout.addWidget(card_opt)
        p0_layout.addStretch()

        self.stack.addWidget(p0)

        # Page 1: Progress
        p1 = QWidget()
        p1_l = QVBoxLayout(p1)
        p1_l.setContentsMargins(0, 20, 0, 0)
        p1_l.setSpacing(14)

        installing_lbl = QLabel("Installing Nova AI Assistant...")
        installing_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        p1_l.addWidget(installing_lbl)

        self.status_msg = QLabel("Preparing setup...")
        self.status_msg.setStyleSheet(f"font-size: 12px; color: {_ACCENT_CYAN};")
        p1_l.addWidget(self.status_msg)

        self.bar = QProgressBar()
        self.bar.setValue(0)
        p1_l.addWidget(self.bar)
        p1_l.addStretch()

        self.stack.addWidget(p1)

        # Page 2: Finish
        p2 = QWidget()
        p2_l = QVBoxLayout(p2)
        p2_l.setContentsMargins(0, 10, 0, 0)
        p2_l.setSpacing(12)

        success_title = QLabel("Installation Completed Successfully!")
        success_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {_ACCENT_GREEN};")
        p2_l.addWidget(success_title)

        self.finish_details = QLabel(
            "Nova AI Assistant is fully installed and configured on your PC.\n"
            "You can launch it anytime from your Desktop or Start Menu."
        )
        self.finish_details.setStyleSheet("font-size: 12px; color: #cbd5e1; line-height: 1.5;")
        p2_l.addWidget(self.finish_details)

        self.chk_launch = QCheckBox("Launch Nova AI Assistant now")
        self.chk_launch.setChecked(True)
        p2_l.addWidget(self.chk_launch)
        p2_l.addStretch()

        self.stack.addWidget(p2)

        root.addWidget(self.stack, 1)

        # Bottom Navigation Buttons
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.close)
        btn_bar.addWidget(self.cancel_btn)

        self.action_btn = QPushButton("Install Now")
        self.action_btn.setObjectName("primary")
        self.action_btn.clicked.connect(self._on_action_clicked)
        btn_bar.addWidget(self.action_btn)

        root.addLayout(btn_bar)

    def _browse_folder(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Installation Folder", self.dir_edit.text())
        if chosen:
            self.dir_edit.setText(chosen)

    def _on_action_clicked(self):
        curr = self.stack.currentIndex()
        if curr == 0:
            target_path = self.dir_edit.text().strip()
            if not target_path:
                return

            self.stack.setCurrentIndex(1)
            self.cancel_btn.setEnabled(False)
            self.action_btn.setEnabled(False)

            self.worker = InstallWorker(
                target_dir=target_path,
                create_desktop=self.chk_desktop.isChecked(),
                create_start_menu=self.chk_start_menu.isChecked(),
                auto_start=self.chk_startup.isChecked(),
            )
            self.worker.progress_changed.connect(self._on_progress)
            self.worker.finished.connect(self._on_finished)
            self.worker.start()
        elif curr == 2:
            # Finish clicked
            if self.chk_launch.isChecked():
                self._launch_app()
            self.close()

    def _on_progress(self, val: int, text: str):
        self.bar.setValue(val)
        self.status_msg.setText(text)

    def _on_finished(self, success: bool, message: str):
        self.stack.setCurrentIndex(2)
        self.cancel_btn.setVisible(False)
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Finish")
        if not success:
            self.finish_details.setText(f"Installation encountered an issue:\n{message}")
            self.chk_launch.setVisible(False)

    def _launch_app(self):
        target_dir = Path(self.dir_edit.text().strip())
        launcher = target_dir / "AI_Assistant.vbs"
        if launcher.exists():
            import subprocess
            subprocess.Popen(["wscript.exe", str(launcher)], cwd=str(target_dir))


def main():
    app = QApplication(sys.argv)
    wizard = SetupWizardWindow()
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
