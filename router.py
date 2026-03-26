"""
router.py — unified router for Sentinel

Two responsibilities:
1. App launching / system commands  (pure logic, no LLM, instant)
2. Search intent detection is REMOVED — the model decides when to search
   by emitting SEARCH: <query> in its response (handled in ai.py).
"""

import re
from commands import launch_app_from_command

# ── App routing tables ────────────────────────────────────────────────────────
OPEN_TRIGGERS = {"open", "launch", "start", "run", "load"}

FILLER_WORDS = {
    "please", "can", "you", "the", "a", "an",
    "app", "application", "browser", "me", "up", "now",
    "could", "would", "will", "just", "hey", "sentinel"
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
def fast_route(text: str) -> bool:
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
            launch_app_from_command(command)
            return True

    # Disqualify question/info requests
    if word_set.intersection(DISQUALIFIERS):
        return False

    # Fused alias e.g. "openbrave"
    for fused, app in APP_ALIASES.items():
        if fused in words:
            print(f"[Router] Fused alias: {app}")
            launch_app_from_command(f"open {app}")
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
                launch_app_from_command(f"open {app}")
                return True

    # Bare 1-2 word utterance with no question words
    if len(words) <= 2:
        bare = " ".join(w for w in words if w not in FILLER_WORDS)
        if bare:
            print(f"[Router] Bare app: {bare}")
            launch_app_from_command(f"open {bare}")
            return True

    return False