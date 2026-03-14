# record_samples.py — run this and say your wake word clearly ~200 times
import sounddevice as sd
import numpy as np
import os, time

os.makedirs("training_data/positive", exist_ok=True)

print("Press Enter before each recording. Say 'sentee naal' clearly. Ctrl+C to stop.")
count = 0
while True:
    input(f"[{count}] Press Enter then speak...")
    audio = sd.rec(int(1.5 * 16000), samplerate=16000, channels=1, dtype='int16')
    sd.wait()
    np.save(f"training_data/positive/sample_{count}.npy", audio)
    print("  Saved.")
    count += 1