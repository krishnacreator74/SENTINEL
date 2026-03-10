from openwakeword.model import Model
import sounddevice as sd
import numpy as np
import time

model = Model(wakeword_models=["voice_models/sentee_naal.onnx"])

sample_rate = 16000
chunk_size = 2048
samples = 50


def wait_for_wake():

    trigger_count = 0
    noise_floor = 0.0
    scores = []

    cooldown = 1.5
    last_trigger = 0

    with sd.InputStream(
        channels=1,
        samplerate=sample_rate,
        blocksize=chunk_size,
        dtype="int16"
    ) as stream:

        # measure background noise
        for _ in range(samples):
            audio, _ = stream.read(chunk_size)
            audio = audio.flatten()

            score = model.predict(audio)["sentee_naal"]

            if score < 0.02:
                noise_floor += score

        noise_floor /= samples

        # slightly lower threshold for flexibility
        threshold = noise_floor + 0.006

        print("Listening for wake word...")

        while True:

            audio, _ = stream.read(chunk_size)
            audio = audio.flatten()

            score = model.predict(audio)["sentee_naal"]
            print(score)

            scores.append(score)

            # keep last 8 frames
            if len(scores) > 8:
                scores.pop(0)

            avg_score = sum(scores) / len(scores)
            peak_score = max(scores)

            # cooldown protection
            if time.time() - last_trigger < cooldown:
                continue

            # detection logic
            if avg_score > threshold and peak_score > threshold * 2:
                trigger_count += 1
            else:
                trigger_count = max(0, trigger_count - 1)

            if trigger_count >= 4:
                print("Wake word detected!")
                last_trigger = time.time()
                trigger_count = 0
                scores.clear()
                time.sleep(0.5)
                return