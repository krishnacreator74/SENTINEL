import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

model = WhisperModel("medium", device="cuda", compute_type="int8")

HALLUCINATIONS = {
    "thanks for watching", "thank you for watching",
    "please subscribe", "like and subscribe",
    "see you next time", "bye", "goodbye", ".",
}  # NOTE: no empty string — "" in any_string is always True in Python

def calibrate(device=None, duration=1.5):
    print("[calibrate] Stay quiet for 1.5s...")
    sample_rate   = 16000
    chunk_samples = int(sample_rate * 0.1)
    rms_vals      = []

    with sd.InputStream(samplerate=sample_rate, channels=1,
                        dtype="float32", device=device) as stream:
        for _ in range(int(duration / 0.1)):
            chunk, _ = stream.read(chunk_samples)
            rms_vals.append(float(np.sqrt(np.mean(chunk.flatten() ** 2))))

    noise_peak     = float(np.max(rms_vals))
    # Your mic peaks at ~0.0003 noise, ~0.003 voice
    # Use 1.5x noise_peak as speech threshold, with a very low floor
    speech_thresh  = max(0.0008, noise_peak * 1.5)
    silence_thresh = max(0.0005, noise_peak * 1.1)
    print(f"[calibrate] noise_peak={noise_peak:.5f} → speech_thresh={speech_thresh:.5f}  silence_thresh={silence_thresh:.5f}")
    return speech_thresh, silence_thresh

def pick_device():
    devices = sd.query_devices()
    print("\n=== Available Input Devices ===")
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            print(f"  [{i}] {d['name']}")
    default_idx = sd.default.device[0]
    print(f"================================")
    print(f"Default: [{default_idx}] {devices[default_idx]['name']}")
    choice = input("Enter device number (or Enter for default): ").strip()
    return int(choice) if choice else None

_DEVICE = pick_device()
_SPEECH_THRESH, _SILENCE_THRESH = calibrate(device=_DEVICE)

def listen():

    sample_rate    = 16000
    chunk_duration = 0.1
    chunk_samples  = int(sample_rate * chunk_duration)

    speech_thresh  = _SPEECH_THRESH
    silence_thresh = _SILENCE_THRESH
    pre_roll_n     = int(0.4  / chunk_duration)
    silence_n      = int(1.0  / chunk_duration)
    min_speech_n   = 2   # just 2 chunks = 0.2s of speech needed
    max_wait_n     = int(10.0 / chunk_duration)
    max_n          = int(30.0 / chunk_duration)

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
                        print(f"[listen] Timeout. Last rms={rms:.5f} thresh={speech_thresh:.5f}")
                        return ""
            else:
                speech_buf.append(chunk)
                if rms > silence_thresh:
                    speech_count  += 1
                    silence_count  = 0
                else:
                    silence_count += 1

                if silence_count >= silence_n and speech_count >= min_speech_n:
                    break

    if not speech_buf or speech_count < min_speech_n:
        print("[listen] No speech detected.")
        return ""

    audio = np.concatenate(speech_buf)
    print(f"[listen] {len(audio)/sample_rate:.1f}s  rms={np.sqrt(np.mean(audio**2)):.5f}  speech_chunks={speech_count}")

    segments, _ = model.transcribe(
        audio, language="en", vad_filter=False,
        beam_size=5, temperature=0.0,
        condition_on_previous_text=False,
    )

    text = ""
    for seg in segments:
        print(f"[segment] no_speech_prob={seg.no_speech_prob:.3f}  '{seg.text}'")
        if seg.no_speech_prob > 0.85:
            continue
        cleaned = seg.text.strip().lower().strip(".,!?")
        if any(h in cleaned for h in HALLUCINATIONS):
            continue
        text += seg.text

    result = text.strip().lower()
    if result.strip(".,!? ") in HALLUCINATIONS or len(result.strip(".,!? ")) < 2:
        return ""

    return result