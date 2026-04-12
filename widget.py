"""
widget.py — Sentinel ambient circle widget

A small, always-on-top transparent circle that lives at the bottom-center
of the screen. Renders using PyQt6's painter for real compositing and glow.

States:
  idle      — dim, very slow breath pulse, almost invisible
  listening — brighter blue, medium pulse
  speaking  — reacts to audio energy, inner glow expands

Click:
  Single click within circle area → toggle chat window
  CLICK_COOLDOWN prevents accidental double-triggers (gaming safety)

Game mode:
  set_game_mode(True)  → widget hides entirely
  set_game_mode(False) → widget restores
"""

import math
import time

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QRadialGradient,
    QPen, QBrush,
)

# ── Geometry ──────────────────────────────────────────────────────────────────
W       = 80
H       = 80
CX      = W / 2
CY      = H / 2
R_CORE  = 14    # ring radius
R_INNER = 10    # inner fill glow radius
R_GLOW  = 30    # outer halo max radius

# ── Colours (r, g, b) ─────────────────────────────────────────────────────────
COL_BLUE = (82,  183, 255)
COL_CYAN = (120, 220, 255)
COL_PINK = (200, 120, 255)

# ── Timing ────────────────────────────────────────────────────────────────────
FRAME_MS       = 16     # ~60 fps
CLICK_COOLDOWN = 0.8    # seconds — min time between accepted clicks


class SentinelWidget(QWidget):

    clicked = pyqtSignal()

    def __init__(self):
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication must exist before SentinelWidget")
        super().__init__()

        # ── State ─────────────────────────────────────────────────────────────
        self.state       = "idle"
        self.energy      = 0.0
        self._smooth_e   = 0.0
        self._phase      = 0.0
        self._game_mode  = False
        self._chat_win   = None
        self._chat_open  = False
        self._last_click = 0.0

        # ── Window flags ──────────────────────────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(W, H)

        # Bottom-center of primary screen
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - W) // 2, screen.height() - H - 40)

        # ── Timer ─────────────────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(FRAME_MS)

        self.show()

    # ── Public API ────────────────────────────────────────────────────────────
    def set_idle(self):
        self.state = "idle"

    def set_listening(self):
        self.state = "listening"

    def set_speaking(self):
        self.state = "speaking"

    def set_energy(self, v: float):
        self.energy = max(0.0, min(1.0, float(v)))

    def set_game_mode(self, on: bool):
        self._game_mode = on
        self.hide() if on else self.show()

    def set_chat_window(self, win):
        self._chat_win = win

    def on_chat_closed_externally(self):
        self._chat_open = False

    # ── Internal ──────────────────────────────────────────────────────────────
    def _tick(self):
        self._phase += FRAME_MS / 1000.0
        target = self.energy if self.state == "speaking" else 0.0
        self._smooth_e = self._smooth_e * 0.85 + target * 0.15
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        dx = event.position().x() - CX
        dy = event.position().y() - CY
        # Only accept clicks inside the halo area
        if math.sqrt(dx * dx + dy * dy) > R_GLOW:
            return
        now = time.perf_counter()
        if now - self._last_click < CLICK_COOLDOWN:
            return
        self._last_click = now

        if self._chat_win is None:
            return
        if not self._chat_open:
            self._chat_open = True
            self._chat_win.show_animated()
        else:
            self._chat_open = False
            self._chat_win.close_window()

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        t = self._phase
        s = self.state
        e = self._smooth_e

        # Per-state values
        if s == "idle":
            breath      = math.sin(t * 0.9) * 0.5 + 0.5
            core_a      = int(50  + breath * 40)
            glow_a      = int(15  + breath * 15)
            inner_a     = int(25  + breath * 25)
            r_h         = R_CORE + 4 + breath * 5
            cr, cg, cb  = COL_BLUE
            rw          = 1.2

        elif s == "listening":
            breath      = math.sin(t * 2.4) * 0.5 + 0.5
            core_a      = int(140 + breath * 70)
            glow_a      = int(45  + breath * 45)
            inner_a     = int(65  + breath * 55)
            r_h         = R_CORE + 6 + breath * 12
            cr, cg, cb  = COL_CYAN
            rw          = 1.6

        else:  # speaking
            beat        = math.sin(t * 9.0) * 0.25 + 0.75
            boost       = e * 0.65 + beat * 0.35
            core_a      = int(170 + boost * 80)
            glow_a      = int(55  + boost * 85)
            inner_a     = int(90  + boost * 120)
            r_h         = R_CORE + 9 + boost * 16
            blend       = e * 0.3
            cr = int(COL_BLUE[0] * (1 - blend) + COL_PINK[0] * blend)
            cg = int(COL_BLUE[1] * (1 - blend) + COL_PINK[1] * blend)
            cb = int(COL_BLUE[2] * (1 - blend) + COL_PINK[2] * blend)
            rw          = 1.8

        center = QPointF(CX, CY)

        # Layer 1 — outer halo
        g1 = QRadialGradient(center, r_h)
        g1.setColorAt(0.0, QColor(cr, cg, cb, glow_a))
        g1.setColorAt(0.55, QColor(cr, cg, cb, glow_a // 4))
        g1.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(g1))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, r_h, r_h)

        # Layer 2 — inner fill (soft white centre)
        g2 = QRadialGradient(QPointF(CX, CY - 3), R_INNER)
        g2.setColorAt(0.0, QColor(255, 255, 255, inner_a))
        g2.setColorAt(0.5, QColor(cr, cg, cb, inner_a // 2))
        g2.setColorAt(1.0, QColor(cr, cg, cb, 0))
        p.setBrush(QBrush(g2))
        p.drawEllipse(center, R_CORE - 2, R_CORE - 2)

        # Layer 3 — core ring
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(cr, cg, cb, core_a), rw)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawEllipse(center, R_CORE, R_CORE)

        # Layer 4 — specular highlight (top-left glint)
        g3 = QRadialGradient(QPointF(CX - 5, CY - 7), 5)
        g3.setColorAt(0.0, QColor(255, 255, 255, core_a // 2))
        g3.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(g3))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(CX - 5, CY - 7), 5, 5)

        p.end()

    def run(self):
        QApplication.instance().exec()


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import threading

    app = QApplication(sys.argv)
    w   = SentinelWidget()

    def _demo():
        time.sleep(2)
        w.set_listening()
        time.sleep(3)
        w.set_speaking()
        for i in range(150):
            w.set_energy(abs(math.sin(i * 0.14)) * 0.9 + 0.1)
            time.sleep(0.05)
        w.set_idle()

    threading.Thread(target=_demo, daemon=True).start()
    sys.exit(app.exec())