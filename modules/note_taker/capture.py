"""
capture.py — Screen capture utilities for Note Taker.
Handles region selection, screenshot diffing, diagram detection, and base64 encoding.
No LLM logic. No audio logic. Pure screen stuff.
"""

import hashlib
import base64
import os
import tkinter as tk
import numpy as np
from io import BytesIO
from PIL import Image, ImageGrab

from . import config


# ── Region selector ────────────────────────────────────────────────────────────
class RegionSelector:
    """
    Fullscreen overlay that lets the user drag a capture region.
    Returns (x, y, w, h) or None if cancelled.
    """
    def __init__(self):
        self.region = None
        self._start = None

    def select(self) -> tuple | None:
        root = tk.Tk()
        root.attributes("-fullscreen", True, "-alpha", 0.25, "-topmost", True)
        root.configure(cursor="crosshair", bg="black")

        canvas = tk.Canvas(root, bg="black", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_rectangle(0, 0, 0, 0, outline="#00FF99", width=2, fill="", tags="r")
        canvas.create_text(
            root.winfo_screenwidth() // 2, 40,
            text="Drag to select region  •  Esc to cancel",
            fill="white", font=("Segoe UI", 15),
        )

        def on_press(e):
            self._start = (e.x, e.y)

        def on_drag(e):
            canvas.coords("r", *self._start, e.x, e.y)

        def on_release(e):
            x = min(self._start[0], e.x)
            y = min(self._start[1], e.y)
            w = abs(e.x - self._start[0])
            h = abs(e.y - self._start[1])
            if w > 20 and h > 20:
                self.region = (x, y, w, h)
            root.destroy()

        canvas.bind("<ButtonPress-1>",   on_press)
        canvas.bind("<B1-Motion>",       on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        root.bind("<Escape>", lambda e: root.destroy())
        root.mainloop()
        return self.region


# ── Screenshot helpers ─────────────────────────────────────────────────────────
def capture(region: tuple) -> Image.Image:
    """Grab a PIL Image from the given (x, y, w, h) region."""
    x, y, w, h = region
    return ImageGrab.grab(bbox=(x, y, x + w, y + h))


def img_hash(img: Image.Image) -> str:
    """Fast perceptual hash — used to detect if the screen changed at all."""
    return hashlib.md5(
        img.resize((64, 64)).convert("L").tobytes()
    ).hexdigest()


def screen_changed(img_a: Image.Image, img_b: Image.Image) -> bool:
    """
    Returns True if the pixel diff between two screenshots exceeds
    CHANGE_THRESHOLD. Cheap 64x64 greyscale comparison.
    """
    da = np.array(img_a.resize((64, 64)).convert("L"), dtype=float)
    db = np.array(img_b.resize((64, 64)).convert("L"), dtype=float)
    return np.mean(np.abs(da - db) > 15) > config.CHANGE_THRESHOLD


def to_b64(img: Image.Image) -> str:
    """Resize to MAX_IMG_WIDTH and return a base64 PNG string for the LLM."""
    w = min(img.width, config.MAX_IMG_WIDTH)
    if img.width > w:
        img = img.resize((w, int(img.height * w / img.width)))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def is_diagram(img: Image.Image) -> bool:
    """
    Returns True if the image has enough colour diversity to be worth saving
    as a diagram screenshot. Uses unique pixel count on a 64x64 thumbnail.
    Avoids the Pillow 14 getdata() deprecation by converting to bytes first.
    """
    resized = img.resize((64, 64)).convert("RGB")
    # tobytes gives raw pixel data — wrap in tuples of 3 for unique colour count
    raw = resized.tobytes()
    pixels = [tuple(raw[i:i+3]) for i in range(0, len(raw), 3)]
    return len(set(pixels)) > config.DIAGRAM_THRESHOLD


def save_diagram(img: Image.Image, session_dir: str, idx: int) -> str:
    """
    Save a resized screenshot as diagram_NNN.png in the session directory.
    Returns the full file path.
    """
    path = os.path.join(session_dir, f"diagram_{idx:03d}.png")
    w = min(img.width, config.MAX_IMG_WIDTH)
    if img.width > w:
        img = img.resize((w, int(img.height * w / img.width)))
    img.save(path, "PNG")
    return path