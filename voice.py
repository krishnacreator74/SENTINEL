from piper import PiperVoice
import sounddevice as sd
import numpy as np

widget = None

voice = PiperVoice.load(
    model_path="voice_models/en_US-hfc_female-medium.onnx",
    config_path="voice_models/en_US-hfc_female-medium.onnx.json"
)

def voice_of_ai(text):

    if widget:
        widget.set_speaking()

    for chunk in voice.synthesize(text):

        audio = chunk.audio_float_array
        sample_rate = chunk.sample_rate

        volume = np.abs(audio).mean()

        if widget:
            widget.set_energy(volume * 5)

        sd.play(audio, sample_rate)
        sd.wait()

    if widget:
        widget.set_idle()