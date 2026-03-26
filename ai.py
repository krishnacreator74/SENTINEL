import re
import json
import threading
import httpx
from config import SYSTEM_PROMPT, MODEL_NAME, TEMPERATURE, TOP_P, TOP_K
from memory_persistent import load_memory
from memory_analyzer import analyze_and_store_memory
from tools import detect_tool

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

TOOL_INSTRUCTIONS = """
You have tools available. Use them by writing on their own line:
SEARCH: <specific query>

Only use SEARCH for: current news, live prices, scores, weather, recent releases.
Never use SEARCH for: coding, general knowledge, math, history, personal info.
Query must have at least 2 specific words. Only search once per reply.
"""

# ── Text helpers ──────────────────────────────────────────────────────────────
def _strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*",          "", text, flags=re.DOTALL)
    text = re.sub(r"Thinking Process:.*?(?=\n[A-Z]|\Z)", "", text, flags=re.DOTALL)
    return text.strip()

def _strip_tool_lines(text: str) -> str:
    """Remove any SEARCH: lines from final spoken output."""
    return re.sub(r"(?m)^SEARCH:.*$", "", text, flags=re.IGNORECASE).strip()

def clean_for_voice(text: str) -> str:
    text = _strip_thinking(text)
    text = _strip_tool_lines(text)
    text = re.sub(r"\*\*|\*", "", text)
    text = text.replace("e.g.", "for example").replace("i.e.", "that is")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def validate_messages(messages: list) -> list:
    fixed, last_role = [], None
    for msg in messages:
        if msg["role"] == last_role:
            continue
        fixed.append(msg)
        last_role = msg["role"]
    return fixed

def build_system_prompt() -> str:
    memory = load_memory()
    return (
        SYSTEM_PROMPT
        + TOOL_INSTRUCTIONS
        + "\nKnown user info:\n"
        + json.dumps(memory, indent=2)
    )

def run_memory_async(user_text: str, assistant_text: str):
    def task():
        try:
            analyze_and_store_memory(user_text, assistant_text)
        except Exception as e:
            print(f"[Memory] Error: {e}")
    threading.Thread(target=task, daemon=True).start()

# ── API helpers ───────────────────────────────────────────────────────────────
def _payload(messages: list, stream: bool, max_tokens: int = 400) -> dict:
    return {
        "model":                MODEL_NAME,
        "messages":             messages,
        "temperature":          TEMPERATURE,
        "top_p":                TOP_P,
        "top_k":                TOP_K,
        "stream":               stream,
        "max_tokens":           max_tokens,
        "enable_thinking":      False,
        "chat_template_kwargs": {"thinking": False},
    }

def _stream_full(messages: list) -> str:
    """Stream complete response — always drains fully to avoid LM Studio disconnect."""
    full = ""
    try:
        with httpx.stream(
            "POST", LM_STUDIO_URL,
            json=_payload(messages, stream=True),
            headers={"Content-Type": "application/json"},
            timeout=90,
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw or not raw.startswith("data:"):
                    continue
                chunk = raw[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    token = json.loads(chunk)["choices"][0]["delta"].get("content", "") or ""
                except (json.JSONDecodeError, KeyError):
                    continue
                full += token
                print(token, end="", flush=True)
    except Exception as e:
        print(f"\n[AI] Stream error: {e}")
    print()
    return full

def _call_sync(messages: list, max_tokens: int = 350) -> str:
    """Blocking call — used when we need a clean answer after tool injection."""
    try:
        print(f"[AI] Sync call...")
        r = httpx.post(
            LM_STUDIO_URL,
            json=_payload(messages, stream=False, max_tokens=max_tokens),
            timeout=90
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""
    except Exception as e:
        print(f"[AI] Sync error: {e}")
        return ""

# ── Core AI class ─────────────────────────────────────────────────────────────
class SentinelAI:
    def __init__(self):
        self._verify_connection()

    def _verify_connection(self):
        try:
            r = httpx.get("http://localhost:1234/v1/models", timeout=5)
            models = [m["id"] for m in r.json().get("data", [])]
            print(f"[AI] Connected. Models: {models}")
            if MODEL_NAME not in models:
                print(f"[AI] WARNING: '{MODEL_NAME}' not loaded!")
        except Exception as e:
            raise RuntimeError(f"[AI] Cannot reach LM Studio: {e}")

    def respond_stream(self, messages: list, on_sentence=None) -> str:
        print(f"[AI] Responding...")

        # ── Step 1: get full first response ───────────────────────────────────
        raw = _stream_full(messages)
        clean = _strip_thinking(raw)
        print(f"[AI] Clean response: {len(clean)} chars")

        if not clean:
            msg = "I had trouble generating a response. Please try again."
            if on_sentence:
                on_sentence(msg)
            return msg

        # ── Step 2: check if model wants to use a tool ────────────────────────
        tool, arg = detect_tool(clean)

        if tool is None:
            # No tool — just speak the response
            self._speak(clean, on_sentence)
            return clean_for_voice(clean)

        # ── Step 3: run the tool ──────────────────────────────────────────────
        print(f"[AI] Tool '{tool.name}' triggered with: '{arg}'")
        if on_sentence:
            on_sentence("Let me look that up.")

        tool_result = tool.run(arg)

        # What the model said before the tool call line
        pre = re.split(r"SEARCH:", clean, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if pre:
            self._speak(pre, on_sentence)

        # ── Step 4: inject result and force a grounded answer ─────────────────
        new_messages = list(messages)
        if pre:
            new_messages.append({"role": "assistant", "content": pre})

        # This prompt structure makes it very hard for the model to ignore results:
        # - Results come FIRST as a system-style block
        # - Instruction is a direct command, not a suggestion
        # - Explicitly forbids asking follow-up questions or saying "I need more info"
        new_messages.append({
            "role": "user",
            "content": (
                "=== SEARCH RESULTS START ===\n"
                + tool_result
                + "\n=== SEARCH RESULTS END ===\n\n"
                "The results above are from a live web search. "
                "Read them and give me a summary right now. "
                "3 to 5 sentences. Plain text only. No bullet points. "
                "Do not say you need more info. Do not ask follow-up questions. "
                "Just summarize what the search results say."
            )
        })
        new_messages = validate_messages(new_messages)

        # ── Step 5: get the grounded answer ───────────────────────────────────
        raw_answer = _call_sync(new_messages, max_tokens=350)
        final = clean_for_voice(_strip_thinking(raw_answer))

        if not final:
            final = "I found results but had trouble summarizing them."

        self._speak(final, on_sentence)
        print(f"[AI] Final answer: {final}")
        return (pre + " " + final).strip()

    def _speak(self, text: str, on_sentence):
        if not on_sentence:
            return
        clean = clean_for_voice(text)
        for sentence in re.split(r"(?<=[.!?])\s+", clean.strip()):
            s = sentence.strip()
            if s:
                on_sentence(s)

    def close(self):
        pass