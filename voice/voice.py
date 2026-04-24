"""
voice.py — Sentinel TTS

One job: synthesize a sentence with Piper, play it, keep HUD in sync.

ALL Qt interactions go through `bridge` signals — never direct cross-thread calls.

HUD contract (sentence-glow model):
  hud_begin_signal(idx)  — called BEFORE sd.play  (sentence lights up)
  hud_end_signal(idx)    — called AFTER  sd.wait  (sentence goes white)
"""

from piper import PiperVoice
import sounddevice as sd
import numpy as np

# Set by main.py after UIBridge is created
bridge = None

_last_energy = 0.0

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
    global _current_sentence_idx, _last_energy

    idx = _current_sentence_idx

    if bridge:
        bridge.state_signal.emit("speaking")
        bridge.energy_signal.emit(0.25)

    first_chunk = True

    for chunk in voice.synthesize(text):
        audio       = chunk.audio_float_array
        sample_rate = chunk.sample_rate

        # Signal HUD on the very first chunk (audio is about to start)
        if first_chunk:
            if bridge and idx >= 0:
                bridge.hud_begin_signal.emit(idx)
            first_chunk = False

        # ── Energy calculation ────────────────────────────────────────────────
        peak       = float(np.max(np.abs(audio)))
        rms        = float(np.sqrt(np.mean(audio ** 2)))
        raw_energy = (0.6 * peak + 0.4 * rms)
        raw_energy = raw_energy ** 0.4
        raw_energy = min(1.0, raw_energy * 20)

        # Two-pole smoothing: lag + transient boost
        smoothed       = 0.5 * _last_energy + 0.5 * raw_energy
        smoothed      += (raw_energy - _last_energy) * 0.2
        smoothed       = max(0.0, min(1.0, smoothed))
        _last_energy   = smoothed

        if bridge:
            bridge.energy_signal.emit(smoothed)

        sd.play(audio, sample_rate, blocking=True)

    # Sentence finished
    if bridge and idx >= 0:
        bridge.hud_end_signal.emit(idx)

    if bridge:
        bridge.energy_signal.emit(0.0)
        bridge.state_signal.emit("idle")