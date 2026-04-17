#background.py
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QColor
import math


class WaveBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._phase = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        self._phase += 0.02
        self.update()
        
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ✅ DEFINE FIRST
        w, h = self.width(), self.height()

        from PyQt6.QtGui import QRadialGradient, QBrush

        # soft glow
        glow = QRadialGradient(w * 0.5, h * 0.2, w * 0.8)
        glow.setColorAt(0.0, QColor(82, 183, 255, 20))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))

        p.fillRect(self.rect(), QBrush(glow))

        # waves
        waves = [
            (0.55, 38, 0.0, QColor(82, 183, 255, 40)),
            (0.38, 55, 1.8, QColor(82, 183, 255, 28)),
            (0.28, 70, 3.4, QColor(120, 100, 255, 22)),
        ]

        for amp_frac, period, phase_off, col in waves:
            amp = h * amp_frac * 0.08
            path = QPainterPath()

            for px in range(0, w + 2, 2):
                py = h * 0.45 + amp * math.sin(
                    (px / period) + self._phase + phase_off
                )

                if px == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)

            p.setPen(QPen(col, 1.2))
            p.drawPath(path)

        p.end()