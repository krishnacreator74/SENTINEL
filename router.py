"""
router.py — unified router for Sentinel

Two responsibilities:
1. App launching / system commands  (pure logic, no LLM, instant)
2. Search intent detection          (single LLM call using whatever model is loaded)

App routing is always deterministic so it never needs a model.
Search routing uses the same model as the main assistant — no second model required.
"""

import re
import json
import httpx
from commands import launch_app_from_command
from config import MODEL_NAME

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

# ── App routing tables ────────────────────────────────────────────────────────
OPEN_TRIGGERS = {"open", "launch", "start", "run", "load"}

FILLER_WORDS = {
    "please", "can", "you", "the", "a", "an",
    "app", "application", "browser", "me", "up", "now"
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

# ── Search routing prompt ─────────────────────────────────────────────────────
SEARCH_ROUTER_PROMPT = """You are a search intent classifier for a voice assistant.

Decide if the user's message needs a real-time web search to answer accurately.

Reply ONLY with JSON: {"search": true} or {"search": false}

Search IS needed:
- Current events, news, scores, weather, prices
- "latest", "right now", "today", "what happened", "recent"
- Specific recent releases, announcements, updates

Search is NOT needed:
- User is storing or recalling personal info ("add this", "what are my specs")
- General knowledge or explanations
- Tasks like writing code, planning, debugging
- Small talk or instructions to you

Reply with only the JSON. Nothing else."""

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

    FILLER_WORDS = {
    "please", "can", "you", "the", "a", "an",
    "app", "application", "browser", "me", "up", "now",
    "could", "would", "will", "just", "hey", "sentinel"
    }
    # Trigger word must be in first 2 words
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

# ── Search intent routing (single LLM call) ───────────────────────────────────
def needs_search(user_text: str) -> bool:
    """
    Ask the loaded model whether this query needs a web search.
    Uses max_tokens=10 so it's near-instant even on a small model.
    Falls back to False on any error so the main flow is never blocked.
    """
    # Hard-skip personal memory queries — never need web search
    personal_triggers = [
        "my specs", "my birthday", "my name", "my ram", "my gpu",
        "my cpu", "what do you know about me", "what's in your memory",
        "add to memory", "remember that", "save this"
    ]
    t = user_text.lower()
    if any(trigger in t for trigger in personal_triggers):
        print("[Router] search=False (personal memory query)")
        return False

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SEARCH_ROUTER_PROMPT},
            {"role": "user",   "content": user_text}
        ],
        "temperature": 0.0,
        "max_tokens":  10,
        "stream":      False
    }

    try:
        r = httpx.post(LM_STUDIO_URL, json=payload, timeout=10)
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()

        # Strip <think> blocks (reasoning models like Qwen)
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        decision = json.loads(raw)
        result   = bool(decision.get("search", False))
        print(f"[Router] search={result} → '{user_text[:60]}'")
        return result

    except Exception as e:
        print(f"[Router] search=False (fallback) — {e}")
        return False