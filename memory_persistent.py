import json
import os

MEMORY_FILE = "user_memory.json"


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}

    with open(MEMORY_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


def update_memory(new_data):

    memory = load_memory()

    for key, value in new_data.items():

        # if key already exists
        if key in memory:

            # merge lists
            if isinstance(memory[key], list) and isinstance(value, list):

                merged = list(set(memory[key] + value))
                memory[key] = merged

            # merge strings
            elif isinstance(memory[key], str) and isinstance(value, str):

                if value not in memory[key]:
                    memory[key] = memory[key] + ", " + value

        else:
            memory[key] = value

    save_memory(memory)