import json
import os

MEMORY_FILE = "user_memory.json"


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        try:
            return json.load(f)
        except Exception:
            return {}


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


def update_memory(new_data):
    memory = load_memory()

    for key, value in new_data.items():
        if key not in memory:
            # New key — just store it
            memory[key] = value
            continue

        existing = memory[key]

        # dict + dict → deep merge (e.g. hardware: {gpu:..} + {cpu:..})
        if isinstance(existing, dict) and isinstance(value, dict):
            existing.update(value)
            memory[key] = existing

        # list + list → deduplicated merge
        elif isinstance(existing, list) and isinstance(value, list):
            merged = list(dict.fromkeys(existing + value))
            memory[key] = merged

        # str + str → append if not already present
        elif isinstance(existing, str) and isinstance(value, str):
            if value not in existing:
                memory[key] = existing + ", " + value

        # type mismatch — overwrite with new value
        else:
            memory[key] = value

    save_memory(memory)