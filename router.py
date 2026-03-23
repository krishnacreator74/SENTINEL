# router.py
from commands import launch_app_from_command
import re

OPEN_TRIGGERS = {"open", "launch", "start", "run", "load"}

FILLER_WORDS = {
    "please", "can", "you", "the", "a", "an",
    "app", "application", "browser", "me", "up", "now"
}

APP_ALIASES = {
    "openbrave":    "brave",
    "openfirefox":  "firefox",
    "openchrome":   "chrome",
    "launchsteam":  "steam",
    "openspotify":  "spotify",
    "opendiscord":  "discord",
    "opensteam":    "steam",
}

SYSTEM_COMMANDS = {
    "sleep":     "sleep",
    "shutdown":  "shutdown",
    "restart":   "restart",
    "reboot":    "restart",
    "lock":      "lock",
    "hibernate": "sleep",
}

# If any of these words appear in the utterance, it's NOT an app launch
DISQUALIFIERS = {
    "what", "who", "where", "when", "why", "how",
    "is", "are", "do", "does", "did", "was", "were",
    "tell", "search", "find", "news", "latest", "game",
    "date", "today", "weather", "price", "show", "give",
    "release", "update", "version", "world", "market",
    "about", "explain", "describe", "help", "difference",
    "between", "versus", "vs", "compare", "which", "best",
}


def _clean(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fast_route(text: str) -> bool:
    if not text:
        return False

    cleaned = _clean(text)
    words   = cleaned.split()
    word_set = set(words)

    # ── System commands (highest priority, no disqualifier check) ────────────
    for keyword, command in SYSTEM_COMMANDS.items():
        if keyword in word_set:
            print(f"[Router] System command: {command}")
            launch_app_from_command(command)
            return True

    # ── Disqualify anything that looks like a question or info request ───────
    if word_set.intersection(DISQUALIFIERS):
        return False

    # ── Fused alias (e.g. "openbrave") ──────────────────────────────────────
    for fused, app in APP_ALIASES.items():
        if fused in words:
            print(f"[Router] Fused alias: {app}")
            launch_app_from_command(f"open {app}")
            return True

    # ── Trigger word must be in the first 2 words ────────────────────────────
    first_two = set(words[:2])
    for trigger in OPEN_TRIGGERS:
        if trigger in first_two:
            idx = words.index(trigger)
            app_words = [w for w in words[idx + 1:] if w not in FILLER_WORDS]

            # Require at least one real app word and at most 3
            # (long tails are almost always not app names)
            if 1 <= len(app_words) <= 3:
                app = " ".join(app_words)
                print(f"[Router] App launch: {app}")
                launch_app_from_command(f"open {app}")
                return True

    # ── Bare name: entire utterance is 1-2 words, no question words ─────────
    if len(words) <= 2:
        bare = " ".join(w for w in words if w not in FILLER_WORDS)
        if bare:
            print(f"[Router] Bare app: {bare}")
            launch_app_from_command(f"open {bare}")
            return True

    return False