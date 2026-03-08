# SENTINEL 🎙️

A local, privacy-focused voice-activated AI assistant that runs entirely on your machine.

## Features

- **Wake Word Detection** - Listens for "Sentinel" to activate
- **Voice Recognition** - Converts speech to text using Faster Whisper
- **AI-Powered Responses** - Uses LM Studio with Qwen3.5-9B for natural conversations
- **Voice Output** - Speaks responses using Piper TTS
- **App Launcher** - Opens applications via voice commands

## Requirements

- Windows 11
- Python 3.10+
- [LM Studio](https://lmstudio.ai/) (for the LLM)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sentinel.git
cd sentinel
```

2. Install Python dependencies:
```bash
pip install sounddevice numpy piper-tts faster-whisper openwakeword lmstudio
```

3. Download required models:
   - **Whisper** - The `tiny` model is downloaded automatically
   - **Piper TTS** - `en_US-hfc_female-medium.onnx` included in `voice_models/`
   - **Wake Word** - `sentinel.onnx` included in `voice_models/`
   - **LLM** - Use LM Studio to download `qwen/qwen3.5-9b`

4. Configure LM Studio:
   - Open LM Studio
   - Download and load the Qwen3.5-9B model
   - Ensure the local server is running on port 1234

## Usage

Run the main script:
```bash
python main.py
```

### Voice Commands

- Say "Sentinel" to wake the assistant
- Once activated, speak your request
- To launch apps, say: "Open [app name]" (e.g., "Open chrome", "Open notepad")

### Example Interaction

```
You: Sentinel
Sentinel: yes?
You: what's the weather like today?
Sentinel: [responds with weather info]

You: Sentinel
Sentinel: yes?
You: open chrome
Sentinel: Opening chrome
[Chrome launches]
```

## Project Structure

```
SENTINEL/
├── main.py              # Main application loop
├── voice.py             # Text-to-speech (Piper)
├── ears.py              # Speech recognition (Whisper)
├── wake.py              # Wake word detection
├── commands.py          # Application launcher
├── config.py            # Configuration
├── ai.py                # AI integration
├── known_apps.json      # Cached application paths
├── voice_models/        # TTS and wake word models
│   ├── en_US-hfc_female-medium.onnx
│   ├── sentinel.onnx
│   └── ...
└── README.md
```

## Configuration

### Wake Word Sensitivity

Edit `wake.py` to adjust detection threshold:
```python
threshold = 0.1  # Lower = more sensitive
```

### Listening Duration

Edit `ears.py` to change how long it listens:
```python
duration = 4  # seconds
```

### Supported Launch Locations

The app launcher scans these directories by default:
- `C:\Program Files`
- `C:\Program Files (x86)`
- `C:\Users\%USERNAME%\AppData\Local`
- `C:\Users\%USERNAME%\AppData\Roaming`
- `C:\ProgramData\Microsoft\Windows\Start Menu\Programs`

## Troubleshooting

**"No speech detected"** - Speak clearly and ensure microphone is working

**LM Studio not connecting** - Ensure LM Studio server is running on port 1234

**Wake word not triggering** - Adjust the `threshold` in `wake.py` or speak louder

**App not launching** - Try using the full application name (e.g., "microsoft edge" instead of "edge")

## License

MIT License

