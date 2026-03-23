import re
import json
import threading
import httpx
from config import SYSTEM_PROMPT, MODEL_NAME, TEMPERATURE, TOP_P, TOP_K
from memory_persistent import load_memory
from memory_analyzer import analyze_and_store_memory

# ── Constants ────────────────────────────────────────────────────────────────
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
# ── Text helpers ─────────────────────────────────────────────────────────────
def clean_for_voice(text: str) -> str:
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*",   "", text)
    text = text.replace("e.g.", "for example")
    text = text.replace("i.e.", "that is")
    return text

def validate_messages(messages: list) -> list:
    """Remove consecutive messages with the same role."""
    fixed, last_role = [], None
    for msg in messages:
        if msg["role"] == last_role:
            continue
        fixed.append(msg)
        last_role = msg["role"]
    return fixed

# ── Search ───────────────────────────────────────────────────────────────────

def get_web_context(query: str) -> str:
    from web_search import search_and_extract
    try:
        ctx = search_and_extract(query)
        print(f"[Search] Got {len(ctx)} chars")
        return ctx
    except Exception as e:
        print(f"[Search] Failed: {e}")
        return ""

# ── Prompt building ───────────────────────────────────────────────────────────
def build_system_prompt(web_context: str = "") -> str:
    memory = load_memory()
    prompt = (
        SYSTEM_PROMPT
        + "\n\nKnown user information:\n"
        + json.dumps(memory, indent=2)
    )
    if web_context:
        prompt += (
            "\n\n[SYSTEM SEARCH RESULT]\n"
            "The following data was automatically fetched from the web before this conversation turn. "
            "Treat it as factual current information and summarize it for the user. "
            "Never say you cannot access the internet — the search already happened:\n\n"
            + web_context
        )
    return prompt

# ── Memory ───────────────────────────────────────────────────────────────────
def run_memory_async(user_text: str, assistant_text: str):
    def task():
        try:
            analyze_and_store_memory(user_text, assistant_text)
        except Exception as e:
            print(f"[Memory] Error: {e}")
    threading.Thread(target=task, daemon=True).start()

# ── Core AI class ─────────────────────────────────────────────────────────────
class SentinelAI:
    def __init__(self):
        self._verify_connection()

    def _verify_connection(self):
        """Check LM Studio is reachable before proceeding."""
        try:
            r = httpx.get("http://localhost:1234/v1/models", timeout=5)
            models = r.json().get("data", [])
            if models:
                print(f"[AI] Connected. Available models: {[m['id'] for m in models]}")
            else:
                print("[AI] Connected but no models loaded in LM Studio.")
        except Exception as e:
            raise RuntimeError(
                f"[AI] Cannot reach LM Studio at localhost:1234 — is it running? ({e})"
            )

    def respond_stream(self, messages: list, on_sentence=None) -> str:
        """
        Stream a response from the model via OpenAI-compatible API.

        Args:
            messages:    Full validated message list (including system prompt).
            on_sentence: Optional callback called with each sentence-chunk
                         as it arrives (used for TTS).

        Returns:
            The complete response string.
        """
        payload = {
            "model":       MODEL_NAME,
            "messages":    messages,
            "temperature": TEMPERATURE,
            "top_p":       TOP_P,
            "stream":      True,
        }

        buffer        = ""
        full_response = ""

        try:
            with httpx.stream(
                "POST",
                LM_STUDIO_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break

                    try:
                        data = json.loads(chunk)
                        text = data["choices"][0]["delta"].get("content", "")
                    except (json.JSONDecodeError, KeyError):
                        continue

                    if not text:
                        continue

                    # Hard-stop if model tries to self-search
                    if "SEARCH:" in full_response + text:
                        print("[AI] Suppressed SEARCH: token.")
                        break

                    full_response += text
                    buffer        += text
                    print(text, end="", flush=True)

                    if re.search(r"[.!?]", buffer):
                        if on_sentence:
                            on_sentence(clean_for_voice(buffer.strip()))
                        buffer = ""

        except httpx.HTTPStatusError as e:
            print(f"[AI] HTTP error: {e.response.status_code} — {e.response.text}")
        except Exception as e:
            print(f"[AI] Stream error: {e}")

        # Flush remaining buffer
        if buffer.strip():
            if on_sentence:
                on_sentence(clean_for_voice(buffer.strip()))

        print()
        return full_response.strip()

    def close(self):
        pass  # No persistent connection to close with httpx