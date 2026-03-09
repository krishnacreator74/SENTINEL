import tkinter as tk
import win32gui
import win32con
import ctypes
import math
import time

# ── Win32 ────────────────────────────────────────────────────────────────────
user32       = ctypes.windll.user32
LWA_COLORKEY = 0x00000001
CHROMA_HEX   = "#020202"
CHROMA_REF   = 0x00020202


def _apply_colorkey(hwnd):
    ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                           ex | win32con.WS_EX_LAYERED
                              | win32con.WS_EX_TOOLWINDOW
                              | win32con.WS_EX_NOACTIVATE)
    user32.SetLayeredWindowAttributes(hwnd, CHROMA_REF, 0, LWA_COLORKEY)


def _find_workerw():
    progman = win32gui.FindWindow("Progman", None)
    user32.SendMessageTimeoutW(progman, 0x052C, 0, 0,
                               win32con.SMTO_NORMAL, 1000, None)
    result = [None]

    def _cb(hwnd, _):
        defview = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
        if defview:
            ww = user32.FindWindowExW(0, hwnd, "WorkerW", None)
            if ww:
                result[0] = ww

    win32gui.EnumWindows(_cb, None)
    return result[0]


# ── Layout ───────────────────────────────────────────────────────────────────
N_BARS      = 7
BAR_W       = 3          # width of each bar
BAR_GAP     = 9          # gap between bars
BAR_SPACING = BAR_W + BAR_GAP
W           = N_BARS * BAR_SPACING + 20
H           = 60

_total      = N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
_start      = (W - _total) // 2
BAR_XS      = [_start + i * BAR_SPACING + BAR_W // 2 for i in range(N_BARS)]


class SentinelWidget:

    def __init__(self):
        self.state         = "idle"
        self.energy        = 0.0
        self.smooth_energy = 0.0

        self.root = tk.Tk()
        sw, sh    = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self._wx  = (sw - W) // 2
        self._wy  = sh - H - 48

        self.root.geometry(f"{W}x{H}+{self._wx}+{self._wy}")
        self.root.overrideredirect(True)
        self.root.configure(bg=CHROMA_HEX)
        self.root.attributes("-topmost", True)
        self.root.update()

        hwnd = self.root.winfo_id()
        _apply_colorkey(hwnd)
        self.root.wm_attributes("-transparentcolor", CHROMA_HEX)

        self.cv = tk.Canvas(self.root, width=W, height=H,
                            bg=CHROMA_HEX, highlightthickness=0)
        self.cv.pack()

        # One rounded bar per channel  (glow layer + sharp core)
        self._glow = []
        self._core = []
        cy = H // 2
        for x in BAR_XS:
            g = self.cv.create_rectangle(x - BAR_W - 1, cy - 3,
                                         x + BAR_W + 1, cy + 3,
                                         fill=CHROMA_HEX, outline="")
            c = self.cv.create_rectangle(x - BAR_W // 2, cy - 2,
                                         x + BAR_W // 2, cy + 2,
                                         fill=CHROMA_HEX, outline="")
            self._glow.append(g)
            self._core.append(c)

        self._cy = cy
        self.animate()
        self.root.after(600,  self._attach)
        self.root.after(1200, self._keep_alive)

    # ── API ──────────────────────────────────────────────────────────────────
    def set_idle(self):
        self.root.after(0, lambda: setattr(self, "state", "idle"))

    def set_speaking(self):
        self.root.after(0, lambda: setattr(self, "state", "speaking"))

    def set_energy(self, v):
        self.root.after(0, lambda: setattr(self, "energy",
                                           max(0.0, min(1.0, float(v)))))

    # ── Desktop ──────────────────────────────────────────────────────────────
    def _attach(self):
        self.root.update_idletasks()
        hwnd    = self.root.winfo_id()
        workerw = _find_workerw()
        if workerw:
            user32.SetParent(hwnd, workerw)
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE,
                                   (style & ~win32con.WS_POPUP) | win32con.WS_CHILD)
            _apply_colorkey(hwnd)
            win32gui.SetWindowPos(hwnd, None, self._wx, self._wy, W, H,
                                  win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW)
            print("[Sentinel] Embedded in WorkerW ✓")
        else:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            print("[Sentinel] TOPMOST fallback")

    def _keep_alive(self):
        try:
            hwnd = self.root.winfo_id()
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        except Exception:
            pass
        self.root.after(200, self._keep_alive)

    # ── Animation ────────────────────────────────────────────────────────────
    def animate(self):
        t        = time.time()
        cy       = self._cy
        speaking = self.state == "speaking"
        mid      = N_BARS // 2

        target_e           = self.energy if speaking else 0.0
        self.smooth_energy = self.smooth_energy * 0.80 + target_e * 0.20

        for i, x in enumerate(BAR_XS):
            dist = abs(i - mid) / mid   # 0=centre 1=edge

            if not speaking:
                # Idle: slow organic breath — centre taller, edges tiny dots
                breath = (math.sin(t * 1.6 + i * 0.9) * 0.5 + 0.5)  # 0-1
                h      = 2 + (1 - dist) * 3 + breath * 2
                # Soft white glow, semi-transparent feel via brightness
                alpha  = int(180 + (1 - dist) * 60)   # 180-240
                col    = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
                gcol   = f"#{max(0,alpha-80):02x}{max(0,alpha-80):02x}{max(0,alpha-80):02x}"

            else:
                # Speaking: fast reactive wave with centre bias
                se    = self.smooth_energy
                wave  = math.sin(t * 16 + i * 1.5) * 0.35
                env   = 1 - dist * 0.45
                h     = max(2, (se * 28 + wave * 10) * env)
                # Pure white core, soft white glow
                bv    = int(min(255, 210 + se * 45))
                col   = f"#{bv:02x}{bv:02x}{bv:02x}"
                gv    = int(bv * 0.45)
                gcol  = f"#{gv:02x}{gv:02x}{gv:02x}"

            top = cy - h
            bot = cy + h

            # Glow rect (wider, softer)
            self.cv.coords(self._glow[i],
                           x - BAR_W - 1, top - 2,
                           x + BAR_W + 1, bot + 2)
            # Core rect (sharp)
            self.cv.coords(self._core[i],
                           x - BAR_W,     top,
                           x + BAR_W,     bot)

            self.cv.itemconfig(self._glow[i], fill=gcol)
            self.cv.itemconfig(self._core[i], fill=col)

        self.root.after(30, self.animate)

    def run(self):
        self.root.mainloop()


# ── Demo ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import threading

    w = SentinelWidget()

    def _demo():
        time.sleep(2)
        w.set_speaking()
        for step in range(80):
            v = abs(math.sin(step * 0.18)) * 0.9 + 0.1
            w.set_energy(v)
            time.sleep(0.08)
        w.set_idle()

    threading.Thread(target=_demo, daemon=True).start()
    w.run()