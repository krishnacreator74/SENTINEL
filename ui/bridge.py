"""
bridge.py — Sentinel UI Bridge

All cross-thread → Qt calls go through here.
Never call widget/hud methods directly from a non-Qt thread.
"""

from PyQt6.QtCore import QObject, pyqtSignal


class UIBridge(QObject):
    # Widget state / energy
    speak_signal  = pyqtSignal(str)
    state_signal  = pyqtSignal(str)
    energy_signal = pyqtSignal(float)

    # HUD — full sentence-glow contract
    hud_load_signal   = pyqtSignal(list, str)   # (sentences, title)
    hud_begin_signal  = pyqtSignal(int)          # sentence idx → active
    hud_end_signal    = pyqtSignal(int)          # sentence idx → past
    hud_finish_signal = pyqtSignal()             # mark all past
    hud_clear_signal  = pyqtSignal()
    hud_close_signal  = pyqtSignal()
    hud_title_signal  = pyqtSignal(str)
    hud_image_signal  = pyqtSignal(str)
    game_mode_signal  = pyqtSignal(bool)

    # Chat update (request, response)
    chat_signal = pyqtSignal(str, str)