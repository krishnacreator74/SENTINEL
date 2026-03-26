from openwakeword.utils import AudioFeatures
import sounddevice as sd
import numpy as np
import pickle
import time
from collections import deque
import ears
import soundfile as sf
import os

fe = AudioFeatures()
with open("voice_models/sentee_naal_clf.pkl", "rb") as f:
    clf = pickle.load(f)

sample_rate = 16000
chunk_size  = 24000  # 1.5s — must match training
hop_size    = 3200   # evaluate every 0.2s

def predict(audio_int16):
    feats = fe.embed_clips(audio_int16.reshape(1, -1)).reshape(1, -1)
    return clf.predict_proba(feats)[0][1]

def wait_for_wake(silence_gate=None):
    cooldown      = 2.0
    last_trigger  = 0
    buffer        = deque(maxlen=chunk_size)
    confirm_times = []

    with sd.InputStream(channels=1, samplerate=sample_rate,
                        blocksize=hop_size, dtype="int16") as stream:

        if silence_gate is None:
            print("[calibrate] Stay quiet...")
            readings = []
            for _ in range(20):
                audio, _ = stream.read(hop_size)
                af = audio.flatten().astype(np.float32) / 32768.0
                readings.append(np.abs(af).mean())

            noise_floor  = np.mean(readings)
            silence_gate = max(0.00005, noise_floor * 1.5)
            print(f"[calibrate] noise={noise_floor:.5f}  gate={silence_gate:.5f}")
            ears.set_thresholds(
                speech  = max(0.0008, noise_floor * 3.0),
                silence = max(0.0005, noise_floor * 2.0)
            )

        print("Listening for wake word...")
        last_hb      = time.time()
        peak_prob    = 0.0
        peak_time    = 0.0

        while True:
            audio, _ = stream.read(hop_size)
            chunk = audio.flatten()
            buffer.extend(chunk)

            now = time.time()

            if now - last_hb > 3.0:
                print(".", end="", flush=True)
                last_hb = now

            if len(buffer) < chunk_size:
                continue

            if now - last_trigger < cooldown:
                confirm_times.clear()
                peak_prob = 0.0
                continue



            window = np.array(buffer, dtype=np.int16)
            prob   = predict(window)

            if prob > 0.1:
                print(f"\nprob={prob:.4f}  peak={peak_prob:.4f}")

            # track rolling peak
            if prob > peak_prob:
                peak_prob = prob
                peak_time = now

            # decay peak over time
            if now - peak_time > 1.5:
                peak_prob *= 0.5

            if prob >= 0.90:
                if not confirm_times or (now - confirm_times[-1]) >= 0.3:
                    confirm_times.append(now)

            confirm_times = [t for t in confirm_times if now - t < 2.0]

            if len(confirm_times) >= 1:
                print("\nWake word detected!")
                
                # # save the triggering audio for inspection
                # os.makedirs("debug_triggers", exist_ok=True)
                # trigger_audio = np.array(buffer, dtype=np.int16)
                # sf.write(f"debug_triggers/trigger_{int(time.time())}.wav",
                #          trigger_audio, sample_rate)
                
                last_trigger  = time.time()
                confirm_times.clear()
                peak_prob     = 0.0
                buffer.clear()
                time.sleep(0.3)
                return silence_gate