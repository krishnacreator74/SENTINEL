"""
router.py — unified router for Sentinel

Two responsibilities:
1. App launching / system commands  (pure logic, no LLM, instant)
2. Search intent detection is REMOVED — the model decides when to search
   by emitting SEARCH: <query> in its response (handled in ai.py).
"""

import re
from system.commands import launch_app_from_command

# ── App routing tables ────────────────────────────────────────────────────────
OPEN_TRIGGERS = {"open", "launch", "start", "run", "load"}

FILLER_WORDS = {
    "please", "can", "you", "the", "a", "an",
    "app", "application", "browser", "me", "up", "now",
    "could", "would", "will", "just", "hey", "sentinel", "for"
}

APP_ALIASES = {
    "openbrave":   "brave",
    "openfirefox": "firefox",
    "openchrome":  "chrome",
    "launchsteam": "steam",
    "openspotify": "spotify",
    "opendiscord": "discord",
    "opensteam":   "steam",
}

SYSTEM_COMMANDS = {
    "sleep":     "sleep",
    "shutdown":  "shutdown",
    "restart":   "restart",
    "reboot":    "restart",
    "lock":      "lock",
    "hibernate": "sleep",
}

DISQUALIFIERS = {
    "what", "who", "where", "when", "why", "how",
    "is", "are", "do", "does", "did", "was", "were",
    "tell", "search", "find", "news", "latest", "game",
    "date", "today", "weather", "price", "show", "give",
    "release", "update", "version", "world", "market",
    "about", "explain", "describe", "help", "difference",
    "between", "versus", "vs", "compare", "which", "best",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _clean(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ── App / system command routing (no LLM) ────────────────────────────────────
def _add_close_hud_command(req: str, emitter=None) -> bool:
    """Returns True if command was handled."""
    triggers = ["close window", "close hud", "close panel",
                "hide window", "hide display", "close display"]
    
    if any(t in req for t in triggers):
        emitter.emit("hud_close")
        return True
    
    return False

def fast_route(text: str, emitter=None) -> bool:
    """
    Handle app launches and system commands instantly with pure logic.
    Returns True if the command was handled (main loop should skip LLM).
    Returns False if this is a regular query for the LLM.
    """
    if not text:
        return False

    cleaned  = _clean(text)
    words    = cleaned.split()
    word_set = set(words)

    # System commands — highest priority, no disqualifier check
    for keyword, command in SYSTEM_COMMANDS.items():
        if keyword in word_set:
            print(f"[Router] System command: {command}")
            launch_app_from_command(command, emitter)
            return True

    # Disqualify question/info requests
    if word_set.intersection(DISQUALIFIERS):
        return False

    # Fused alias e.g. "openbrave"
    for fused, app in APP_ALIASES.items():
        if fused in words:
            print(f"[Router] Fused alias: {app}")
            launch_app_from_command(f"open {app}", emitter)
            return True

    # Trigger word must be in first 4 words
    first_four = set(words[:4])
    for trigger in OPEN_TRIGGERS:
        if trigger in first_four:
            idx = words.index(trigger)
            app_words = [w for w in words[idx + 1:] if w not in FILLER_WORDS]
            if 1 <= len(app_words) <= 3:
                app = " ".join(app_words)
                print(f"[Router] App launch: {app}")
                launch_app_from_command(f"open {app}", emitter)
                return True

    return False