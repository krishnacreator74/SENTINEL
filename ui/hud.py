"""
hud.py  —  Sentinel HUD  (sentence-glow edition)

Each AI response is split into sentences.
States per sentence:
  FUTURE  — dim / not yet spoken
  ACTIVE  — glowing blue, left accent bar  (currently speaking)
  PAST    — solid white, stays visible

No word-level tracking, no cursor manipulation.
Voice just calls begin_sentence(idx) / end_sentence(idx).

Fix: show_hud() called during load now shows immediately at full opacity.
     A fade-in is used only when the window was fully hidden (opacity == 0).
     begin_sentence() never restarts a fade — it just ensures visibility.
"""

import logging
import os, sys, time, threading, urllib.request, re

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QScrollArea, QSizeGrip, QFrame,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QObject, pyqtSlot, QRectF,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient,
    QPixmap, QImage, QPainterPath,
)

# ── Palette ────────────────────────────────────────────────────────────────────
C_BG_TOP    = QColor(8,   10,  15,  255)
C_BG_BOT    = QColor(4,   6,   10,  255)
C_BORDER    = QColor(255, 255, 255, 22)
C_CLOSE_HOV = QColor(255, 75,  75,  200)

C_FUTURE    = QColor(220, 235, 255, 55)
C_ACTIVE_BG = QColor(82,  183, 255, 55)
C_ACTIVE_BD = QColor(82,  183, 255, 160)
C_ACTIVE_TX = QColor(180, 225, 255, 255)
C_ACTIVE_BAR= QColor(82,  183, 255, 255)
C_PAST      = QColor(220, 235, 255, 235)

CORNER_R        = 16
HEADER_H        = 44
MIN_W, MIN_H    = 380, 140
DEFAULT_W       = 520
DEFAULT_H       = 380

STATE_FUTURE  = 0
STATE_ACTIVE  = 1
STATE_PAST    = 2


# ── Signal bridge ──────────────────────────────────────────────────────────────
class HUDSignals(QObject):
    load_sentences  = pyqtSignal(list)
    begin_sentence  = pyqtSignal(int)
    end_sentence    = pyqtSignal(int)
    finish_all      = pyqtSignal()
    show_image      = pyqtSignal(str)
    pixmap_ready    = pyqtSignal(QPixmap)
    clear           = pyqtSignal()
    close_hud       = pyqtSignal()
    set_title       = pyqtSignal(str)


# ── Glass pane ────────────────────────────────────────────────────────────────
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

        glow = QRadialGradient(w / 2, 0, w * 0.6)
        glow.setColorAt(0.0, QColor(82, 183, 255, 18))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillPath(clip, QBrush(glow))

        p.setPen(QPen(C_BORDER, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), CORNER_R, CORNER_R)

        tg = QLinearGradient(0, 1, w, 1)
        tg.setColorAt(0.0,  QColor(82, 183, 255, 0))
        tg.setColorAt(0.25, QColor(82, 183, 255, 45))
        tg.setColorAt(0.75, QColor(82, 183, 255, 45))
        tg.setColorAt(1.0,  QColor(82, 183, 255, 0))
        p.setPen(QPen(QBrush(tg), 1))
        p.drawLine(CORNER_R, 1, w - CORNER_R, 1)
        p.end()


# ── Single sentence widget ────────────────────────────────────────────────────
class SentenceBlock(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._state = STATE_FUTURE

        m = re.match(r"^(\d+)\.\s+(.*)", text, re.DOTALL)
        self._is_numbered = m is not None
        self._is_heading  = (not m) and text.endswith(":") and len(text) < 80

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(10)

        if self._is_numbered:
            num_lbl = QLabel(m.group(1))
            num_lbl.setFixedSize(22, 22)
            num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num_lbl.setStyleSheet(
                "background: rgba(82,183,255,0.18); border-radius: 11px;"
                "color: rgba(82,183,255,220); font-size: 11px; font-weight: 600;"
                "font-family: 'Segoe UI', sans-serif;"
            )
            lay.addWidget(num_lbl, 0, Qt.AlignmentFlag.AlignTop)
            display_text = m.group(2)
        else:
            display_text = text

        self._lbl = QLabel(display_text)
        self._lbl.setWordWrap(True)
        lay.addWidget(self._lbl, 1)
        self._apply_state()

    def set_state(self, state: int):
        if self._state == state:
            return
        self._state = state
        self._apply_state()
        self.update()

    def _apply_state(self):
        if self._is_heading:
            colours = {
                STATE_FUTURE: "rgba(82,183,255,120)",
                STATE_ACTIVE: "rgba(82,183,255,220)",
                STATE_PAST:   "rgba(82,183,255,200)",
            }
            self._lbl.setStyleSheet(
                "background: transparent; border: none;"
                "font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;"
                "font-size: 11px; font-weight: 600; letter-spacing: 0.8px;"
                f"color: {colours[self._state]};"
            )
            return

        colours = {
            STATE_FUTURE: "rgba(220,235,255,80)",
            STATE_ACTIVE: "rgba(180,225,255,255)",
            STATE_PAST:   "rgba(220,235,255,235)",
        }
        self._lbl.setStyleSheet(
            "background: transparent; border: none;"
            "font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;"
            "font-size: 13px; font-weight: 400; line-height: 1.75;"
            f"color: {colours[self._state]};"
        )

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())

        if self._state == STATE_ACTIVE and not self._is_heading:
            p.setBrush(QBrush(C_ACTIVE_BG))
            p.setPen(QPen(C_ACTIVE_BD, 1))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
            bar = QRectF(0, self.height() * 0.15, 2, self.height() * 0.7)
            p.setBrush(QBrush(C_ACTIVE_BAR))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bar, 1, 1)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(r)

        p.end()


# ── Close button ───────────────────────────────────────────────────────────────
class CloseButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False

    def enterEvent(self, _):    self._hovered = True;  self.update()
    def leaveEvent(self, _):    self._hovered = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, r = 9, 9, 7
        if self._hovered:
            p.setBrush(QBrush(C_CLOSE_HOV)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            p.setPen(QPen(QColor(255, 255, 255, 220), 1.4))
            d = 3
            p.drawLine(cx-d, cy-d, cx+d, cy+d); p.drawLine(cx+d, cy-d, cx-d, cy+d)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        p.end()


# ── Thin divider ───────────────────────────────────────────────────────────────
class ThinDivider(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedHeight(1)

    def paintEvent(self, _):
        p = QPainter(self); w = self.width()
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0.0,  QColor(255, 255, 255, 0))
        g.setColorAt(0.15, QColor(255, 255, 255, 20))
        g.setColorAt(0.85, QColor(255, 255, 255, 20))
        g.setColorAt(1.0,  QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), QBrush(g)); p.end()


# ── Main HUD window ────────────────────────────────────────────────────────────
class SentinelHUD(QWidget):

    def __init__(self):
        super().__init__()
        self.signals           = HUDSignals()
        self._drag_pos         = None
        self._anim             = None
        self._blocks: list[SentenceBlock] = []
        self._user_scrolled_up = False
        self._is_speaking      = False   # True while sentences are being spoken
        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._auto_close_timer = None

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_Resized)
        screen = QApplication.primaryScreen().geometry()
        x = screen.width()  - DEFAULT_W - 36
        y = screen.height() - DEFAULT_H - 72
        self.setGeometry(x, y, DEFAULT_W, DEFAULT_H)
        self.setMinimumSize(MIN_W, MIN_H)

    def _build_ui(self):
        self.glass = GlassPane(self)
        self.glass.setGeometry(self.rect())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(HEADER_H)
        header.setStyleSheet("background:transparent;")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 14, 0); hlay.setSpacing(10)

        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet("background:#52b7ff;border-radius:3px;")
        hlay.addWidget(dot)

        self.title_lbl = QLabel("SENTINEL")
        self.title_lbl.setStyleSheet(
            "color:rgba(240,244,252,0.9);font-size:11px;font-weight:600;"
            "letter-spacing:2.5px;"
            "font-family:'Helvetica Neue','Segoe UI',sans-serif;"
            "background:transparent;"
        )
        hlay.addWidget(self.title_lbl)
        hlay.addStretch()

        self.close_btn = CloseButton()
        self.close_btn.clicked.connect(self._on_close_clicked)
        hlay.addWidget(self.close_btn)

        root.addWidget(header)
        root.addWidget(ThinDivider())

        self.content_w = QWidget()
        self.content_w.setStyleSheet("background:transparent;")
        self.cl = QVBoxLayout(self.content_w)
        self.cl.setContentsMargins(10, 10, 10, 14)
        self.cl.setSpacing(4)
        self.cl.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.content_w)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setStyleSheet("""
            QScrollArea  { background:transparent; border:none; }
            QScrollBar:vertical {
                background:transparent; width:3px; margin:6px 4px;
            }
            QScrollBar::handle:vertical {
                background:rgba(82,183,255,0.35); border-radius:1px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height:0; }
        """)
        root.addWidget(self.scroll, 1)
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_user_scroll)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 4, 4); grip_row.addStretch()
        grip = QSizeGrip(self)
        grip.setStyleSheet(
            "QSizeGrip{width:10px;height:10px;image:none;background:transparent;}"
        )
        grip_row.addWidget(grip)
        root.addLayout(grip_row)
        self.setLayout(root)

    def _connect_signals(self):
        self.signals.load_sentences.connect(self._on_load_sentences)
        self.signals.begin_sentence.connect(self._on_begin_sentence)
        self.signals.end_sentence.connect(self._on_end_sentence)
        self.signals.finish_all.connect(self._on_finish_all)
        self.signals.show_image.connect(self._on_image)
        self.signals.pixmap_ready.connect(self._on_pixmap)
        self.signals.clear.connect(self._on_clear)
        self.signals.close_hud.connect(self.hide_hud)
        self.signals.set_title.connect(self._on_title)

    def _scroll_to_active(self, idx: int):
        if self._user_scrolled_up:
            return
        if 0 <= idx < len(self._blocks):
            block = self._blocks[idx]
            QTimer.singleShot(40, lambda: self.scroll.ensureWidgetVisible(block, 0, 20))

    def _on_user_scroll(self, value: int):
        sb = self.scroll.verticalScrollBar()
        at_bottom = (sb.maximum() - value) <= 60
        if at_bottom:
            self._user_scrolled_up = False
        elif sb.maximum() > 0:
            self._user_scrolled_up = True

    # ── Slots ─────────────────────────────────────────────────────────────────
    @pyqtSlot(list)
    def _on_load_sentences(self, sentences: list):
        # Cancel any pending auto-close
        if self._auto_close_timer is not None:
            self._auto_close_timer.stop()
            self._auto_close_timer = None

        self._clear_content()
        self._user_scrolled_up = False
        self._is_speaking      = True

        for text in sentences:
            block = SentenceBlock(text)
            self._blocks.append(block)
            self.cl.insertWidget(self.cl.count() - 1, block)

        # Show immediately at full opacity — no fade-in while content is loading
        self._show_immediate()

    @pyqtSlot(int)
    def _on_begin_sentence(self, idx: int):
        if 0 <= idx < len(self._blocks):
            self._blocks[idx].set_state(STATE_ACTIVE)
            # Ensure visible without re-triggering a fade-in animation
            if not self.isVisible():
                self._show_immediate()
            self._scroll_to_active(idx)

    @pyqtSlot(int)
    def _on_end_sentence(self, idx: int):
        if 0 <= idx < len(self._blocks):
            self._blocks[idx].set_state(STATE_PAST)

    @pyqtSlot()
    def _on_finish_all(self):
        self._is_speaking = False
        for b in self._blocks:
            b.set_state(STATE_PAST)
        self._auto_close_timer = QTimer()
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.hide_hud)
        self._auto_close_timer.start(10_000)

    @pyqtSlot(str)
    def _on_image(self, src: str):
        def _load():
            try:
                if src.startswith("http"):
                    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        data = r.read()
                    img = QImage.fromData(data)
                else:
                    img = QImage(src)
                if img.isNull():
                    return
                pix = QPixmap.fromImage(img)
                vw  = self.scroll.viewport().width()
                max_w = max(200, vw - 40)
                if pix.width() > max_w:
                    pix = pix.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)
                self.signals.pixmap_ready.emit(pix)
            except Exception as e:
                print(f"[HUD] Image error: {e}")
                logging.error(f"[HUD] Image error: {e}")
        threading.Thread(target=_load, daemon=True).start()

    @pyqtSlot(QPixmap)
    def _on_pixmap(self, pix: QPixmap):
        lbl = QLabel()
        lbl.setPixmap(pix)
        lbl.setFixedSize(pix.width(), pix.height())
        lbl.setStyleSheet(
            "border-radius:8px;border:1px solid rgba(255,255,255,0.08);"
            "background:transparent;"
        )
        self.cl.insertWidget(self.cl.count() - 1, lbl)
        if not self._user_scrolled_up:
            QTimer.singleShot(60, lambda: self.scroll.ensureWidgetVisible(lbl, 0, 20))

    @pyqtSlot()
    def _on_clear(self): self._clear_content()

    @pyqtSlot(str)
    def _on_title(self, t: str): self.title_lbl.setText(t.upper())

    def _clear_content(self):
        self._blocks = []
        while self.cl.count() > 1:
            item = self.cl.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.scroll.verticalScrollBar().setValue(0)

    # ── Window visibility ──────────────────────────────────────────────────────
    def _show_immediate(self):
        """Show at full opacity instantly — used during active speech."""
        # Stop any running hide/fade animation so it doesn't clobber opacity
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()

    def show_hud(self):
        """Gentle fade-in — used only when HUD appears while NOT actively speaking."""
        if self._is_speaking:
            self._show_immediate()
            return
        if self._anim is not None:
            self._anim.stop()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(300)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start()
        self._anim = a

    def hide_hud(self):
        if self._anim is not None:
            self._anim.stop()
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(200)
        a.setStartValue(self.windowOpacity())
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.Type.InCubic)
        a.finished.connect(self.hide)
        a.finished.connect(self._clear_content)
        a.start()
        self._anim = a

    def _on_close_clicked(self): 
        QApplication.quit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.glass.setGeometry(self.rect())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < HEADER_H:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _): self._drag_pos = None

    def closeEvent(self, e):
        e.accept(); os._exit(0)


# ── Public API (used by voice.py and ai.py) ────────────────────────────────────
class HUD:
    def __init__(self, app: QApplication):
        self._win = SentinelHUD()
        self._win.close_btn.clicked.disconnect()
        self._win.close_btn.clicked.connect(self._win.hide_hud)

    def load_sentences(self, sentences: list[str], title: str = "SENTINEL"):
        self._win.signals.set_title.emit(title)
        self._win.signals.load_sentences.emit(sentences)

    def begin_sentence(self, idx: int):
        self._win.signals.begin_sentence.emit(idx)

    def end_sentence(self, idx: int):
        self._win.signals.end_sentence.emit(idx)

    def finish_all(self):
        self._win.signals.finish_all.emit()

    def append_image(self, src: str):
        self._win.signals.show_image.emit(src)

    def set_title(self, title: str):
        self._win.signals.set_title.emit(title)

    def clear(self):
        self._win.signals.clear.emit()

    def close(self):
        self._win.signals.close_hud.emit()


# ── Demo ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app     = QApplication(sys.argv)
    hud_win = SentinelHUD()

    DEMO = [
        "Here are today's top tech stories:",
        "1. Google releases Gemma 4 — a new open-source model family available on Hugging Face.",
        "2. RTX 5090 rumoured to launch this quarter with 32GB VRAM and significant perf uplift.",
        "3. OpenAI confirms GPT-5 is in final testing, targeting a mid-year release window.",
        "Grab the latest details from each source's official blog for full specs.",
    ]

    def _demo():
        time.sleep(0.4)
        hud_win.signals.set_title.emit("SEARCH RESULTS")
        hud_win.signals.load_sentences.emit(DEMO)
        for i, _ in enumerate(DEMO):
            time.sleep(0.3)
            hud_win.signals.begin_sentence.emit(i)
            time.sleep(2.5)
            hud_win.signals.end_sentence.emit(i)
        time.sleep(0.5)
        hud_win.signals.finish_all.emit()

    threading.Thread(target=_demo, daemon=True).start()
    sys.exit(app.exec())