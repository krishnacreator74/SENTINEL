import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel


# load whisper model
model = WhisperModel("medium",device="cuda", compute_type="int8")

def listen():

    duration = 4 # seconds
    sample_rate = 16000


    print("Listening...")

    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32"
    )

    sd.wait()

    audio = audio.flatten() 

    segments, _ = model.transcribe(audio, language="en")

    text = ""

    for segment in segments:
        text += segment.text

    return text.strip().lower()