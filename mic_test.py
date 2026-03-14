# test_all_mics.py
import sounddevice as sd
import numpy as np

devices = sd.query_devices()
input_devices = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]

for idx, device in input_devices:
    print(f"\nTesting [{idx}] {device['name']}...")
    try:
        audio = sd.rec(int(2 * 16000), samplerate=16000, 
                      channels=1, dtype='int16', device=idx)
        sd.wait()
        arr = audio.flatten().astype(np.float32) / 32768.0
        print(f"  max={np.abs(arr).max():.5f}  rms={np.sqrt(np.mean(arr**2)):.5f}")
    except Exception as e:
        print(f"  ERROR: {e}")