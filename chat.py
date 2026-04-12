"""
chat.py — Sentinel Chat Window

A text-based interface to the same AI pipeline used by voice mode.
Shares ChatMemory with the voice loop so history is unified.
Opens when the user clicks the widget; closes on X or widget re-click.
"""

import sys
import threading
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QLineEdit, QPushButton, QFrame, QSizeGrip, QApplication,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QObject, pyqtSlot, QRectF, QPoint,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient,
    QPainterPath, QKeyEvent, QFont,
)

# ── Palette (mirrors hud.py) ──────────────────────────────────────────────────
C_BG_TOP     = QColor(8,   10,  15,  255)
C_BG_BOT     = QColor(4,   6,   10,  255)
C_BORDER     = QColor(255, 255, 255, 22)
C_ACCENT     = QColor(82,  183, 255, 255)
C_ACCENT_DIM = QColor(82,  183, 255, 160)
C_ACCENT_BG  = QColor(82,  183, 255, 40)
C_TEXT_BRIGHT= QColor(220, 235, 255, 240)
C_TEXT_DIM   = QColor(180, 210, 255, 120)
C_USER_BG    = QColor(82,  183, 255, 55)
C_USER_BD    = QColor(82,  183, 255, 130)
C_AI_BG      = QColor(255, 255, 255, 12)
C_AI_BD      = QColor(255, 255, 255, 28)

CORNER_R   = 18
HEADER_H   = 50
WIN_W      = 640
WIN_H      = 560
MIN_W      = 420
MIN_H      = 300


# ── Glass background panel ────────────────────────────────────────────────────
class GlassPane(QWidget):
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, CORNER_R, CORNER_R)
        p.setClipPath(clip)

        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, C_BG_TOP)
        bg.setColorAt(1.0, C_BG_BOT)
        p.fillPath(clip, QBrush(bg))

        glow = QRadialGradient(w / 2, 0, w * 0.7)
        glow.setColorAt(0.0, QColor(82, 183, 255, 14))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillPath(clip, QBrush(glow))

        p.setPen(QPen(C_BORDER, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), CORNER_R, CORNER_R)

        # Top accent line
        tg = QLinearGradient(0, 1, w, 1)
        tg.setColorAt(0.0,  QColor(82, 183, 255, 0))
        tg.setColorAt(0.25, QColor(82, 183, 255, 55))
        tg.setColorAt(0.75, QColor(82, 183, 255, 55))
        tg.setColorAt(1.0,  QColor(82, 183, 255, 0))
        p.setPen(QPen(QBrush(tg), 1))
        p.drawLine(CORNER_R, 1, w - CORNER_R, 1)
        p.end()


# ── Thin divider ──────────────────────────────────────────────────────────────
class ThinDivider(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, _):
        p = QPainter(self)
        w = self.width()
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0.0,  QColor(255, 255, 255, 0))
        g.setColorAt(0.15, QColor(255, 255, 255, 22))
        g.setColorAt(0.85, QColor(255, 255, 255, 22))
        g.setColorAt(1.0,  QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), QBrush(g))
        p.end()


# ── Typing indicator (3 bouncing dots) ───────────────────────────────────────
class TypingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def _tick(self):
        self._phase += 0.18
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background bubble (same as AI message)
        path = QPainterPath()
        bw = 68
        path.addRoundedRect(QRectF(14, 4, bw, 28), 14, 14)
        p.setBrush(QBrush(C_AI_BG))
        p.setPen(QPen(C_AI_BD, 1))
        p.drawPath(path)

        # Three dots
        import math
        cx = 14 + bw / 2
        dot_r = 3.5
        spacing = 13
        for i in range(3):
            offset = math.sin(self._phase + i * 1.2) * 4.5
            x = cx - spacing + i * spacing
            y = 18 - offset
            alpha = int(160 + abs(math.sin(self._phase + i * 1.2)) * 95)
            p.setBrush(QBrush(QColor(82, 183, 255, alpha)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(x - dot_r, y - dot_r, dot_r * 2, dot_r * 2))
        p.end()

    def stop(self):
        self._timer.stop()


# ── Single message bubble ─────────────────────────────────────────────────────
class MessageBubble(QWidget):
    """
    role = 'user' → right-aligned blue bubble
    role = 'assistant' → left-aligned dark bubble
    """
    def __init__(self, text: str, role: str, parent=None):
        super().__init__(parent)
        self._role = role

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(0)

        self._lbl = QLabel(text)
        self._lbl.setWordWrap(True)
        self._lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._lbl.setMaximumWidth(440)

        font = QFont("Segoe UI", 10)
        font.setWeight(QFont.Weight.Normal)
        self._lbl.setFont(font)

        if role == "user":
            self._lbl.setStyleSheet(
                "color: rgba(180,225,255,255);"
                "background: transparent;"
                "padding: 9px 14px;"
                "border-radius: 14px;"
                "line-height: 1.6;"
            )
            outer.addStretch()
            outer.addWidget(self._lbl)
        else:
            self._lbl.setStyleSheet(
                "color: rgba(220,235,255,230);"
                "background: transparent;"
                "padding: 9px 14px;"
                "border-radius: 14px;"
                "line-height: 1.6;"
            )
            outer.addWidget(self._lbl)
            outer.addStretch()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        lbl_rect = self._lbl.geometry()
        r = QRectF(lbl_rect.x(), lbl_rect.y(), lbl_rect.width(), lbl_rect.height())

        if self._role == "user":
            p.setBrush(QBrush(C_USER_BG))
            p.setPen(QPen(C_USER_BD, 1))
        else:
            p.setBrush(QBrush(C_AI_BG))
            p.setPen(QPen(C_AI_BD, 1))

        p.drawRoundedRect(r, 14, 14)
        p.end()


# ── Role label (tiny timestamp/label above groups) ────────────────────────────
class RoleLabel(QLabel):
    def __init__(self, text: str, align_right: bool = False, parent=None):
        super().__init__(text, parent)
        align = "right" if align_right else "left"
        self.setStyleSheet(
            f"color: rgba(82,183,255,140);"
            f"font-size: 10px; font-weight: 500; letter-spacing: 1px;"
            f"font-family: 'Segoe UI', sans-serif;"
            f"background: transparent; padding: 0 14px;"
            f"text-align: {align};"
        )
        if align_right:
            self.setAlignment(Qt.AlignmentFlag.AlignRight)


# ── Input bar ─────────────────────────────────────────────────────────────────
class InputBar(QWidget):
    submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Message Sentinel...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(82,183,255,0.25);
                border-radius: 20px;
                color: rgba(220,235,255,230);
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                padding: 0 16px;
                selection-background-color: rgba(82,183,255,0.35);
            }
            QLineEdit:focus {
                border: 1px solid rgba(82,183,255,0.65);
                background: rgba(255,255,255,0.10);
            }
            QLineEdit::placeholder {
                color: rgba(180,210,255,80);
            }
        """)
        self._input.returnPressed.connect(self._on_submit)
        lay.addWidget(self._input, 1)

        self._btn = QPushButton()
        self._btn.setFixedSize(38, 38)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet("""
            QPushButton {
                background: rgba(82,183,255,0.18);
                border: 1px solid rgba(82,183,255,0.45);
                border-radius: 19px;
            }
            QPushButton:hover {
                background: rgba(82,183,255,0.32);
                border: 1px solid rgba(82,183,255,0.75);
            }
            QPushButton:pressed {
                background: rgba(82,183,255,0.45);
            }
        """)
        self._btn.clicked.connect(self._on_submit)
        lay.addWidget(self._btn)

        # Draw send arrow on button via paintEvent override — done in subclass below
        self._btn.paintEvent = self._paint_send_btn

    def _paint_send_btn(self, event):
        p = QPainter(self._btn)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Draw the button background first (re-implement minimal style)
        r = QRectF(0, 0, 38, 38)
        p.setBrush(QBrush(QColor(82, 183, 255, 45)))
        p.setPen(QPen(QColor(82, 183, 255, 115), 1))
        p.drawRoundedRect(r, 19, 19)
        # Arrow up-right
        p.setPen(QPen(QColor(82, 183, 255, 230), 2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        pts = [
            QPoint(12, 26), QPoint(19, 12), QPoint(26, 26),
        ]
        from PyQt6.QtGui import QPolygon
        p.drawPolyline(QPolygon(pts))
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


# ── Main chat window ──────────────────────────────────────────────────────────
class ChatWindow(QWidget):

    def __init__(self, ai, chat_memory, on_close=None):
        super().__init__()
        self._ai          = ai
        self._memory      = chat_memory
        self._on_close    = on_close
        self._drag_pos    = None
        self._typing_w    = None
        self._busy        = False
        self._anim        = None

        self._setup_window()
        self._build_ui()
        self._load_history()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width()  - WIN_W) // 2
        y = (screen.height() - WIN_H) // 2
        self.setGeometry(x, y, WIN_W, WIN_H)
        self.setMinimumSize(MIN_W, MIN_H)

    def _build_ui(self):
        self.glass = GlassPane(self)
        self.glass.setGeometry(self.rect())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(HEADER_H)
        header.setStyleSheet("background:transparent;")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(20, 0, 16, 0)
        hlay.setSpacing(10)

        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet("background:#52b7ff;border-radius:3px;")
        hlay.addWidget(dot)

        title = QLabel("SENTINEL")
        title.setStyleSheet(
            "color:rgba(240,244,252,0.92); font-size:11px; font-weight:600;"
            "letter-spacing:2.8px; font-family:'Segoe UI',sans-serif;"
            "background:transparent;"
        )
        hlay.addWidget(title)

        subtitle = QLabel("chat")
        subtitle.setStyleSheet(
            "color:rgba(82,183,255,150); font-size:10px; font-weight:400;"
            "letter-spacing:1.2px; font-family:'Segoe UI',sans-serif;"
            "background:transparent;"
        )
        hlay.addWidget(subtitle)
        hlay.addStretch()

        # Close button (X)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(255,255,255,0);
                border-radius: 14px;
                color: rgba(255,255,255,80);
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255,75,75,0.25);
                border: 1px solid rgba(255,75,75,0.5);
                color: rgba(255,130,130,255);
            }
        """)
        close_btn.clicked.connect(self.close_window)
        hlay.addWidget(close_btn)

        root.addWidget(header)
        root.addWidget(ThinDivider())

        # ── Scroll area for messages ─────────────────────────────────────────
        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background:transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 12, 0, 8)
        self._msg_layout.setSpacing(2)
        self._msg_layout.addStretch()   # pushes messages up

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._msg_container)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setStyleSheet("""
            QScrollArea  { background:transparent; border:none; }
            QScrollBar:vertical {
                background:transparent; width:3px; margin:6px 3px;
            }
            QScrollBar::handle:vertical {
                background:rgba(82,183,255,0.30); border-radius:1px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height:0; }
        """)
        root.addWidget(self._scroll, 1)

        root.addWidget(ThinDivider())

        # ── Input bar ────────────────────────────────────────────────────────
        self._input_bar = InputBar()
        self._input_bar.submitted.connect(self._on_user_message)
        root.addWidget(self._input_bar)

        # Resize grip
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 4, 4)
        grip_row.addStretch()
        grip = QSizeGrip(self)
        grip.setStyleSheet(
            "QSizeGrip{width:10px;height:10px;image:none;background:transparent;}"
        )
        grip_row.addWidget(grip)
        root.addLayout(grip_row)
        self.setLayout(root)

    # ── History loading ───────────────────────────────────────────────────────
    def _load_history(self):
        """Render existing chat memory into the window on open."""
        messages = self._memory.get_messages()
        if not messages:
            self._add_sentinel_greeting()
            return
        last_role = None
        for msg in messages:
            role = msg["role"]
            text = msg["content"]
            if role not in ("user", "assistant"):
                continue
            if role != last_role:
                label_text = "YOU" if role == "user" else "SENTINEL"
                self._add_role_label(label_text, align_right=(role == "user"))
                last_role = role
            self._insert_bubble(text, role)
        self._scroll_to_bottom()

    def _add_sentinel_greeting(self):
        self._add_role_label("SENTINEL", align_right=False)
        self._insert_bubble(
            "Hey — what can I help you with?", "assistant"
        )

    def _add_role_label(self, text: str, align_right: bool = False):
        lbl = RoleLabel(text, align_right=align_right)
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, lbl)

    def _insert_bubble(self, text: str, role: str):
        bubble = MessageBubble(text, role)
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, bubble)

    def _scroll_to_bottom(self):
        QTimer.singleShot(60, lambda: (
            self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()
            )
        ))

    # ── Message handling ──────────────────────────────────────────────────────
    def _on_user_message(self, text: str):
        if self._busy:
            return
        self._busy = True
        self._input_bar.set_enabled(False)

        # Show user bubble
        self._add_role_label("YOU", align_right=True)
        self._insert_bubble(text, "user")
        self._scroll_to_bottom()

        # Show typing indicator
        self._show_typing()

        # Run AI in background thread
        threading.Thread(target=self._run_ai, args=(text,), daemon=True).start()

    def _show_typing(self):
        if self._typing_w is not None:
            return
        self._add_role_label("SENTINEL", align_right=False)
        self._typing_w = TypingIndicator()
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, self._typing_w)
        self._scroll_to_bottom()

    def _hide_typing(self):
        if self._typing_w is None:
            return
        self._typing_w.stop()
        self._msg_layout.removeWidget(self._typing_w)
        self._typing_w.deleteLater()
        self._typing_w = None

    def _run_ai(self, user_text: str):
        from ai import build_system_prompt, run_memory_async

        # Add to shared memory
        self._memory.add_user(user_text)

        messages = [
            {"role": "system", "content": build_system_prompt()}
        ] + self._memory.get_messages()

        # Deduplicate consecutive roles
        fixed, last_role = [], None
        for m in messages:
            if m["role"] != last_role:
                fixed.append(m)
                last_role = m["role"]

        # respond() with no voice/HUD — text only
        response = self._ai.respond(
            fixed,
            on_sentence=None,
            hud=None,
        )

        if not response:
            response = "Sorry, I had trouble with that. Please try again."

        # Save to memory
        self._memory.add_assistant(response)
        run_memory_async(user_text, response)

        # Update UI on main thread
        from PyQt6.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(
            self, "_on_ai_response_slot",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, response)
        )

    def _on_ai_response(self, text: str):
        self._hide_typing()
        self._insert_bubble(text, "assistant")
        self._scroll_to_bottom()
        self._busy = False
        self._input_bar.set_enabled(True)
        self._input_bar.focus()
        
    from PyQt6.QtCore import pyqtSlot

    @pyqtSlot(str)
    def _on_ai_response_slot(self, text: str):
        self._on_ai_response(text)

    # ── Window chrome ─────────────────────────────────────────────────────────
    def show_animated(self):
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(280)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start()
        self._anim = a
        QTimer.singleShot(300, self._input_bar.focus)

    def close_window(self):
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(200)
        a.setStartValue(self.windowOpacity())
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.Type.InCubic)
        a.finished.connect(self.hide)
        a.start()
        self._anim = a
        if self._on_close:
            QTimer.singleShot(220, self._on_close)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.glass.setGeometry(self.rect())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < HEADER_H:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None

    def closeEvent(self, e):
        e.ignore()
        self.close_window()