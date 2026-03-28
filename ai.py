import re
import json
import threading
import httpx
from config import SYSTEM_PROMPT, MODEL_NAME, TEMPERATURE, TOP_P, TOP_K
from memory_persistent import load_memory
from memory_analyzer import analyze_and_store_memory
from tools import detect_tool, run_tool

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

TOOL_INSTRUCTIONS = """
You have access to a web search tool. Use it whenever the user asks you to search,
look something up, or when you need current information you don't have.

To search, write this on its own line — nothing else, no other text:
SEARCH: <your query>

Use SEARCH for: current news, live prices, scores, weather, recent game releases,
game settings, coding benchmarks, tech comparisons, or anything the user explicitly
asks you to search for.

IMPORTANT: If you decide to search, write ONLY the SEARCH line. Do not write any
other text before or after it. The search results will come back and you will
answer then.

Query must have at least 2 specific words. Only search once per reply.
"""

# ── Text helpers ──────────────────────────────────────────────────────────────
def _strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*",          "", text, flags=re.DOTALL)
    text = re.sub(r"Thinking Process:.*?(?=\n[A-Z]|\Z)", "", text, flags=re.DOTALL)
    return text.strip()

def _strip_tool_lines(text: str) -> str:
    return re.sub(r"(?m)^SEARCH:.*$", "", text, flags=re.IGNORECASE).strip()

def clean_for_voice(text: str) -> str:
    text = _strip_thinking(text)
    text = _strip_tool_lines(text)
    text = re.sub(r"\*\*|\*", "", text)
    text = text.replace("e.g.", "for example").replace("i.e.", "that is")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

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

_SEARCH_LINE_RE = re.compile(r"SEARCH:\s*.{3,}", re.IGNORECASE)

def _stream_full(messages: list) -> str:
    """
    Stream token by token. Cuts off early once a complete SEARCH: line is
    detected — prevents Qwen from hallucinating an answer in the same turn
    after emitting the SEARCH: trigger.
    """
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
                # Cut stream the moment a complete SEARCH: line has arrived
                if "\n" in full and _SEARCH_LINE_RE.search(full):
                    print("\n[AI] SEARCH line complete — cutting stream.")
                    break
    except Exception as e:
        print(f"\n[AI] Stream error: {e}")
    print()
    return full

def _call_sync(messages: list, max_tokens: int = 400) -> str:
    try:
        print(f"[AI] Sync call ({len(messages)} messages)...")
        r = httpx.post(
            LM_STUDIO_URL,
            json=_payload(messages, stream=False, max_tokens=max_tokens),
            timeout=90
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"] or ""
        print(f"[AI] Sync got {len(content)} chars")
        return content
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

        # ── Step 1: stream first response ─────────────────────────────────────
        raw = _stream_full(messages)
        clean = _strip_thinking(raw)
        print(f"[AI] Clean response: {len(clean)} chars")

        if not clean:
            msg = "I had trouble generating a response. Please try again."
            if on_sentence:
                on_sentence(msg)
            return msg

        # ── Step 2: check for tool trigger ────────────────────────────────────
        tool, arg = detect_tool(clean)

        if tool is None:
            self._speak(clean, on_sentence)
            return clean_for_voice(clean)

        # ── Step 3: run the tool ──────────────────────────────────────────────
        print(f"[AI] Tool '{tool.name}' triggered with: '{arg}'")

        # Only speak what came BEFORE the SEARCH: line — discard everything
        # after it (Qwen often hallucinates an answer right after the SEARCH
        # line in the same response; we never want that spoken or used).
        pre = re.split(r"SEARCH:", clean, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        pre = clean_for_voice(pre)
        if pre:
            print(f"[AI] Pre-search text: {pre[:80]}...")
            self._speak(pre, on_sentence)

        if on_sentence:
            on_sentence("Let me search that for you.")

        # Get original user question
        original_question = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                original_question = msg["content"]
                break

        tool_result = run_tool(tool, arg, original_question=original_question)
        print(f"[AI] Tool result: {len(tool_result)} chars")

        # ── Step 4: build clean messages for grounded answer ──────────────────
        # Discard the model's entire first response — it may contain
        # hallucinated settings written after the SEARCH: line.
        # Inject results as a fresh user turn so the model answers only
        # from real search data.

        new_messages = list(messages)  # already ends with the user question
        new_messages.append({
            "role": "assistant",
            "content": "Let me search that for you."
        })
        new_messages.append({
            "role": "user",
            "content": (
                "=== SEARCH RESULTS ===\n"
                + tool_result
                + "\n=== END RESULTS ===\n\n"
                "Based only on the search results above, answer my original question. "
                "Plain text. 3 to 5 sentences. No bullet points. No markdown. "
                "Do not say you need more info. Do not ask follow-up questions."
            )
        })

        # ── Step 5: get grounded answer ───────────────────────────────────────
        raw_answer = _call_sync(new_messages, max_tokens=400)
        final = clean_for_voice(_strip_thinking(raw_answer))

        if not final:
            final = "I found some results but had trouble summarizing them. Try asking again."

        self._speak(final, on_sentence)
        print(f"[AI] Final answer: {final}")
        return final

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