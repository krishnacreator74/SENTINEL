# context_helpers.py — Context Formatting Helpers
# This file contains helper functions for formatting and cleaning user input before it's sent to the AI or

import json
import os

MEMORY_FILE = "user_memory.json"

def load_user_context() -> str:
    if not os.path.exists(MEMORY_FILE):
        return ""

    try:
        with open(MEMORY_FILE) as f:
            memory = json.load(f)
    except Exception:
        return ""

    if not memory:
        return ""

    parts = []

    specs = memory.get("specs") or memory.get("hardware") or memory.get("rig")
    if isinstance(specs, dict):
        parts.append("Rig: " + ", ".join(f"{k}={v}" for k, v in specs.items()))
    elif isinstance(specs, str):
        parts.append(f"Rig: {specs}")

    prefs = memory.get("preferences")
    if isinstance(prefs, list):
        parts.append("Preferences: " + ", ".join(prefs))

    skip = {"specs", "hardware", "rig", "preferences"}
    for k, v in memory.items():
        if k in skip:
            continue
        if isinstance(v, str):
            parts.append(f"{k}: {v}")
        elif isinstance(v, list) and all(isinstance(i, str) for i in v):
            parts.append(f"{k}: {', '.join(v)}")

    return " | ".join(parts)