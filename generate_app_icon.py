"""
generate_app_icon.py

Generates the official high-resolution, multi-size Windows icon (.ico)
and high-DPI PNG for Nova AI and the Nova AI Setup Wizard.
"""

import os
import sys
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication

def create_nova_icon(output_ico: Path, output_png: Path, size: int = 256):
    app = QApplication.instance() or QApplication(sys.argv)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setRenderHint(QPainter.TextAntialiasing)

    # 1. Outer Dark Glow / Drop Shadow
    center = size / 2.0
    radius = (size - 16) / 2.0

    outer_glow = QRadialGradient(center, center, radius + 8)
    outer_glow.setColorAt(0.7, QColor(56, 189, 248, 60))
    outer_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setBrush(QBrush(outer_glow))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(0, 0, size, size))

    # 2. Main Obsidian Badge Background
    bg_grad = QLinearGradient(0, 0, size, size)
    bg_grad.setColorAt(0.0, QColor("#090d16"))
    bg_grad.setColorAt(0.5, QColor("#030712"))
    bg_grad.setColorAt(1.0, QColor("#080a14"))
    p.setBrush(QBrush(bg_grad))

    # Outer Neon Gradient Border (Cyan to Deep Azure to Electric Violet)
    border_pen = QPen()
    border_pen.setWidthF(7.0)
    border_grad = QLinearGradient(0, 0, size, size)
    border_grad.setColorAt(0.0, QColor("#38bdf8"))
    border_grad.setColorAt(0.5, QColor("#2563eb"))
    border_grad.setColorAt(1.0, QColor("#8b5cf6"))
    border_pen.setBrush(QBrush(border_grad))
    p.setPen(border_pen)
    p.drawEllipse(QRectF(10, 10, size - 20, size - 20))

    # 3. Inner Accent Precision Ring
    inner_pen = QPen(QColor(56, 189, 248, 120), 2.0, Qt.DashLine)
    p.setPen(inner_pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(22, 22, size - 44, size - 44))

    # 4. Orbital Micro-Sparkles (North, South, East, West)
    sparkle_pen = QPen(QColor("#ffffff"), 1.0)
    sparkle_brush = QBrush(QColor("#38bdf8"))
    p.setPen(sparkle_pen)
    p.setBrush(sparkle_brush)
    dot_r = 3.5
    p.drawEllipse(QPointF(center, 10), dot_r, dot_r)
    p.drawEllipse(QPointF(center, size - 10), dot_r, dot_r)
    p.drawEllipse(QPointF(10, center), dot_r, dot_r)
    p.drawEllipse(QPointF(size - 10, center), dot_r, dot_r)

    # 5. Bold High-Tech Stylized "N" Monogram
    p.setPen(Qt.NoPen)
    n_grad = QLinearGradient(center, 40, center, size - 40)
    n_grad.setColorAt(0.0, QColor("#ffffff"))
    n_grad.setColorAt(0.4, QColor("#e0f2fe"))
    n_grad.setColorAt(0.8, QColor("#38bdf8"))
    n_grad.setColorAt(1.0, QColor("#0284c7"))
    p.setBrush(QBrush(n_grad))

    font = QFont("Segoe UI", 124, QFont.Bold)
    font.setStyleStrategy(QFont.PreferAntialias)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 1)
    p.setFont(font)
    p.drawText(QRectF(0, 4, size, size), Qt.AlignCenter, "N")

    p.end()

    # Save PNG
    output_png.parent.mkdir(parents=True, exist_ok=True)
    pm.save(str(output_png), "PNG")

    # Convert to Multi-Size Windows .ICO
    output_ico.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(str(output_png))
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(str(output_ico), format="ICO", sizes=ico_sizes)

    print(f"[SUCCESS] Generated {output_png} and {output_ico}")

def main():
    root = Path(__file__).resolve().parent
    ico1 = root / "nova.ico"
    png1 = root / "nova.png"
    ico2 = root / "installer" / "nova.ico"
    png2 = root / "installer" / "nova.png"

    create_nova_icon(ico1, png1)
    create_nova_icon(ico2, png2)

if __name__ == "__main__":
    main()
