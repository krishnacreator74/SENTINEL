"""
widget.py — Sentinel ambient circle widget

Uses Win32 UpdateLayeredWindow for per-pixel alpha transparency.
GDI resources (DIB section, DCs) are created once and reused every frame
for maximum performance — no per-frame allocation.

States:
  idle      → dim, organic breath, slow colour drift
  listening → brightens over ~400ms, steady pulse
  speaking  → energy-reactive, wakes up/cools smoothly
"""

import math
import time
import ctypes
from ctypes import windll, byref, c_int, Structure

from PyQt6.QtGui import QWindow
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen, QBrush, QImage

# ── Win32 types ───────────────────────────────────────────────────────────────
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

# ── Geometry ──────────────────────────────────────────────────────────────────
W      = 80
H      = 80
CX     = W / 2.0
CY     = H / 2.0
R_BASE = 14.0

# ── Timing ────────────────────────────────────────────────────────────────────
FRAME_MS       = 16
CLICK_COOLDOWN = 0.8

# ── Lerp speeds ───────────────────────────────────────────────────────────────
LERP_FAST   = 0.08
LERP_MEDIUM = 0.05
LERP_SLOW   = 0.025


def _lerp(a, b, t):
    return a + (b - a) * t

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _noise_breath(phase):
    a = math.sin(phase * 0.97)  * 0.50
    b = math.sin(phase * 1.73)  * 0.30
    c = math.sin(phase * 2.618) * 0.20
    return (a + b + c) * 0.5 + 0.5


class SentinelWidget(QWindow):

    clicked = pyqtSignal()

    def __init__(self):
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication must exist before SentinelWidget")
        super().__init__()

        # State
        self.state     = "idle"
        self.energy    = 0.0
        self._smooth_e = 0.0

        # Lerped display params
        self._d_core_a  = 50.0
        self._d_glow_a  = 15.0
        self._d_inner_a = 25.0
        self._d_r_halo  = R_BASE + 4
        self._d_ring_w  = 1.2
        self._d_col_r   = 82.0
        self._d_col_g   = 183.0
        self._d_col_b   = 255.0
        self._d_squish  = 0.0

        # Animation
        self._phase       = 0.0
        self._drift_phase = 0.0
        self._squish_vel  = 0.0

        # Click / menu
        self._menu       = None
        self._chat_open  = False
        self._last_click = 0.0
        self._game_mode  = False

        # GDI resources — created once in _init_gdi
        self._hdc_screen = None
        self._hdc_mem    = None
        self._hbm        = None
        self._ppv        = None
        self._img        = None
        self._gdi_ready  = False

        # Window
        self.setFlag(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.resize(W, H)

        screen = QApplication.primaryScreen().geometry()
        self.setPosition((screen.width() - W) // 2, screen.height() - H - 40)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(FRAME_MS)

        self.show()
        QTimer.singleShot(50, self._init_layered)

    # ── Win32 setup ───────────────────────────────────────────────────────────
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

    def _init_gdi(self):
        self._hdc_screen = _user32.GetDC(0)
        self._hdc_mem    = _gdi32.CreateCompatibleDC(self._hdc_screen)
        bmi = BITMAPINFOHEADER(
            biSize=40, biWidth=W, biHeight=-H,
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
        self._img      = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
        self._gdi_ready = True

    # ── Core render → Win32 surface ───────────────────────────────────────────
    def _blit_layered(self):
        hwnd = int(self.winId())
        if not hwnd or not self._gdi_ready:
            return

        self._img.fill(QColor(0, 0, 0, 0))
        p = QPainter(self._img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_circle(p)
        p.end()

        ptr = self._img.bits()
        ptr.setsize(W * H * 4)
        ctypes.memmove(self._ppv, ctypes.c_void_p(int(ptr)), W * H * 4)

        blend = BLENDFUNCTION()
        blend.BlendOp             = AC_SRC_OVER
        blend.BlendFlags          = 0
        blend.SourceConstantAlpha = 255
        blend.AlphaFormat         = AC_SRC_ALPHA

        geo = self.geometry()
        dst = POINT(geo.x(), geo.y())
        src = POINT(0, 0)
        sz  = SIZE(W, H)

        _user32.UpdateLayeredWindow(
            hwnd, self._hdc_screen,
            byref(dst), byref(sz),
            self._hdc_mem, byref(src),
            0, byref(blend), ULW_ALPHA
        )

    # ── Circle painter ────────────────────────────────────────────────────────
    def _paint_circle(self, p: QPainter):
        ca = int(_clamp(self._d_core_a,  0, 255))
        ga = int(_clamp(self._d_glow_a,  0, 255))
        ia = int(_clamp(self._d_inner_a, 0, 255))
        rh = self._d_r_halo
        rw = self._d_ring_w
        cr = int(_clamp(self._d_col_r, 0, 255))
        cg = int(_clamp(self._d_col_g, 0, 255))
        cb = int(_clamp(self._d_col_b, 0, 255))
        sq = self._d_squish

        center  = QPointF(CX, CY)
        rx_ring = R_BASE * (1.0 + sq)
        ry_ring = R_BASE * (1.0 - sq * 0.5)

        # Layer 1 — outer halo
        g1 = QRadialGradient(center, rh)
        g1.setColorAt(0.0, QColor(cr, cg, cb, ga))
        g1.setColorAt(0.5, QColor(cr, cg, cb, ga // 4))
        g1.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(g1))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, rh, rh)

        # Layer 2 — inner fill glow
        g2 = QRadialGradient(QPointF(CX, CY - 2), R_BASE * 0.75)
        g2.setColorAt(0.0, QColor(255, 255, 255, ia))
        g2.setColorAt(0.5, QColor(cr, cg, cb, ia // 2))
        g2.setColorAt(1.0, QColor(cr, cg, cb, 0))
        p.setBrush(QBrush(g2))
        p.drawEllipse(
            QRectF(CX - rx_ring + 2, CY - ry_ring + 2,
                   (rx_ring - 2) * 2, (ry_ring - 2) * 2)
        )

        # Layer 3 — core ring
        pen = QPen(QColor(cr, cg, cb, ca), rw)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(
            QRectF(CX - rx_ring, CY - ry_ring,
                   rx_ring * 2, ry_ring * 2)
        )

        # Layer 4 — specular glint
        g3 = QRadialGradient(QPointF(CX - 5, CY - 7), 5)
        g3.setColorAt(0.0, QColor(255, 255, 255, ca // 3))
        g3.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(g3))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(CX - 5, CY - 7), 5, 5)

    # ── Tick ──────────────────────────────────────────────────────────────────
    def _tick(self):
        dt = FRAME_MS / 1000.0
        self._phase       += dt
        self._drift_phase += dt * 0.12

        s = self.state
        e_target       = self.energy if s == "speaking" else 0.0
        self._smooth_e = _lerp(self._smooth_e, e_target, LERP_FAST)
        e = self._smooth_e

        if s == "idle":
            b     = _noise_breath(self._phase * 0.7)
            drift = math.sin(self._drift_phase) * 0.5 + 0.5
            t_r, t_g, t_b = 82 + drift * 20, 183 + drift * 25, 255
            t_core_a  = 45  + b * 35
            t_glow_a  = 12  + b * 14
            t_inner_a = 22  + b * 22
            t_r_halo  = R_BASE + 3 + b * 5
            t_ring_w  = 1.1
            t_squish  = 0.0
            spd       = LERP_MEDIUM

        elif s == "listening":
            b     = _noise_breath(self._phase * 1.8)
            t_r, t_g, t_b = 100, 210, 255
            t_core_a  = 130 + b * 75
            t_glow_a  = 40  + b * 45
            t_inner_a = 60  + b * 55
            t_r_halo  = R_BASE + 6 + b * 10
            t_ring_w  = 1.5
            t_squish  = b * 0.04
            spd       = LERP_FAST

        else:  # speaking
            b     = _noise_breath(self._phase * 4.5)
            blend = e * 0.4
            t_r   = 82  + blend * (200 - 82)
            t_g   = 183 + blend * (100 - 183)
            t_b   = 255
            boost     = e * 0.7 + b * 0.3
            t_core_a  = 160 + boost * 90
            t_glow_a  = 50  + boost * 90
            t_inner_a = 80  + boost * 120
            t_r_halo  = R_BASE + 9 + boost * 16
            t_ring_w  = 1.5 + boost * 0.5
            if e > 0.5:
                self._squish_vel += (e - 0.5) * 0.08
            t_squish = 0.0
            spd      = LERP_FAST

        # Squish spring
        spring_k = 18.0
        damping  = 6.5
        err      = self._d_squish - t_squish
        self._squish_vel += (-spring_k * err - damping * self._squish_vel) * dt
        self._d_squish   += self._squish_vel * dt
        self._d_squish    = _clamp(self._d_squish, -0.06, 0.10)

        decay = LERP_SLOW if (s == "idle" and self._d_core_a > 80) else spd

        self._d_core_a  = _lerp(self._d_core_a,  t_core_a,  decay)
        self._d_glow_a  = _lerp(self._d_glow_a,  t_glow_a,  decay)
        self._d_inner_a = _lerp(self._d_inner_a, t_inner_a, decay)
        self._d_r_halo  = _lerp(self._d_r_halo,  t_r_halo,  spd)
        self._d_ring_w  = _lerp(self._d_ring_w,  t_ring_w,  spd)
        self._d_col_r   = _lerp(self._d_col_r,   t_r,       spd)
        self._d_col_g   = _lerp(self._d_col_g,   t_g,       spd)
        self._d_col_b   = _lerp(self._d_col_b,   t_b,       spd)

        self._blit_layered()

    # ── paintEvent — Win32 owns the surface ───────────────────────────────────
    def paintEvent(self, _):
        pass

    # ── Click ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        dx = event.position().x() - CX
        dy = event.position().y() - CY
        if math.sqrt(dx * dx + dy * dy) > R_BASE + 20:
            return
        now = time.perf_counter()
        if now - self._last_click < CLICK_COOLDOWN:
            return
        self._last_click = now
        if self._menu is not None:
            self._menu.toggle()

    # ── Public API ────────────────────────────────────────────────────────────
    def set_idle(self):
        self.state = "idle"

    def set_listening(self):
        self.state = "listening"

    def set_speaking(self):
        self.state = "speaking"

    def set_energy(self, v: float):
        self.energy = _clamp(float(v), 0.0, 1.0)

    def set_game_mode(self, on: bool):
        self._game_mode = on
        self.hide() if on else self.show()

    def set_menu(self, menu):
        self._menu = menu

    def on_chat_closed_externally(self):
        self._chat_open = False

    def run(self):
        QApplication.instance().exec()


# ── Standalone demo ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import threading

    app = QApplication(sys.argv)
    w   = SentinelWidget()

    def _demo():
        time.sleep(2)
        print("→ listening")
        w.set_listening()
        time.sleep(4)
        print("→ speaking")
        w.set_speaking()
        for i in range(200):
            v = (abs(math.sin(i * 0.12)) * 0.7
                 + abs(math.sin(i * 0.31)) * 0.2
                 + abs(math.sin(i * 0.07)) * 0.1)
            w.set_energy(min(1.0, v))
            time.sleep(0.04)
        print("→ idle")
        w.set_idle()
        w.set_energy(0)

    threading.Thread(target=_demo, daemon=True).start()
    sys.exit(app.exec())