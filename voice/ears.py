import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

model = WhisperModel("medium", device="cuda", compute_type="int8")

HALLUCINATIONS = {
    "thanks for watching", "thank you for watching",
    "please subscribe", "like and subscribe",
    "see you next time", "bye", "goodbye", ".",
}

import threading

def input_with_timeout(prompt, timeout=5):
    user_input = [None]

    def get_input():
        try:
            user_input[0] = input(prompt)
        except:
            pass

    t = threading.Thread(target=get_input, daemon=True)
    t.start()
    t.join(timeout)

    return user_input[0]


def pick_device(timeout=5):
    devices = sd.query_devices()

    print("\n=== Available Input Devices ===")
    valid_indices = []
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            print(f"  [{i}] {d['name']}")
            valid_indices.append(i)

    default_idx = sd.default.device[0]
    print("================================")
    print(f"Default: [{default_idx}] {devices[default_idx]['name']}")

    choice = input_with_timeout(
        f"Enter device number (auto-select in {timeout}s): ",
        timeout
    )

    if choice and choice.strip().isdigit():
        return int(choice.strip())

    print(f"\n[Auto] Using default device: {devices[default_idx]['name']}")
    return None
_DEVICE = pick_device()

_SPEECH_THRESH  = 0.001
_SILENCE_THRESH = 0.0005

def set_thresholds(speech, silence):
    global _SPEECH_THRESH, _SILENCE_THRESH
    _SPEECH_THRESH  = speech
    _SILENCE_THRESH = silence

def listen():
    sample_rate    = 16000
    chunk_duration = 0.1
    chunk_samples  = int(sample_rate * chunk_duration)

    speech_thresh  = _SPEECH_THRESH
    silence_thresh = _SILENCE_THRESH

    pre_roll_n   = int(0.4  / chunk_duration)   # 4 chunks
    silence_n    = int(1.8  / chunk_duration)   # 18 chunks — was 10, longer pause tolerance
    min_speech_n = 2
    max_wait_n   = int(10.0 / chunk_duration)   # 100 chunks before any speech
    max_n        = int(45.0 / chunk_duration)   # 450 chunks — was 300, allow longer sentences

    print(f"Listening...  (thresh={speech_thresh:.5f})")

    pre_roll_buf   = []
    speech_buf     = []
    silence_count  = 0
    speech_count   = 0
    speech_started = False
    waited         = 0

    with sd.InputStream(samplerate=sample_rate, channels=1,
                        dtype="float32", device=_DEVICE) as stream:

        for _ in range(max_n):
            chunk, _ = stream.read(chunk_samples)
            chunk    = chunk.flatten()
            rms      = float(np.sqrt(np.mean(chunk ** 2)))

            if not speech_started:
                pre_roll_buf.append(chunk)
                if len(pre_roll_buf) > pre_roll_n:
                    pre_roll_buf.pop(0)

                if rms > speech_thresh:
                    print(f"[listen] Speech started  rms={rms:.5f}")
                    speech_buf     = list(pre_roll_buf)
                    speech_started = True
                    speech_count   = 1
                    silence_count  = 0
                else:
                    waited += 1
                    if waited >= max_wait_n:
                        print(f"[listen] Timeout. rms={rms:.5f}")
                        return ""
            else:
                speech_buf.append(chunk)

                if rms > silence_thresh:
                    speech_count  += 1
                    silence_count  = 0
                else:
                    silence_count += 1

                # Progressive silence threshold — the more speech we have,
                # the longer we wait before cutting off.
                # Short utterance (<2s): 1.8s silence to end
                # Long utterance (>5s): 2.5s silence to end
                speech_seconds = speech_count * chunk_duration
                if speech_seconds > 5.0:
                    effective_silence_n = int(2.5 / chunk_duration)  # 25 chunks
                else:
                    effective_silence_n = silence_n                   # 18 chunks

                if silence_count >= effective_silence_n and speech_count >= min_speech_n:
                    break

    if not speech_buf or speech_count < min_speech_n:
        return ""

    audio = np.concatenate(speech_buf)
    duration = len(audio) / sample_rate
    print(f"[listen] {duration:.1f}s  rms={np.sqrt(np.mean(audio**2)):.5f}  speech_chunks={speech_count}")

    segments, info = model.transcribe(
        audio,
        language="en",
        vad_filter=True,              # let Whisper's own VAD help on long clips
        vad_parameters={
            "threshold": 0.3,         # permissive — don't drop quiet speech
            "min_speech_duration_ms": 100,
            "min_silence_duration_ms": 800,
        },
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
    )

    text = ""
    any_good_segment = False
    for seg in segments:
        print(f"[segment] no_speech_prob={seg.no_speech_prob:.3f}  '{seg.text}'")
        if seg.no_speech_prob > 0.85:
            continue
        cleaned = seg.text.strip().lower().strip(".,!?")
        if any(h in cleaned for h in HALLUCINATIONS):
            continue
        text += seg.text
        any_good_segment = True

    # Only reject if EVERY segment was noise — not just the last one
    if not any_good_segment:
        print("[listen] All segments rejected as noise")
        return ""

    result = text.strip().lower()
    if result.strip(".,!? ") in HALLUCINATIONS or len(result.strip(".,!? ")) < 2:
        return ""

    return result