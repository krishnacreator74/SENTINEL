"""
audio.py — Audio capture and transcription for Note Taker.
Handles Whisper loading, loopback recording, and mic VAD listening.
No LLM logic. No screen logic. Pure audio.

Workers push transcribed strings into a shared queue.
Session reads from that queue whenever it needs speech context.
"""

import threading
import time
import warnings
import numpy as np

from . import config

# Suppress soundcard Windows audio buffer warnings — cosmetic only, no data loss
warnings.filterwarnings("ignore", module="soundcard")


# ── Whisper loader ─────────────────────────────────────────────────────────────
_whisper = None

def load_whisper():
    """
    Load the Whisper model once. Call this at startup.
    Exits the process if Whisper fails to load.
    """
    global _whisper
    print("[Whisper] Loading...")
    try:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_DTYPE,
        )
        print(f"[Whisper] {config.WHISPER_MODEL}/{config.WHISPER_DEVICE} ready.")
    except Exception as e:
        import sys
        sys.exit(f"[Whisper] Failed to load: {e}")


def transcribe(audio: np.ndarray, sr: int = 16000) -> str:
    """
    Run Whisper on a numpy float32 audio array.
    Returns cleaned transcript string, or empty string if nothing real was said.
    Resamples to 16kHz if needed.
    """
    if _whisper is None:
        raise RuntimeError("Whisper not loaded. Call load_whisper() first.")
    if audio is None or len(audio) == 0:
        return ""

    # Resample if needed
    if sr != 16000:
        try:
            import scipy.signal as sps
            audio = sps.resample(audio, int(len(audio) * 16000 / sr))
        except ImportError:
            pass  # best effort — whisper will handle it

    segs, _ = _whisper.transcribe(
        audio.astype(np.float32),
        language="en",
        vad_filter=True,
        vad_parameters={
            "threshold": 0.3,
            "min_speech_duration_ms": 100,
            "min_silence_duration_ms": 800,
        },
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
    )

    text = ""
    any_good = False
    for seg in segs:
        # Raised to 0.95 — was rejecting real speech at 0.85
        if seg.no_speech_prob > config.NO_SPEECH_PROB:
            continue
        cleaned = seg.text.strip().lower().strip(".,!?")
        if any(h in cleaned for h in config.WHISPER_HALLUCINATIONS):
            continue
        text += seg.text
        any_good = True

    if not any_good:
        return ""

    result = text.strip()
    if result.strip(".,!? ") in config.WHISPER_HALLUCINATIONS:
        return ""
    if len(result.strip()) < 2:
        return ""
    return result


# ── Loopback worker ────────────────────────────────────────────────────────────
def _find_loopback():
    """Find the system loopback audio device (speaker output capture)."""
    try:
        import soundcard as sc
        # Prefer explicit loopback devices
        lb = [m for m in sc.all_microphones(include_loopback=True)
              if getattr(m, "isloopback", False)]
        if lb:
            print(f"[Loopback] {lb[0].name}")
            return lb[0]
        # Fallback: Stereo Mix or similar
        for m in sc.all_microphones(include_loopback=True):
            if any(k in m.name.lower() for k in ("stereo mix", "what u hear", "loopback")):
                print(f"[Loopback] fallback: {m.name}")
                return m
        print("[Loopback] No loopback device found.")
        return None
    except ImportError:
        print("[Loopback] soundcard not installed — pip install soundcard")
        return None


class LoopbackWorker:
    """
    Records speaker output in chunks and pushes transcripts to the shared queue.
    Runs on its own daemon thread.
    """
    def __init__(self, queue, stop_event):
        self._q    = queue
        self._stop = stop_event
        self._dev  = _find_loopback()
        self._t    = threading.Thread(target=self._loop, daemon=True, name="Loopback")

    @property
    def available(self) -> bool:
        return self._dev is not None

    def start(self):
        if not self.available:
            print("[Loopback] skipped — no device.")
            return
        self._t.start()
        print("[Loopback] started.")

    def _loop(self):
        frames = config.LOOPBACK_CHUNK_S * config.LOOPBACK_SR
        with self._dev.recorder(samplerate=config.LOOPBACK_SR, channels=1) as rec:
            while not self._stop.is_set():
                try:
                    audio = rec.record(numframes=frames).flatten().astype(np.float32)
                    # Skip silent chunks — saves Whisper CPU
                    if np.sqrt(np.mean(audio ** 2)) < 0.0005:
                        continue
                    t = transcribe(audio, config.LOOPBACK_SR)
                    if t:
                        self._q.put(t.strip())
                except Exception:
                    time.sleep(1)


# ── Mic worker ─────────────────────────────────────────────────────────────────
class MicWorker:
    """
    Listens on the microphone using voice/ears.py if available,
    otherwise falls back to a simple VAD loop via sounddevice.
    Pushes transcripts to the shared queue.
    """
    def __init__(self, queue, stop_event):
        self._q      = queue
        self._stop   = stop_event
        self._listen = None
        self._t      = threading.Thread(target=self._loop, daemon=True, name="Mic")

        try:
            from voice.ears import listen
            self._listen = listen
            print("[Mic] voice/ears.py loaded.")
        except Exception as e:
            print(f"[Mic] ears.py unavailable ({e}), using raw VAD.")
            self._listen = self._raw_listen

    def start(self):
        self._t.start()
        print("[Mic] started.")

    def _loop(self):
        while not self._stop.is_set():
            try:
                t = self._listen()
                if t and t.strip():
                    print(f"[Mic] {t[:80]}")
                    self._q.put(t.strip())
            except Exception as e:
                print(f"[Mic error] {e}")
                time.sleep(1)

    def _raw_listen(self) -> str:
        """Simple VAD loop using sounddevice as fallback."""
        import sounddevice as sd
        SR    = 16000
        CHUNK = int(SR * 0.1)
        buf, started, silence, waited = [], False, 0, 0

        with sd.InputStream(samplerate=SR, channels=1, dtype="float32") as stream:
            for _ in range(450):
                chunk, _ = stream.read(CHUNK)
                chunk = chunk.flatten()
                rms   = float(np.sqrt(np.mean(chunk ** 2)))

                if not started:
                    if rms > config.MIC_RMS_FLOOR:
                        started = True
                        buf     = [chunk]
                    else:
                        waited += 1
                        if waited > 100:
                            return ""
                else:
                    buf.append(chunk)
                    if rms < 0.0005:
                        silence += 1
                        if silence >= 20 and len(buf) > 2:
                            break
                    else:
                        silence = 0

        if not buf:
            return ""
        return transcribe(np.concatenate(buf).astype(np.float32), SR)


# ── Worker factory ─────────────────────────────────────────────────────────────
def build_workers(queue, stop_event) -> list:
    """
    Build the correct set of audio workers based on CAPTURE_METHOD in config.
    Returns a list of started-ready worker instances.
    """
    workers = []
    method  = config.CAPTURE_METHOD

    if method in ("loopback", "both"):
        lb = LoopbackWorker(queue, stop_event)
        if lb.available:
            workers.append(lb)
        elif method == "loopback":
            print("[Audio] Loopback unavailable, falling back to mic.")
            workers.append(MicWorker(queue, stop_event))

    if method in ("mic", "both"):
        workers.append(MicWorker(queue, stop_event))

    return workers