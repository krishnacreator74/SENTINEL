from commands import launch_app_from_command
import re

OPEN_TRIGGERS = {"open", "launch", "start", "run", "load"}

FILLER_WORDS = {
    "please", "can", "you", "the", "a", "an",
    "app", "application", "browser", "me", "up", "now"
}

# Known app aliases - catches fused words like "openbrave" -> "brave"
APP_ALIASES = {
    "openbrave": "brave",
    "openfirefox": "firefox",
    "openchrome": "chrome",
    "launchsteam": "steam",
    "openspotify": "spotify",
    "opendiscord": "discord",
    "opensteam": "steam",
}

SYSTEM_COMMANDS = {
    "sleep":     "sleep",
    "shutdown":  "shutdown",
    "restart":   "restart",
    "reboot":    "restart",
    "lock":      "lock",
    "hibernate": "sleep",
}


def _clean(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)   # replace punct with space (not empty)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fast_route(text: str) -> bool:
    if not text:
        return False

    cleaned = _clean(text)
    words = cleaned.split()
    word_set = set(words)

    # ---- SYSTEM COMMANDS (highest priority) ----
    for keyword, command in SYSTEM_COMMANDS.items():
        if keyword in word_set:
            print(f"[Router] System command detected: {command}")
            launch_app_from_command(command)
            return True

    # ---- FUSED WORD ALIAS (e.g. "openbrave" with no space) ----
    for fused, app in APP_ALIASES.items():
        if fused in words:
            print(f"[Router] Fused app launch detected: {app}")
            launch_app_from_command(f"open {app}")
            return True

    # ---- OPEN / LAUNCH APP (trigger word present) ----
    for trigger in OPEN_TRIGGERS:
        if trigger in word_set:
            idx = words.index(trigger)
            app_words = [w for w in words[idx + 1:] if w not in FILLER_WORDS]

            if app_words:
                app = " ".join(app_words)
                print(f"[Router] App launch detected: {app}")
                launch_app_from_command(f"open {app}")
                return True

    # ---- BARE APP NAME (no trigger word, single word only to avoid false positives) ----
    # Only fires if the entire utterance is 1-2 words and not a question
    question_words = {"what", "who", "where", "when", "why", "how", "is", "are", "do", "does"}
    if len(words) <= 2 and not word_set.intersection(question_words):
        bare = " ".join(w for w in words if w not in FILLER_WORDS)
        if bare:
            print(f"[Router] Bare app name detected: {bare}")
            launch_app_from_command(f"open {bare}")
            return True

    return False