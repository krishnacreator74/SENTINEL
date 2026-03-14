# auto_record_negatives.py
# Just run this and go about your business for 10 minutes
# It auto-saves every 1.5s chunk that has speech energy
import sounddevice as sd
import numpy as np
from pathlib import Path

folder  = Path("training_data/negative")
folder.mkdir(parents=True, exist_ok=True)
existing = len(list(folder.glob("*.npy")))
count    = existing

print(f"Auto-recording negatives (already have {existing})...")
print("Talk, watch videos, do anything. DON'T say your wake word.")
print("Ctrl+C when done.\n")

with sd.InputStream(channels=1, samplerate=16000,
                    blocksize=24000, dtype="int16") as stream:
    while True:
        audio, _ = stream.read(24000)
        arr      = audio.flatten()
        energy   = np.abs(arr.astype(np.float32) / 32768.0).mean()

        # only save chunks with actual audio content
        if energy > 0.001:
            np.save(folder / f"sample_{count}.npy", arr)
            print(f"  saved sample_{count}.npy  energy={energy:.4f}")
            count += 1
        else:
            print(f"  skip (silence)  energy={energy:.4f}")