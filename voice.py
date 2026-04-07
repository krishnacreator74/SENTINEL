"""
voice.py — Sentinel TTS

One job: synthesize a sentence with Piper, play it, keep HUD in sync.

HUD contract (sentence-glow model):
  hud.begin_sentence(idx)  — called BEFORE sd.play  (sentence lights up)
  hud.end_sentence(idx)    — called AFTER  sd.wait  (sentence goes white)

No word indices. No timing guesses. No cross-module state.
"""

from piper import PiperVoice
import sounddevice as sd
import numpy as np
import threading
import re

widget = None
hud    = None   # set by main.py

voice = PiperVoice.load(
    model_path="voice_models/en_US-hfc_female-medium.onnx",
    config_path="voice_models/en_US-hfc_female-medium.onnx.json"
)

# Current sentence index — set by ai.py before each voice_of_ai call
_current_sentence_idx: int = -1

def set_sentence_idx(idx: int):
    """ai.py calls this before each sentence so voice.py can sync the HUD."""
    global _current_sentence_idx
    _current_sentence_idx = idx


def voice_of_ai(text: str):
    """Synthesize and play one sentence. Drives HUD begin/end around playback."""
    global _current_sentence_idx

    if widget:
        widget.set_speaking()

    chunks = list(voice.synthesize(text))
    if not chunks:
        if widget:
            widget.set_idle()
        return

    audio = np.concatenate([c.audio_float_array for c in chunks])
    sample_rate = chunks[0].sample_rate
    idx = _current_sentence_idx

    # Tell HUD this sentence is active — BEFORE playback starts
    if hud and idx >= 0:
        hud.begin_sentence(idx)

    sd.play(audio, sample_rate)
    sd.wait()

    # Tell HUD this sentence is done — AFTER audio finishes
    if hud and idx >= 0:
        hud.end_sentence(idx)

    if widget:
        widget.set_idle()