#window.py
import threading

from chat.chat import WIN_W, WIN_H, MIN_W, MIN_H, HEADER_H
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSlot, Q_ARG, QMetaObject
)
from PyQt6.QtGui import QFont

from chat.view import ChatView
from chat.components import InputBar, Divider
from chat.chat import GlassPane, WaveBackground, _font


class ChatWindow(QWidget):

    def push_exchange(self, user_text: str, ai_text: str):
        # show user
        self._chat_view.insert_bubble(user_text, "user")

        # show typing (optional but nice)
        self._chat_view.show_typing()

        def _finish():
            self._chat_view.hide_typing()
            self._chat_view.insert_bubble(ai_text, "assistant")

        QTimer.singleShot(300, _finish)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def show_animated(self):
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()

        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

        self._anim = anim

    def __init__(self, ai, chat_memory, emitter, bridge, on_close=None):
        super().__init__()
        self._ai       = ai
        self._memory   = chat_memory
        self._emitter  = emitter
        self._bridge   = bridge
        self._on_close = on_close
        self._busy     = False
        self._drag_pos = None
        self._anim     = None

        self._setup_window()
        self._build_ui()
        self._load_history()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(
            (screen.width()  - WIN_W) // 2,
            (screen.height() - WIN_H) // 2,
            WIN_W, WIN_H
        )
        self.setMinimumSize(MIN_W, MIN_H)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self._max_btn.setText("⬜")
        else:
            self.showMaximized()
            self._max_btn.setText("❐")

    def _build_ui(self):
        self.glass = GlassPane(self)
        self.glass.setGeometry(self.rect())

        self._waves = WaveBackground(self)
        self._waves.setGeometry(self.rect())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # HEADER
        header = QWidget()
        header.setFixedHeight(HEADER_H)

        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 16, 0)

        title = QLabel("SENTINEL")
        title.setFont(_font(11, QFont.Weight.DemiBold))
        title.setStyleSheet("color:rgba(240,244,252,0.9); letter-spacing:2px;")
        hl.addWidget(title)

        hl.addStretch()

        self._panel_btn = QPushButton("☰")
        self._panel_btn.setFixedSize(28, 28)
        self._panel_btn.setStyleSheet("color:white; background:transparent; border:none;")
        hl.addWidget(self._panel_btn)

        self._max_btn = QPushButton("⬜")
        self._max_btn.setFixedSize(28, 28)
        self._max_btn.setStyleSheet("color:white; background:transparent; border:none;")
        self._max_btn.clicked.connect(self._toggle_maximize)
        hl.addWidget(self._max_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("color:white; background:transparent; border:none;")
        close_btn.clicked.connect(self.close_window)
        hl.addWidget(close_btn)

        root.addWidget(header)
        root.addWidget(Divider())

        # CHAT AREA
        self._chat_view = ChatView()
        root.addWidget(self._chat_view, 1)

        # INPUT (BOTTOM)
        self._input_bar = InputBar()
        self._input_bar.submitted.connect(self._on_user_message)
        root.addWidget(self._input_bar)

    def _load_history(self):
        messages = self._memory.get_messages()

        for msg in messages:
            role = msg.get("role")
            text = msg.get("content", "")
            src  = msg.get("source", "text")

            if role in ("user", "assistant"):
                self._chat_view.insert_bubble(text, role, src)

        self._chat_view.scroll_to_bottom()

    def _on_user_message(self, text: str):
        if self._busy:
            return

        self._busy = True
        self._input_bar.set_enabled(False)

        self._chat_view.insert_bubble(text, "user")
        self._chat_view.scroll_to_bottom()
        self._chat_view.show_typing()

        threading.Thread(target=self._run_ai, args=(text,), daemon=True).start()

    def _run_ai(self, user_text: str):
        from core.ai import build_system_prompt, run_memory_async
        from system.router import fast_route

        if fast_route(user_text, self._emitter, self._bridge):
            import time
            time.sleep(0.3)  # small delay for realism

            QMetaObject.invokeMethod(
                self, "_on_ai_response_slot",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, "Done.")
            )
            return

        self._memory.add_user(user_text)

        messages = [{"role": "system", "content": build_system_prompt()}]
        messages += self._memory.get_messages()

        response = self._ai.respond(messages, self._emitter, self._bridge)

        response_text = response["text"]

        response_text = response["text"]

        self._memory.add_assistant(response_text)
        
        run_memory_async(response)

        QMetaObject.invokeMethod(
            self, "_on_ai_response_slot",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, response_text)
        )

    @pyqtSlot(str)
    def _on_ai_response_slot(self, text: str):
        self._chat_view.hide_typing()
        self._chat_view.insert_bubble(text, "assistant")
        self._chat_view.scroll_to_bottom()

        self._busy = False
        self._input_bar.set_enabled(True)
        self._input_bar.focus()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.glass.setGeometry(self.rect())
        self._waves.setGeometry(self.rect())

    def close_window(self):
        self.hide()