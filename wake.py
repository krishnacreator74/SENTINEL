from openwakeword.model import Model
import sounddevice as sd
import numpy as np
import time

model = Model(wakeword_models=["voice_models/sentinel.onnx"])

sample_rate = 16000
chunk_size = 1280
threshold = 0.1


def wait_for_wake():

    print("Listening for wake word...")
    trigger_count = 0    
    with sd.InputStream(
        channels=1,
        samplerate=sample_rate,
        blocksize=chunk_size,
        dtype="int16"
    ) as stream:
        
        while True:


            audio, _ = stream.read(chunk_size)
            audio = audio.flatten()

            score = model.predict(audio)["sentinel"]

            if score > threshold:
                trigger_count += 1
            else:
                trigger_count = 0

            # require multiple frames
            if trigger_count >= 2:
                print("Wake word detected!")
                time.sleep(1)  # short cooldown
                return