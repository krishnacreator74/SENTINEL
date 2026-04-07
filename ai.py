import re
import json
import time
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

DISPLAY WINDOW:
You have a HUD popup window available. When your response contains:
  - News / current events
  - Search results
  - Lists, comparisons, or structured info
  - Weather details
  - Anything the user would benefit from reading (not just hearing)

Start your response with [HUD] on its own line.
The window will appear automatically.
If your response is conversational or a simple one-liner, do NOT use [HUD].

Example:
[HUD]
Here are today's top headlines...

Do NOT use [HUD] for: greetings, confirmations, short answers, errors.
"""

# ── Text helpers ───────────────────────────────────────────────────────────────
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
    text = re.sub(r"(?m)^\[HUD(?:\s+\w+=\w+)?\]\s*$", "", text)
    text = re.sub(r"\*\*|\*", "", text)
    text = re.sub(r"`[^`]*`", lambda m: m.group(0).strip("`"), text)
    text = text.replace("e.g.", "for example").replace("i.e.", "that is")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def _has_hud_tag(raw: str) -> bool:
    return bool(re.search(r"(?m)^\[HUD", _strip_thinking(raw), re.IGNORECASE))

def _split_sentences(text: str) -> list[str]:
    """
    Split cleaned voice text into display blocks for the HUD.

    Rules:
    - Numbered list items (e.g. "1. Phone news: ...") are kept as single blocks
      — we never split on a period that follows a digit at line/sentence start.
    - Normal prose is split on sentence-ending punctuation (.!?) followed by space.
    - Empty strings are dropped.
    """
    lines   = text.splitlines()
    blocks  = []
    current = ""

    for line in lines:
        line = line.strip()
        if not line:
            if current:
                blocks.append(current.strip())
                current = ""
            continue

        # Numbered list item — e.g. "1." "2." "10." at start of line
        if re.match(r"^\d+\.\s", line):
            if current:
                blocks.append(current.strip())
                current = ""
            blocks.append(line)
            continue

        # Heading-like short line ending with colon — keep as its own block
        if line.endswith(":") and len(line) < 80:
            if current:
                blocks.append(current.strip())
                current = ""
            blocks.append(line)
            continue

        # Normal prose: accumulate and split on sentence boundaries
        current += (" " if current else "") + line

    if current:
        blocks.append(current.strip())

    # Now split any accumulated prose blocks on sentence boundaries
    result = []
    for block in blocks:
        # Don't re-split numbered items or short headings
        if re.match(r"^\d+\.", block) or (block.endswith(":") and len(block) < 80):
            result.append(block)
            continue
        # Split on . ! ? followed by whitespace — but NOT on digits ("3.5", "1.")
        parts = re.split(r"(?<=[^0-9\s][.!?])\s+(?=[A-Z])", block)
        result.extend(p.strip() for p in parts if p.strip())

    return result

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

# ── API helpers ────────────────────────────────────────────────────────────────
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
                if "\n" in full and _SEARCH_LINE_RE.search(full):
                    print("\n[AI] SEARCH line complete — cutting stream.")
                    break
    except Exception as e:
        print(f"\n[AI] Stream error: {e}")
    print()
    return full


# ── Core AI class ──────────────────────────────────────────────────────────────
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

    def respond_stream(self, messages: list, on_sentence=None, hud=None) -> str:
        print("[AI] Responding...")

        raw   = _stream_full(messages)
        clean = _strip_thinking(raw)
        print(f"[AI] Clean response: {len(clean)} chars")

        if not clean:
            msg = "I had trouble generating a response. Please try again."
            if on_sentence: on_sentence(msg)
            return msg

        tool, arg = detect_tool(clean)

        # ── Branch A: no tool ─────────────────────────────────────────────────
        if tool is None:
            should_hud = _has_hud_tag(raw)
            self._speak(clean, on_sentence, hud, use_hud=should_hud)
            return clean_for_voice(clean)

        # ── Branch B: tool ────────────────────────────────────────────────────
        print(f"[AI] Tool '{tool.name}' triggered with: '{arg}'")

        pre = re.split(r"SEARCH:", clean, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if pre:
            self._speak(clean_for_voice(pre), on_sentence, hud=None, use_hud=False)

        if on_sentence:
            on_sentence("Let me search that for you.")

        original_question = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                original_question = msg["content"]
                break

        result = run_tool(tool, arg, original_question=original_question)
        print(f"[AI] Tool result: {len(result.text)} chars, {len(result.images)} images")

        final = clean_for_voice(_strip_thinking(result.text))
        if not final:
            final = "I found some results but had trouble summarizing them. Try again."

        self._speak(final, on_sentence, hud, use_hud=True, title="SEARCH RESULTS")

        if hud is not None and result.images:
            def _imgs():
                time.sleep(0.5)
                for url in result.images:
                    hud.append_image(url)
            threading.Thread(target=_imgs, daemon=True).start()

        print(f"[AI] Final answer: {final}")
        return final

    def _speak(
        self,
        text: str,
        on_sentence,
        hud=None,
        use_hud: bool = False,
        title: str = "SENTINEL",
    ):
        """
        Split text into sentences, load them into the HUD (if use_hud),
        then speak each one — HUD highlights the active sentence in real time.
        """
        import voice as _voice

        if not on_sentence:
            if hud and use_hud:
                hud.finish_all()
            return

        voice_text = clean_for_voice(text)
        sentences  = _split_sentences(voice_text)

        if not sentences:
            return

        # Load all sentences into HUD upfront so the user sees the full response
        if hud and use_hud:
            hud.load_sentences(sentences, title=title)
            time.sleep(0.08)   # let Qt paint before first sentence starts

        for idx, sentence in enumerate(sentences):
            # Tell voice.py which sentence index is about to play
            _voice.set_sentence_idx(idx if (hud and use_hud) else -1)
            on_sentence(sentence)   # blocks until Piper finishes

        # Safety: make sure all blocks are white after speaking
        if hud and use_hud:
            hud.finish_all()

    def close(self):
        pass