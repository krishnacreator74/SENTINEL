"""
chat.py — Sentinel Chat Window

Two-column layout:
  Left  — sidebar with nav (Chat, History, Settings placeholder)
  Right — unified conversation timeline (voice + text interleaved)

Features:
  - Animated sine wave background
  - Voice messages mirrored with mic badge
  - Copyable message text via QTextEdit
  - fast_route() checked before AI — so app launching works
  - Normal window (no WindowStaysOnTopHint) — doesn't block work
  - push_exchange() for voice loop to mirror conversations in
"""

import math
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QLineEdit, QPushButton, QFrame,
    QSizeGrip, QApplication, QTextEdit, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, pyqtSlot, QRectF, QPoint, QPointF, Q_ARG, QMetaObject,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QFont, QPolygon,
)

# ── Palette ───────────────────────────────────────────────────────────────────
BG_DARK   = QColor(6,   8,  14, 255)
BG_SIDE   = QColor(10,  13, 20, 255)
BG_MID    = QColor(14,  18, 28, 255)
ACCENT    = QColor(82,  183, 255, 255)
ACCENT_DIM= QColor(82,  183, 255, 120)
BORDER    = QColor(255, 255, 255, 18)
BORDER_A  = QColor(82,  183, 255, 45)
USER_BG   = QColor(82,  183, 255, 50)
USER_BD   = QColor(82,  183, 255, 120)
AI_BG     = QColor(255, 255, 255, 9)
AI_BD     = QColor(255, 255, 255, 22)
VOICE_BG  = QColor(120, 80,  255, 40)
VOICE_BD  = QColor(140, 100, 255, 100)
TEXT_HI   = QColor(225, 238, 255, 240)
TEXT_MID  = QColor(180, 210, 255, 170)
TEXT_DIM  = QColor(140, 170, 220, 100)

SIDEBAR_W = 180
WIN_W     = 740
WIN_H     = 580
MIN_W     = 520
MIN_H     = 360
CORNER_R  = 16
HEADER_H  = 48

FONT_MAIN = "Segoe UI Variable"
FONT_FALL = "Segoe UI"


def _font(size=10, weight=QFont.Weight.Normal):
    f = QFont(FONT_MAIN, size)
    f.setWeight(weight)
    f.setFamilies([FONT_MAIN, FONT_FALL, "Helvetica Neue", "Arial"])
    return f


# ── Animated sine wave background ─────────────────────────────────────────────
class WaveBackground(QWidget):
    """3 slow drifting sine waves — very subtle, just alive."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._phase = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 FPS smooth animation

    def _tick(self):
        self._phase += 0.02
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        waves = [
            (0.55, 38, 0.0,   QColor(82, 183, 255, 40)),
            (0.38, 55, 1.8,   QColor(82, 183, 255, 30)),
            (0.28, 70, 3.4,   QColor(120, 100, 255, 25)),
        ]
        for amp_frac, period, phase_off, col in waves:
            amp  = h * amp_frac * 0.08
            path = QPainterPath()
            for px in range(0, w + 2, 2):
                base_y = h * 0.45 + phase_off * 10
                py = base_y + amp * math.sin((px / period) + self._phase)
                if px == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)
            p.setPen(QPen(col, 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.end()


# ── Glass background ──────────────────────────────────────────────────────────
class GlassPane(QWidget):
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, CORNER_R, CORNER_R)
        p.setClipPath(clip)

        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, BG_DARK)
        bg.setColorAt(1, QColor(4, 6, 10, 255))
        p.fillPath(clip, QBrush(bg))

        glow = QRadialGradient(w * 0.6, 0, w * 0.8)
        glow.setColorAt(0.0, QColor(82, 183, 255, 10))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillPath(clip, QBrush(glow))

        p.setPen(QPen(BORDER, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), CORNER_R, CORNER_R)

        # Top accent line
        tg = QLinearGradient(0, 1, w, 1)
        tg.setColorAt(0.0,  QColor(82, 183, 255, 0))
        tg.setColorAt(0.3,  QColor(82, 183, 255, 50))
        tg.setColorAt(0.7,  QColor(82, 183, 255, 50))
        tg.setColorAt(1.0,  QColor(82, 183, 255, 0))
        p.setPen(QPen(QBrush(tg), 1))
        p.drawLine(CORNER_R, 1, w - CORNER_R, 1)

        # Sidebar divider
        p.setPen(QPen(BORDER, 1))
        
        p.end()



# ── Sidebar nav item ──────────────────────────────────────────────────────────
class NavItem(QWidget):
    clicked = pyqtSignal()

    def __init__(self, label: str, active: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active  = active
        self._hovered = False
        self._label   = label
        self._alpha   = 0.0

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 12, 0)
        lay.setSpacing(10)

        dot = QLabel()
        dot.setFixedSize(5, 5)
        dot.setStyleSheet(
            f"background: {'#52b7ff' if active else 'rgba(255,255,255,40)'};"
            "border-radius: 2px;"
        )
        lay.addWidget(dot)
        self._dot = dot

        lbl = QLabel(label)
        lbl.setFont(_font(10))
        lbl.setStyleSheet(
            f"color: {'rgba(82,183,255,230)' if active else 'rgba(180,210,255,120)'};"
            "background: transparent;"
        )
        lay.addWidget(lbl, 1)
        self._lbl = lbl

    def set_active(self, v: bool):
        self._active = v
        self._lbl.setStyleSheet(
            f"color: {'rgba(82,183,255,230)' if v else 'rgba(180,210,255,120)'};"
            "background: transparent;"
        )
        self._dot.setStyleSheet(
            f"background: {'#52b7ff' if v else 'rgba(255,255,255,40)'};"
            "border-radius: 2px;"
        )

    def enterEvent(self, _): self._hovered = True;  self.update()
    def leaveEvent(self, _): self._hovered = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        if self._hovered or self._active:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            alpha = 25 if self._active else 15
            p.setBrush(QBrush(QColor(82, 183, 255, alpha)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(self.rect(), 6, 6)
            p.end()
        super().paintEvent(_)



