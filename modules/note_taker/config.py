"""
config.py — Note Taker module configuration.
All constants live here. Nothing else. Edit this file to tune behaviour.
"""

# ── LM Studio ─────────────────────────────────────────────────────────────────
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME    = "qwen/qwen3-9b"

# ── Whisper ───────────────────────────────────────────────────────────────────
WHISPER_MODEL  = "medium"
WHISPER_DEVICE = "cuda"
WHISPER_DTYPE  = "int8"

# ── Audio ─────────────────────────────────────────────────────────────────────
CAPTURE_METHOD   = "both"       # 'loopback', 'mic', or 'both'
LOOPBACK_CHUNK_S = 5            # seconds per loopback recording chunk
LOOPBACK_SR      = 16000        # sample rate
MIC_RMS_FLOOR    = 0.001        # minimum RMS to start capturing mic speech
NO_SPEECH_PROB   = 0.95         # whisper segments above this are rejected as noise

# ── Screen ────────────────────────────────────────────────────────────────────
MAX_IMG_WIDTH     = 1024        # screenshot width sent to LLM
CHANGE_THRESHOLD  = 0.06        # pixel diff fraction to count as screen change
DIAGRAM_THRESHOLD = 600         # colour diversity (unique pixels) to save screenshot

# ── Session ───────────────────────────────────────────────────────────────────
NOTES_DIR        = "sentinel_notes"
INTERVAL_SECONDS = 20           # minimum seconds between note writes

# ── Dedup ─────────────────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.85     # fuzzy match ratio above which a box is a duplicate

# ── Stop phrases (mic trigger) ────────────────────────────────────────────────
STOP_PHRASES = (
    "stop notes", "stop taking notes", "end notes",
    "stop", "finish notes", "sentinel stop",
)

# ── Whisper hallucination blocklist ───────────────────────────────────────────
WHISPER_HALLUCINATIONS = {
    "thanks for watching", "thank you for watching", "please subscribe",
    "like and subscribe", "see you next time", "bye", "goodbye", ".",
    "thank you", "you",
}