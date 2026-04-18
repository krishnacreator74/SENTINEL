import json
import re
import httpx
from memory.memory_persistent import update_memory
from config import MODEL_NAME
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

IMPORTANT:
Hardware information is ALWAYS valuable long-term memory.

Examples of hardware to store:
- GPU (e.g. RTX 3060)
- CPU (e.g. Ryzen 5)
- RAM (e.g. 16GB)
- Storage (e.g. SSD, HDD, NVMe)
- Monitor details (resolution, refresh rate)
- OS

If the user mentions ANY hardware, you MUST store it under "hardware".

Output a JSON object using ONLY these keys (omit any key that has no data):
- "hardware": object with fields like gpu, cpu, ram, storage, monitor_resolution, monitor_hz, os
- "projects": list of strings describing things the user is building or working on
- "preferences": list of strings for things the user explicitly prefers (tone, format, tools)
- "facts": object for personal facts like name, location, job, timezone
- "goals": list of strings for things the user wants to achieve

Strict rules:
1. Only extract things the USER said. Ignore anything the assistant said.
2. Only store EXPLICIT information — never infer or assume.
3. Hardware info must be stored if present (e.g. "ssd" → {{"storage": "ssd"}}).
4. "preferences" must be things the user actually asked for.
5. Do NOT store: search results, temporary info, AI explanations.
6. If nothing is worth storing, return {{}}.

Return only valid JSON. No explanation."""


def analyze_and_store_memory(parsed_response: dict):
    from memory.memory_persistent import update_memory

    memory_data = parsed_response.get("memory", {})

    if not isinstance(memory_data, dict) or not memory_data:
        print("[Memory] Nothing worth storing.")
        return

    # Optional safety: only allow known keys
    ALLOWED_KEYS = {"hardware", "projects", "preferences", "facts", "goals"}
    filtered = {k: v for k, v in memory_data.items() if k in ALLOWED_KEYS}

    if filtered:
        update_memory(filtered)
        print("[Memory] Stored:", filtered)
    else:
        print("[Memory] Nothing valid to store.")