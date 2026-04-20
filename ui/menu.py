"""
menu.py — Sentinel radial arc menu

Uses same Win32 UpdateLayeredWindow approach as widget.py for true transparency.
QWindow instead of QWidget — no Qt compositor involvement.

4 items fan in a curved arc upward from the widget circle.
Hover: glow boost + label fades in.
Click: triggers action, menu closes.
"""

import math
import ctypes
from ctypes import windll, byref, c_int, Structure

from PyQt6.QtGui import QWindow
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen, QBrush, QPainterPath, QFont, QImage

# ── Win32 (shared with widget.py pattern) ────────────────────────────────────
class POINT(Structure):
    _fields_ = [("x", c_int), ("y", c_int)]

class SIZE(Structure):
    _fields_ = [("cx", c_int), ("cy", c_int)]

class BLENDFUNCTION(Structure):
    _fields_ = [
        ("BlendOp",             ctypes.c_byte),
        ("BlendFlags",          ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat",         ctypes.c_byte),
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize",          ctypes.c_uint32),
        ("biWidth",         ctypes.c_int32),
        ("biHeight",        ctypes.c_int32),
        ("biPlanes",        ctypes.c_uint16),
        ("biBitCount",      ctypes.c_uint16),
        ("biCompression",   ctypes.c_uint32),
        ("biSizeImage",     ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed",       ctypes.c_uint32),
        ("biClrImportant",  ctypes.c_uint32),
    ]

WS_EX_LAYERED             = 0x00080000
WS_EX_TOOLWINDOW          = 0x00000080
WS_EX_NOACTIVATE          = 0x08000000
WS_EX_NOREDIRECTIONBITMAP = 0x00200000
ULW_ALPHA                 = 0x00000002
AC_SRC_OVER               = 0x00
AC_SRC_ALPHA              = 0x01

_gdi32  = windll.gdi32
_user32 = windll.user32

# ── Layout ────────────────────────────────────────────────────────────────────
ITEM_R     = 18
ARC_DIST   = 72
ARC_SPREAD = 120
STAGGER_MS = 65
OPEN_MS    = 220
CLOSE_MS   = 160

MW  = 260
MH  = 220
MCX = MW / 2.0
MCY = MH - 30.0


def _lerp(a, b, t):
    return a + (b - a) * t

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _item_angles(n, spread_deg):
    if n == 1:
        return [90.0]
    step  = spread_deg / (n - 1)
    start = 90.0 + spread_deg / 2.0
    return [start - i * step for i in range(n)]


# ── Icon painters ─────────────────────────────────────────────────────────────
def _icon_chat(p, cx, cy, size, col):
    p.setPen(QPen(col, 1.5, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s    = size * 0.55
    rect = QRectF(cx - s, cy - s * 0.9, s * 2, s * 1.6)
    path = QPainterPath()
    path.addRoundedRect(rect, s * 0.35, s * 0.35)
    p.drawPath(path)
    tail = QPainterPath()
    tx   = cx - s * 0.1
    ty   = cy + s * 0.7
    tail.moveTo(tx, ty)
    tail.lineTo(tx - s * 0.35, ty + s * 0.45)
    tail.lineTo(tx + s * 0.3,  ty)
    p.drawPath(tail)

def _icon_gamepad(p, cx, cy, size, col):
    p.setPen(QPen(col, 1.5, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s    = size * 0.5
    body = QRectF(cx - s, cy - s * 0.5, s * 2, s)
    path = QPainterPath()
    path.addRoundedRect(body, s * 0.4, s * 0.4)
    p.drawPath(path)
    p.drawLine(QPointF(cx - s * 0.55, cy), QPointF(cx - s * 0.25, cy))
    p.drawEllipse(QPointF(cx + s * 0.5,  cy - s * 0.1), s * 0.12, s * 0.12)
    p.drawEllipse(QPointF(cx + s * 0.7,  cy + s * 0.1), s * 0.10, s * 0.10)

def _icon_settings(p, cx, cy, size, col):
    p.setPen(QPen(col, 1.4, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s     = size * 0.48
    teeth = 6
    path  = QPainterPath()
    for i in range(teeth * 2):
        angle = math.radians(i * 180.0 / teeth)
        r     = s if i % 2 == 0 else s * 0.62
        x     = cx + math.cos(angle) * r
        y     = cy + math.sin(angle) * r
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    p.drawPath(path)
    p.drawEllipse(QPointF(cx, cy), s * 0.28, s * 0.28)

def _icon_exit(p, cx, cy, size, col):
    p.setPen(QPen(col, 2.0, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    s = size * 0.38
    p.drawLine(QPointF(cx - s, cy - s), QPointF(cx + s, cy + s))
    p.drawLine(QPointF(cx + s, cy - s), QPointF(cx - s, cy + s))


ITEMS = [
    {"label": "Chat",      "icon": _icon_chat,     "action": "chat"},
    {"label": "Game Mode", "icon": _icon_gamepad,  "action": "game"},
    {"label": "Settings",  "icon": _icon_settings, "action": "settings"},
    {"label": "Exit",      "icon": _icon_exit,     "action": "exit"},
]
ANGLES = _item_angles(len(ITEMS), ARC_SPREAD)


# ── Main menu window ──────────────────────────────────────────────────────────
class SentinelMenu(QWindow):

    def _init_gdi(self):
            self._hdc_screen = _user32.GetDC(0)
            self._hdc_mem    = _gdi32.CreateCompatibleDC(self._hdc_screen)
            bmi = BITMAPINFOHEADER(
                biSize=40, biWidth=MW, biHeight=-MH,
                biPlanes=1, biBitCount=32, biCompression=0,
                biSizeImage=0, biXPelsPerMeter=0, biYPelsPerMeter=0,
                biClrUsed=0, biClrImportant=0,
            )
            self._ppv = ctypes.c_void_p()
            self._hbm = _gdi32.CreateDIBSection(
                self._hdc_mem, ctypes.byref(bmi), 0,
                ctypes.byref(self._ppv), None, 0
            )
            _gdi32.SelectObject(self._hdc_mem, self._hbm)
            self._img       = QImage(MW, MH, QImage.Format.Format_ARGB32_Premultiplied)
            self._gdi_ready = True

    def __init__(self, widget_ref, chat_win_ref):
        super().__init__()
        self._widget   = widget_ref
        self._chat_win = chat_win_ref

        self._open      = False
        self._animating = False
        self._progress  = [0.0] * len(ITEMS)
        self._hovered   = -1
        self._hover_a   = [0.0] * len(ITEMS)
        self._label_a   = [0.0] * len(ITEMS)
        self._sched_timers = []
        self._hdc_screen = None
        self._hdc_mem    = None
        self._hbm        = None
        self._ppv        = None
        self._gdi_ready  = False

        # QWindow setup — same pattern as widget.py
        self.setFlag(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.resize(MW, MH)

        # Animation + hover tick
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        # Mouse tracking via event filter on app
        QApplication.instance().installEventFilter(self)

        self.hide()

    # ── Win32 layered init (called after show()) ──────────────────────────────
    def _init_layered(self):
        hwnd = int(self.winId())
        if not hwnd:
            return
        ex = _user32.GetWindowLongW(hwnd, -20)
        _user32.SetWindowLongW(hwnd, -20,
            ex | WS_EX_LAYERED | WS_EX_TOOLWINDOW
               | WS_EX_NOACTIVATE | WS_EX_NOREDIRECTIONBITMAP
        )
        self._init_gdi()
        self._blit_layered()

    # ── Core render → Win32 surface ───────────────────────────────────────────
    def _blit_layered(self):
        hwnd = int(self.winId())
        if not hwnd or not self._gdi_ready:
            return

        self._img.fill(QColor(0, 0, 0, 0))
        p = QPainter(self._img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_menu(p)
        p.end()

        ptr = self._img.bits()
        ptr.setsize(MW * MH * 4)
        ctypes.memmove(self._ppv, ctypes.c_void_p(int(ptr)), MW * MH * 4)

        blend = BLENDFUNCTION()
        blend.BlendOp             = AC_SRC_OVER
        blend.BlendFlags          = 0
        blend.SourceConstantAlpha = 255
        blend.AlphaFormat         = AC_SRC_ALPHA

        geo = self.geometry()
        dst = POINT(geo.x(), geo.y())
        src = POINT(0, 0)
        sz  = SIZE(MW, MH)

        _user32.UpdateLayeredWindow(
            hwnd, self._hdc_screen,
            byref(dst), byref(sz),
            self._hdc_mem, byref(src),
            0, byref(blend), ULW_ALPHA
        )

    # ── Menu painter ─────────────────────────────────────────────────────────
    def _paint_menu(self, p: QPainter):
        for i, item in enumerate(ITEMS):
            prog = self._progress[i]
            if prog <= 0.01:
                continue

            ix, iy = self._item_pos(i)
            ha     = self._hover_a[i]
            la     = self._label_a[i]
            scale  = prog

            p.save()
            p.translate(ix, iy)
            p.scale(scale, scale)

            # Outer glow
            glow_a = int(_lerp(35, 120, ha))
            glow_r = ITEM_R + _lerp(4, 10, ha)
            grad   = QRadialGradient(QPointF(0, 0), glow_r)
            grad.setColorAt(0.0, QColor(82, 183, 255, glow_a))
            grad.setColorAt(0.6, QColor(82, 183, 255, glow_a // 4))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(0, 0), glow_r, glow_r)

            # Circle fill
            p.setBrush(QBrush(QColor(12, 18, 28, int(_lerp(210, 235, ha)))))
            p.setPen(QPen(QColor(82, 183, 255, int(_lerp(100, 220, ha))),
                          _lerp(1.2, 2.0, ha)))
            p.drawEllipse(QPointF(0, 0), ITEM_R, ITEM_R)

            # Icon
            icon_col = QColor(
                int(_lerp(180, 255, ha)),
                int(_lerp(220, 255, ha)),
                255,
                int(_lerp(200, 255, ha)),
            )
            item["icon"](p, 0, 0, ITEM_R, icon_col)

            p.restore()

            # Label
            if la > 0.15:
                angle_rad  = math.radians(ANGLES[i])
                label_dist = ITEM_R + 10
                lx = ix + math.cos(angle_rad) * label_dist * scale
                ly = iy - math.sin(angle_rad) * label_dist * scale

                font = QFont("Segoe UI", 9)
                font.setWeight(QFont.Weight.Medium)
                p.setFont(font)
                p.setPen(QColor(200, 225, 255, int(la * 220)))

                fm = p.fontMetrics()
                tw = fm.horizontalAdvance(item["label"])

                if ANGLES[i] > 135:
                    tx = lx - tw - 4
                elif ANGLES[i] < 45:
                    tx = lx + 4
                else:
                    tx = lx - tw / 2

                ty = ly - fm.height() - 4
                p.drawText(int(tx), int(ty), item["label"])

    # ── paintEvent — Win32 owns the surface ───────────────────────────────────
    def paintEvent(self, _):
        pass

    # ── Positioning ───────────────────────────────────────────────────────────
    def _reposition(self):
        wg = self._widget.geometry()
        wx = wg.x() + wg.width()  // 2
        wy = wg.y() + wg.height() // 2
        self.setPosition(int(wx - MCX), int(wy - MCY))

    def _item_pos(self, idx):
        angle_rad = math.radians(ANGLES[idx])
        dist      = ARC_DIST * self._progress[idx]
        x = MCX + math.cos(angle_rad) * dist
        y = MCY - math.sin(angle_rad) * dist
        return x, y

    # ── Open / close ──────────────────────────────────────────────────────────
    def toggle(self):
        if self._animating:
            return
        if not self._open:
            self._do_open()
        else:
            self._do_close()

    def force_close(self):
        if self._open or self._animating:
            self._do_close()

    def _do_open(self):
        self._open      = True
        self._animating = True
        self._reposition()
        self.show()
        self.raise_()
        QTimer.singleShot(50, self._init_layered)

        for t in self._sched_timers:
            t.stop()
        self._sched_timers.clear()

        for i in range(len(ITEMS)):
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda ix=i: self._animate_item_open(ix))
            t.start(i * STAGGER_MS)
            self._sched_timers.append(t)

        total = (len(ITEMS) - 1) * STAGGER_MS + OPEN_MS + 50
        QTimer.singleShot(total, lambda: setattr(self, "_animating", False))

    def _do_close(self):
        self._animating = True
        for t in self._sched_timers:
            t.stop()
        self._sched_timers.clear()

        n = len(ITEMS)
        for i in range(n):
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda ix=i: self._animate_item_close(ix))
            t.start((n - 1 - i) * STAGGER_MS)
            self._sched_timers.append(t)

        QTimer.singleShot((n - 1) * STAGGER_MS + CLOSE_MS + 50, self._finish_close)

    def _finish_close(self):
        self._open      = False
        self._animating = False
        self._hovered   = -1
        self.hide()

    # ── Per-item animation ────────────────────────────────────────────────────
    def _animate_item_open(self, idx):
        self._progress[idx] = 0.0
        dur = OPEN_MS

        def _step(elapsed=[0]):
            elapsed[0] += 16
            raw = _clamp(elapsed[0] / dur, 0.0, 1.0)
            self._progress[idx] = 1 - (1 - raw) ** 3
            if raw < 1.0:
                QTimer.singleShot(16, _step)

        _step()

    def _animate_item_close(self, idx):
        dur = CLOSE_MS

        def _step(elapsed=[0]):
            elapsed[0] += 16
            raw = _clamp(elapsed[0] / dur, 0.0, 1.0)
            self._progress[idx] = 1.0 - (1 - (1 - raw) ** 3)
            if raw < 1.0:
                QTimer.singleShot(16, _step)

        _step()

    # ── Tick — hover lerp + blit ──────────────────────────────────────────────
    def _tick(self):
        changed = False
        for i in range(len(ITEMS)):
            target = 1.0 if i == self._hovered else 0.0
            new_h = _lerp(self._hover_a[i], target, 0.12)
            new_l = _lerp(self._label_a[i], target, 0.10)
            if new_h < 0.01:
                new_h = 0.0
            if new_l < 0.01:
                new_l = 0.0
            if new_h != self._hover_a[i] or new_l != self._label_a[i]:
                self._hover_a[i] = new_h
                self._label_a[i] = new_l
                changed = True

        if (changed or self._animating or self._open) and self.isVisible():
            self._blit_layered()

    # ── Mouse via event filter (QWindow doesn't get mouseMoveEvent reliably) ──
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if not self.isVisible():
            return False

        if event.type() == QEvent.Type.MouseMove:
            gp    = event.globalPosition().toPoint()
            geo   = self.geometry()
            local = gp - geo.topLeft()
            mx, my = local.x(), local.y()

            self._hovered = -1
            for i in range(len(ITEMS)):
                if self._progress[i] < 0.5:
                    continue
                ix, iy = self._item_pos(i)
                dx, dy = mx - ix, my - iy
                if math.sqrt(dx*dx + dy*dy) <= ITEM_R + 4:
                    self._hovered = i
                    break

        elif event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                gp    = event.globalPosition().toPoint()
                geo   = self.geometry()
                local = gp - geo.topLeft()
                mx, my = local.x(), local.y()

                # Check if click is on any item
                hit = -1
                for i in range(len(ITEMS)):
                    if self._progress[i] < 0.5:
                        continue
                    ix, iy = self._item_pos(i)
                    dx, dy = mx - ix, my - iy
                    if math.sqrt(dx*dx + dy*dy) <= ITEM_R + 4:
                        hit = i
                        break

                if self._open:
                    if hit >= 0:
                        action = ITEMS[hit]["action"]
                        self._do_close()
                        QTimer.singleShot(180, lambda: self._run_action(action))
                    else:
                        # Click outside menu — close
                        in_menu = (0 <= mx <= MW and 0 <= my <= MH)
                        if not in_menu:
                            self._do_close()

        return False

    # ── Actions ───────────────────────────────────────────────────────────────
    def _run_action(self, action):
        if action == "chat":
            if self._chat_win is not None:
                if not self._widget._chat_open:
                    self._widget._chat_open = True
                    self._chat_win.show_animated()
                else:
                    self._widget._chat_open = False
                    self._chat_win.close_window()

        elif action == "game":
            self._widget.set_game_mode(True)

        elif action == "settings":
            print("[Menu] Settings — placeholder")

        elif action == "exit":
            QApplication.instance().quit()