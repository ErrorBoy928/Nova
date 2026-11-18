"""
ui/snipping_widget.py

Full-screen desktop overlay to select and crop a screen region for AI analysis.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal, QPoint
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from utils.app_paths import user_data_dir
from utils.logger import get_logger

log = get_logger(__name__)


class SnippingWidget(QWidget):
    snipped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setCursor(Qt.CrossCursor)
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting = False

    def start_snip(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting = False
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        log.info("Snipping overlay started.")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.start_pos = event.position().toPoint()
            self.end_pos = self.start_pos
            self.is_selecting = True
            self.update()
        elif event.button() == Qt.RightButton:
            self.hide()

    def mouseMoveEvent(self, event) -> None:
        if self.is_selecting:
            self.end_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.hide()
            rect = QRect(self.start_pos, self.end_pos).normalized()
            if rect.width() > 10 and rect.height() > 10:
                screen = QGuiApplication.primaryScreen()
                if screen:
                    pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
                    temp_dir = user_data_dir() / "temp"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    save_path = temp_dir / "snip_capture.png"
                    if pixmap.save(str(save_path)):
                        self.snipped.emit(str(save_path))

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))
        if self.is_selecting or (self.start_pos != self.end_pos):
            rect = QRect(self.start_pos, self.end_pos).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#ff6b00"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
