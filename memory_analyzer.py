import json
import re
import httpx
from memory_persistent import update_memory
from config import MODEL_NAME

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"


def _clean_json(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```json|```", "", text)
    return text.strip()


# ── Fixed memory schema ───────────────────────────────────────────────────────
# Only these top-level keys are allowed. The LLM must fit everything into them.
# This prevents it from inventing keys like "capabilities", "knowledge_base",
# "optimization_settings", etc.
ALLOWED_KEYS = {"hardware", "projects", "preferences", "facts", "goals"}

SYSTEM_PROMPT = f"""You extract long-term facts about the USER from their messages.

Output a JSON object using ONLY these keys (omit any key that has no data):
- "hardware": object with fields like gpu, cpu, ram, monitor_resolution, monitor_hz, os
- "projects": list of strings describing things the user is building or working on
- "preferences": list of strings for things the user explicitly prefers (tone, format, tools)
- "facts": object for personal facts like name, location, job, timezone
- "goals": list of strings for things the user wants to achieve

Strict rules:
1. Only extract things the USER said. Ignore anything the assistant said.
2. Only store EXPLICIT information — never infer or assume.
3. "preferences" must be things the user actually asked for, not how the AI responded.
   BAD: "casual tone" (that's how AI replied)   GOOD: "prefers concise answers" (user asked for it)
4. Do NOT store: search results, game settings from searches, AI explanations, one-time questions.
5. Do NOT store anything that would go stale quickly (prices, news, scores).
6. If nothing in the user message is worth storing long-term, return {{}}

Return only valid JSON. No explanation."""


def analyze_and_store_memory(user_text: str, assistant_text: str):
    """
    Analyzes only the user's message for long-term memory.
    assistant_text is accepted for signature compatibility but NOT passed to the LLM —
    this prevents the AI's own words from being stored as user preferences.
    """
    # Quick pre-filter: skip very short or trivial messages
    if len(user_text.strip()) < 10:
        return

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"User message: {user_text}"}
        ],
        "temperature": 0.1,   # low temp = more literal, less creative
        "stream": False,
        "max_tokens": 300,
    }

    try:
        r = httpx.post(LM_STUDIO_URL, json=payload, timeout=30)
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        print("[Memory] Raw:", raw)

        cleaned = _clean_json(raw)
        data = json.loads(cleaned)

        if not isinstance(data, dict) or not data:
            return

        # Strip any keys not in the allowed schema
        filtered = {k: v for k, v in data.items() if k in ALLOWED_KEYS}

        # Strip empty values
        filtered = {k: v for k, v in filtered.items() if v}

        if filtered:
            update_memory(filtered)
            print("[Memory] Stored:", filtered)
        else:
            print("[Memory] Nothing worth storing.")

    except json.JSONDecodeError as e:
        print(f"[Memory] Parse failed: {e}")
    except Exception as e:
        print(f"[Memory] Error: {e}")