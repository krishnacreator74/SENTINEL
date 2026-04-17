#view.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from chat.background import WaveBackground
from chat.components import MessageBubble, TypingIndicator
from chat.chat import _font


class ChatView(QWidget):
    
    def __init__(self):
        super().__init__()
        self._typing_w = None
        self._has_messages = False

        # ── ROOT ─────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ── STACK CONTAINER (overlay) ────────
        self._stack = QWidget(self)

        self._bg = WaveBackground(self._stack)
        root.addWidget(self._stack)

        # ── MESSAGE AREA ─────────────────────
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 80, 0, 20)
        self._msg_layout.setSpacing(10)
        self._msg_layout.addStretch()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        self._scroll = QScrollArea(self._stack)
        self._scroll.setWidget(self._msg_container)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.verticalScrollBar().setSingleStep(10)

        self._scroll.setStyleSheet("""
        QScrollArea {
            background: transparent;
            border: none;
        }

        QScrollBar:vertical {
            background: transparent;
            width: 6px;
            margin: 6px 2px;
        }

        QScrollBar::handle:vertical {
            background: rgba(82,183,255,0.35);
            border-radius: 3px;
        }

        QScrollBar::handle:vertical:hover {
            background: rgba(82,183,255,0.6);
        }

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
        }
        """)

        # ── EMPTY STATE ──────────────────────
        self._empty_container = QWidget(self._stack)
        self._empty_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        empty_layout = QVBoxLayout(self._empty_container)
        empty_layout.setContentsMargins(0, 0, 0, 0)

        empty_layout.addStretch()

        self._empty = QLabel("Hey — what’s on your mind?")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setFont(_font(16))
        self._empty.setStyleSheet("color: rgba(255,255,255,180);")

        empty_layout.addWidget(self._empty, alignment=Qt.AlignmentFlag.AlignCenter)

        empty_layout.addStretch()

    # ── HANDLE RESIZE (CRITICAL) ────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)

        rect = self.rect()

        self._stack.setGeometry(rect)
        self._bg.setGeometry(rect)          
        self._scroll.setGeometry(rect)
        self._empty_container.setGeometry(rect)

    # ── Message Handling ───────────────────
    def insert_bubble(self, text, role, source="text"):
        if not self._has_messages:
            from PyQt6.QtCore import QPropertyAnimation

            self._anim = QPropertyAnimation(self._empty, b"windowOpacity")
            self._anim.setDuration(450)
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim.finished.connect(self._empty.hide)
            self._anim.start()

            self._has_messages = True

        bubble = MessageBubble(text, role, source)
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, bubble)

        self.scroll_to_bottom()
        QTimer.singleShot(80, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        def _scroll():
            bar = self._scroll.verticalScrollBar()
            bar.setValue(bar.maximum())

        QTimer.singleShot(0, _scroll)

        QTimer.singleShot(0, _scroll)

    def show_typing(self):
        if self._typing_w:
            return

        self._typing_w = TypingIndicator()
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, self._typing_w)

        self.scroll_to_bottom()
        QTimer.singleShot(50, self.scroll_to_bottom)

    def hide_typing(self):
        if not self._typing_w:
            return

        self._typing_w.stop()
        self._msg_layout.removeWidget(self._typing_w)
        self._typing_w.deleteLater()
        self._typing_w = None