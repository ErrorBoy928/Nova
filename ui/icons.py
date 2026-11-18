"""
ui/icons.py

High-DPI Vector Icon generator for the AI Assistant UI.
Provides crisp, modern, minimalist monochrome icons without any emojis.
"""

import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def create_mic_icon(color: str = "#e2e8f0", size: int = 24) -> QIcon:
    """Crisp modern microphone vector icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    # Mic capsule
    capsule = QRectF(size * 0.35, size * 0.15, size * 0.30, size * 0.45)
    p.drawRoundedRect(capsule, size * 0.15, size * 0.15)

    # Stand arc
    path = QPainterPath()
    path.arcMoveTo(QRectF(size * 0.22, size * 0.30, size * 0.56, size * 0.42), 0)
    path.arcTo(QRectF(size * 0.22, size * 0.30, size * 0.56, size * 0.42), 0, -180)
    p.drawPath(path)

    # Stem and base
    p.drawLine(QPointF(size * 0.5, size * 0.72), QPointF(size * 0.5, size * 0.86))
    p.drawLine(QPointF(size * 0.32, size * 0.86), QPointF(size * 0.68, size * 0.86))
    p.end()
    return QIcon(pm)


def create_speaker_icon(color: str = "#e2e8f0", size: int = 24) -> QIcon:
    """Crisp modern speaker vector icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    # Speaker cone
    path = QPainterPath()
    path.moveTo(size * 0.20, size * 0.38)
    path.lineTo(size * 0.34, size * 0.38)
    path.lineTo(size * 0.55, size * 0.22)
    path.lineTo(size * 0.55, size * 0.78)
    path.lineTo(size * 0.34, size * 0.62)
    path.lineTo(size * 0.20, size * 0.62)
    path.closeSubpath()
    p.drawPath(path)

    # Sound waves
    wave_path = QPainterPath()
    wave_path.arcMoveTo(QRectF(size * 0.45, size * 0.32, size * 0.32, size * 0.36), -50)
    wave_path.arcTo(QRectF(size * 0.45, size * 0.32, size * 0.32, size * 0.36), -50, 100)
    p.drawPath(wave_path)

    p.end()
    return QIcon(pm)


def create_screen_icon(color: str = "#e2e8f0", size: int = 24) -> QIcon:
    """Crisp computer monitor / screen observing icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    # Monitor outline
    screen_rect = QRectF(size * 0.15, size * 0.18, size * 0.70, size * 0.50)
    p.drawRoundedRect(screen_rect, 2, 2)

    # Eye pupil inside screen or clean dot
    p.drawPoint(QPointF(size * 0.5, size * 0.43))
    p.drawEllipse(QRectF(size * 0.42, size * 0.36, size * 0.16, size * 0.14))

    # Stand
    p.drawLine(QPointF(size * 0.5, size * 0.68), QPointF(size * 0.5, size * 0.82))
    p.drawLine(QPointF(size * 0.32, size * 0.82), QPointF(size * 0.68, size * 0.82))
    p.end()
    return QIcon(pm)


def create_snip_icon(color: str = "#e2e8f0", size: int = 24) -> QIcon:
    """Crisp crosshair / crop snip vector icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    # Corner brackets (Crop style)
    # Top-Left
    p.drawLine(QPointF(size * 0.20, size * 0.38), QPointF(size * 0.20, size * 0.20))
    p.drawLine(QPointF(size * 0.20, size * 0.20), QPointF(size * 0.38, size * 0.20))

    # Top-Right
    p.drawLine(QPointF(size * 0.62, size * 0.20), QPointF(size * 0.80, size * 0.20))
    p.drawLine(QPointF(size * 0.80, size * 0.20), QPointF(size * 0.80, size * 0.38))

    # Bottom-Left
    p.drawLine(QPointF(size * 0.20, size * 0.62), QPointF(size * 0.20, size * 0.80))
    p.drawLine(QPointF(size * 0.20, size * 0.80), QPointF(size * 0.38, size * 0.80))

    # Bottom-Right
    p.drawLine(QPointF(size * 0.62, size * 0.80), QPointF(size * 0.80, size * 0.80))
    p.drawLine(QPointF(size * 0.80, size * 0.80), QPointF(size * 0.80, size * 0.62))

    # Center dot
    p.drawEllipse(QRectF(size * 0.45, size * 0.45, size * 0.10, size * 0.10))
    p.end()
    return QIcon(pm)


def create_gear_icon(color: str = "#e2e8f0", size: int = 24) -> QIcon:
    """Crisp settings gear vector icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    cx, cy = size * 0.5, size * 0.5
    # Inner circle
    p.drawEllipse(QRectF(cx - size * 0.18, cy - size * 0.18, size * 0.36, size * 0.36))

    # Outer teeth (clean 6 notches)
    for i in range(6):
        angle = i * (math.pi / 3)
        x1 = cx + math.cos(angle) * (size * 0.26)
        y1 = cy + math.sin(angle) * (size * 0.26)
        x2 = cx + math.cos(angle) * (size * 0.40)
        y2 = cy + math.sin(angle) * (size * 0.40)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    p.end()
    return QIcon(pm)


def create_send_icon(color: str = "#ffffff", size: int = 24) -> QIcon:
    """Crisp send arrow vector icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    path = QPainterPath()
    path.moveTo(size * 0.22, size * 0.78)
    path.lineTo(size * 0.82, size * 0.50)
    path.lineTo(size * 0.22, size * 0.22)
    path.lineTo(size * 0.38, size * 0.50)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def create_attach_icon(color: str = "#e2e8f0", size: int = 24) -> QIcon:
    """Crisp paperclip vector icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    path = QPainterPath()
    path.moveTo(size * 0.50, size * 0.32)
    path.lineTo(size * 0.32, size * 0.50)
    path.arcTo(QRectF(size * 0.22, size * 0.50, size * 0.32, size * 0.32), 180, -180)
    path.lineTo(size * 0.65, size * 0.35)
    path.arcTo(QRectF(size * 0.45, size * 0.15, size * 0.36, size * 0.36), 0, 180)
    path.lineTo(size * 0.40, size * 0.60)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def create_copy_icon(color: str = "#94a3b8", size: int = 24) -> QIcon:
    """Crisp double-square copy icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    # Back square
    p.drawRoundedRect(QRectF(size * 0.35, size * 0.18, size * 0.48, size * 0.52), 2, 2)
    # Front square
    p.setBrush(QColor("#101014"))
    p.drawRoundedRect(QRectF(size * 0.18, size * 0.32, size * 0.48, size * 0.52), 2, 2)
    p.end()
    return QIcon(pm)


def create_clean_icon(color: str = "#38bdf8", size: int = 24) -> QIcon:
    """Crisp sparkle / cleanup icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    cx, cy = size * 0.5, size * 0.5
    path = QPainterPath()
    path.moveTo(cx, cy - size * 0.38)
    path.quadTo(cx, cy, cx + size * 0.38, cy)
    path.quadTo(cx, cy, cx, cy + size * 0.38)
    path.quadTo(cx, cy, cx - size * 0.38, cy)
    path.quadTo(cx, cy, cx, cy - size * 0.38)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def create_health_icon(color: str = "#10b981", size: int = 24) -> QIcon:
    """Crisp pulse / health telemetry icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    path = QPainterPath()
    path.moveTo(size * 0.15, size * 0.52)
    path.lineTo(size * 0.32, size * 0.52)
    path.lineTo(size * 0.42, size * 0.24)
    path.lineTo(size * 0.58, size * 0.78)
    path.lineTo(size * 0.68, size * 0.52)
    path.lineTo(size * 0.85, size * 0.52)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def create_moon_icon(color: str = "#a78bfa", size: int = 24) -> QIcon:
    """Crisp crescent moon / night mode icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    path = QPainterPath()
    path.moveTo(size * 0.65, size * 0.20)
    path.cubicTo(size * 0.30, size * 0.25, size * 0.30, size * 0.75, size * 0.65, size * 0.80)
    path.cubicTo(size * 0.48, size * 0.68, size * 0.48, size * 0.32, size * 0.65, size * 0.20)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def create_music_icon(color: str = "#f472b6", size: int = 24) -> QIcon:
    """Crisp musical note / relax icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    p.drawEllipse(QRectF(size * 0.22, size * 0.60, size * 0.22, size * 0.18))
    p.drawLine(QPointF(size * 0.44, size * 0.68), QPointF(size * 0.44, size * 0.24))
    path = QPainterPath()
    path.moveTo(size * 0.44, size * 0.24)
    path.cubicTo(size * 0.65, size * 0.24, size * 0.70, size * 0.38, size * 0.72, size * 0.44)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def create_work_icon(color: str = "#60a5fa", size: int = 24) -> QIcon:
    """Crisp workspace / focus icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    p.drawRoundedRect(QRectF(size * 0.18, size * 0.20, size * 0.64, size * 0.50), 3, 3)
    p.drawLine(QPointF(size * 0.18, size * 0.34), QPointF(size * 0.82, size * 0.34))
    p.drawLine(QPointF(size * 0.12, size * 0.78), QPointF(size * 0.88, size * 0.78))
    p.end()
    return QIcon(pm)
