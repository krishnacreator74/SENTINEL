from openwakeword.model import Model
import sounddevice as sd
import numpy as np
import time

model = Model(wakeword_models=["voice_models/sentinel.onnx"])

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
            score = model.predict(audio)["sentinel"]

            if score < 0.01:
                noise_floor += score

        noise_floor /= samples
        threshold = noise_floor + 0.01

        print("Listening for wake word...")

        while True:

            audio, _ = stream.read(chunk_size)
            audio = audio.flatten()

            score = model.predict(audio)["sentinel"]

            scores.append(score)
            if len(scores) > 5:
                scores.pop(0)

            avg_score = sum(scores) / len(scores)

            # cooldown protection
            if time.time() - last_trigger < cooldown:
                continue

            if avg_score > threshold and score > threshold * 2:
                trigger_count += 1
            else:
                trigger_count = 0

            if trigger_count >= 3:
                print("Wake word detected!")
                last_trigger = time.time()
                time.sleep(0.5)
                return