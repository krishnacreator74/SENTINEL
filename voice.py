from piper import PiperVoice
import sounddevice as sd
import numpy as np

voice = PiperVoice.load(
    model_path="voice_models/en_US-hfc_female-medium.onnx",
    config_path="voice_models/en_US-hfc_female-medium.onnx.json"
)

def voice_of_ai(text):
    audio_parts = []
    sample_rate = None

    for chunk in voice.synthesize(text):

        audio_parts.append(chunk.audio_float_array)
        sample_rate = chunk.sample_rate

    audio = np.concatenate(audio_parts)

    sd.play(audio, sample_rate)
    sd.wait()