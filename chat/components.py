#components.py
import math

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QTextEdit,
    QLineEdit, QPushButton, QFrame, QSizePolicy
)

from PyQt6.QtCore import (
    QRectF, Qt, QTimer, QPoint, QPointF, pyqtSignal
)

from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor,
    QPainterPath, QPolygon, QFont,
    QLinearGradient, QRadialGradient
)

from chat.chat import _font, USER_BG, USER_BD, AI_BG, AI_BD, VOICE_BG, VOICE_BD


# ── Message bubble ────────────────────────────────────────────────────────────
class MessageBubble(QWidget):
    def __init__(self, text, role, source="text", parent=None):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 4, 20, 4)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setFont(_font(10))
        self._label.setMaximumWidth(420)

        if role == "user":
            self._label.setStyleSheet("""
                QLabel {
                    background: rgba(82,183,255,0.20);
                    color: white;
                    border-radius: 14px;
                    padding: 10px 14px;
                }
            """)
            outer.addStretch()
            outer.addWidget(self._label)

        else:
            self._label.setStyleSheet("""
                QLabel {
                    background: rgba(255,255,255,0.08);
                    color: white;
                    border-radius: 14px;
                    padding: 10px 14px;
                }
            """)
            outer.addWidget(self._label)
            outer.addStretch()

# ── Typing indicator ──────────────────────────────────────────────────────────
class TypingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)

        self._label = QLabel("● ○ ○")
        self._label.setFont(_font(10))
        self._label.setStyleSheet("color: rgba(255,255,255,120);")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 4, 20, 4)
        lay.addWidget(self._label)
        lay.addStretch()

        # animation states (SEPARATE)
        self._states = ["● ○ ○", "● ● ○", "● ● ●", "○ ● ●", "○ ○ ●"]

        self._phase = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(200)

    def _animate(self):
        self._phase = (self._phase + 1) % len(self._states)
        self._label.setText(self._states[self._phase])

    def stop(self):
        self._timer.stop()

# ── Input bar ─────────────────────────────────────────────────────────────────
class InputBar(QWidget):
    submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(62)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask anything...")
        self._input.setFont(_font(10))
        self._input.setStyleSheet("""
        QLineEdit {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 14px;
            padding: 10px 14px;
            color: white;
        }
        QLineEdit:focus {
            border: 1px solid rgba(82,183,255,0.6);
        }
    """)
        self._input.returnPressed.connect(self._on_submit)
        lay.addWidget(self._input, 1)

        self._btn = QPushButton()
        self._btn.setFixedSize(38, 38)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._on_submit)
        self._btn.setStyleSheet("""
            QPushButton {
                background: rgba(82,183,255,0.15);
                border: 1px solid rgba(82,183,255,0.40);
                border-radius: 19px;
            }
            QPushButton:hover {
                background: rgba(82,183,255,0.28);
                border: 1px solid rgba(82,183,255,0.70);
            }
            QPushButton:pressed { background: rgba(82,183,255,0.42); }
        """)
        self._btn.paintEvent = self._paint_btn
        lay.addWidget(self._btn)

    def _paint_btn(self, _):
        p = QPainter(self._btn)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(82, 183, 255, 38)))
        p.setPen(QPen(QColor(82, 183, 255, 100), 1))
        p.drawEllipse(QRectF(0, 0, 38, 38))
        p.setPen(QPen(QColor(82, 183, 255, 220), 2,
                      Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline(QPolygon([QPoint(12, 26), QPoint(19, 12), QPoint(26, 26)]))
        p.end()

    def _on_submit(self):
        text = self._input.text().strip()
        if text:
            self._input.clear()
            self.submitted.emit(text)

    def set_enabled(self, v: bool):
        self._input.setEnabled(v)
        self._btn.setEnabled(v)
        if v:
            self._input.setFocus()

    def focus(self):
        self._input.setFocus()

# ── Thin divider ──────────────────────────────────────────────────────────────
class Divider(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, _):
        p = QPainter(self)
        w = self.width()
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0.0,  QColor(255, 255, 255, 0))
        g.setColorAt(0.15, QColor(255, 255, 255, 18))
        g.setColorAt(0.85, QColor(255, 255, 255, 18))
        g.setColorAt(1.0,  QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), QBrush(g))
        p.end()

