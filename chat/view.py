from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from chat.components import MessageBubble, TypingIndicator
from chat.chat import _font


class ChatView(QWidget):
    def __init__(self):
        super().__init__()

        self._typing_w = None
        self._has_messages = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ── STACK CONTAINER ─────────────────────
        self._stack = QWidget()
        stack_layout = QVBoxLayout(self._stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)

        # ── MESSAGE AREA ────────────────────────
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 40, 0, 20)
        self._msg_layout.setSpacing(10)
        self._msg_layout.addStretch()

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._msg_container)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")

        # ── EMPTY STATE ─────────────────────────
        self._empty = QLabel("Hey — what’s on your mind?")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setFont(_font(16))
        self._empty.setStyleSheet("color: rgba(255,255,255,180);")

        # 🔥 wrap it in center layout
        empty_container = QWidget()
        empty_layout = QVBoxLayout(empty_container)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.addStretch()
        empty_layout.addWidget(self._empty, alignment=Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()

        # ── STACK THEM ──────────────────────────
        stack_layout.addWidget(self._scroll)
        stack_layout.addWidget(empty_container)

        root.addWidget(self._stack)

    # ── Message Handling ───────────────────────────────────
    def insert_bubble(self, text, role, source="text"):
        if not self._has_messages:
            from PyQt6.QtCore import QPropertyAnimation

            self._anim = QPropertyAnimation(self._empty, b"windowOpacity")
            self._anim.setDuration(300)
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim.finished.connect(self._empty.hide)
            self._anim.start()
            self._has_messages = True

        bubble = MessageBubble(text, role, source)
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, bubble)

    def scroll_to_bottom(self):
        QTimer.singleShot(60, lambda: (
            self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()
            )
        ))

    def show_typing(self):
        if self._typing_w:
            return

        self._typing_w = TypingIndicator()
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, self._typing_w)
        self.scroll_to_bottom()

    def hide_typing(self):
        if not self._typing_w:
            return

        self._typing_w.stop()
        self._msg_layout.removeWidget(self._typing_w)
        self._typing_w.deleteLater()
        self._typing_w = None