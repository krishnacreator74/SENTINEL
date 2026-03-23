import json
import re
import httpx
from memory_persistent import update_memory
from config import MODEL_NAME

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

def clean_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()

def analyze_and_store_memory(user_text: str, assistant_text: str):
    combined = f"User: {user_text}\nAssistant: {assistant_text}"

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": """Extract ONLY important long-term memory.

If nothing important return {}

Create keys that make logical sense for the data. Examples:
- "specs": {"gpu": "RTX 3080 Ti", "ram": "32GB"}
- "projects": ["building a game called X"]
- "preferences": ["casual tone", "concise answers"]
- "goals": ["release game by June"]

Rules:
- Be specific and accurate
- Group related info logically
- Never put hardware specs under "skills"
- Return only valid JSON, no explanation"""
            },
            {
                "role": "user",
                "content": combined
            }
        ],
        "temperature": 0.2,
        "stream": False
    }

    try:
        r = httpx.post(LM_STUDIO_URL, json=payload, timeout=30)
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        print("[Memory] Raw:", raw)

        cleaned = clean_json(raw)
        data = json.loads(cleaned)

        if data and any(data.values()):
            update_memory(data)
            print("[Memory] Stored:", data)

    except json.JSONDecodeError as e:
        print(f"[Memory] Parse failed: {e}")
    except Exception as e:
        print(f"[Memory] Error: {e}")