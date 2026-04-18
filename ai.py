"""
ai.py — Sentinel core, redesigned for structured JSON output.

Flow:
  1. Send messages to LM Studio (JSON mode enforced via schema)
  2. Parse the structured response — no regex fragility
  3. Execute tools in parallel if multiple requested
  4. Feed tool results back for final response
  5. Stream sentences to HUD + voice
"""

import json
import time
import threading
import httpx

from config import SYSTEM_PROMPT, MODEL_NAME, TEMPERATURE, TOP_P, TOP_K
from memory_persistent import load_memory
from memory_analyzer import analyze_and_store_memory
from tools import run_tool_by_name, ToolResult

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"


# ── Prompt builder ─────────────────────────────────────────────────────────────
def build_system_prompt() -> str:
    memory = load_memory()
    return (
        SYSTEM_PROMPT
        + "\n\nKnown user info:\n"
        + json.dumps(memory, indent=2)
    )


# ── Memory helper ──────────────────────────────────────────────────────────────
def run_memory_async(user_text: str, assistant_text: str):
    def task():
        try:
            analyze_and_store_memory(user_text, assistant_text)
        except Exception as e:
            print(f"[Memory] Error: {e}")
    threading.Thread(target=task, daemon=True).start()


# ── LM Studio call (non-streaming, JSON mode) ──────────────────────────────────
def _call_lm(messages: list, max_tokens: int = 500) -> dict:
    """
    Calls LM Studio with structured output enforced.
    Returns parsed dict from model JSON, or empty dict on failure.
    LM Studio enforces the schema you pasted in its UI — we just parse.
    """
    payload = {
        "model":       MODEL_NAME,
        "messages":    messages,
        "temperature": TEMPERATURE,
        "top_p":       TOP_P,
        "top_k":       TOP_K,
        "stream":      False,
        "max_tokens":  max_tokens,
        # NOTE: Do NOT add response_format here — LM Studio doesn't support it
        # and returns 400. Structured output is enforced via the LM Studio UI schema.
    }
    try:
        r = httpx.post(
            LM_STUDIO_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=90,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        print(f"[AI] Raw JSON: {raw[:300]}")
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[AI] JSON parse error: {e}")
        return {}
    except Exception as e:
        print(f"[AI] Call error: {e}")
        return {}


# ── Sentence splitter (unchanged — still needed for HUD/voice) ────────────────
import re

def _split_sentences(text: str) -> list[str]:
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
        if re.match(r"^\d+\.\s", line):
            if current:
                blocks.append(current.strip())
                current = ""
            blocks.append(line)
            continue
        if line.endswith(":") and len(line) < 80:
            if current:
                blocks.append(current.strip())
                current = ""
            blocks.append(line)
            continue
        current += (" " if current else "") + line
    if current:
        blocks.append(current.strip())
    result = []
    for block in blocks:
        if re.match(r"^\d+\.", block) or (block.endswith(":") and len(block) < 80):
            result.append(block)
            continue
        parts = re.split(r"(?<=[^0-9\s][.!?])\s+(?=[A-Z])", block)
        result.extend(p.strip() for p in parts if p.strip())
    return result


# ── HUD + voice delivery ───────────────────────────────────────────────────────
def _speak(text: str, on_sentence, hud=None, use_hud: bool = False, title: str = "SENTINEL"):
    import voice as _voice
    if not on_sentence:
        if hud and use_hud:
            hud.finish_all()
        return
    sentences = _split_sentences(text)
    if not sentences:
        return
    if hud and use_hud:
        hud.load_sentences(sentences, title=title)
        time.sleep(0.08)
    for idx, sentence in enumerate(sentences):
        _voice.set_sentence_idx(idx if (hud and use_hud) else -1)
        on_sentence(sentence)
    if hud and use_hud:
        hud.finish_all()


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
    
    def _execute_tool(self, name: str, input_: str, original_question: str):
        return run_tool_by_name(
            name,
            input_,
            original_question=original_question
        )

    def respond(self, messages: list, on_sentence=None, hud=None) -> str:
        """
        Main entry point. Replaces respond_stream.

        1. Ask model → get structured JSON
        2. If tools requested → run them (parallel if multiple)
        3. If awaiting_tool_result → call model again with results
        4. Speak + HUD the final response
        """
        print("[AI] Calling model...")
        result = _call_lm(messages)

        if not result:
            msg = "I had trouble generating a response. Please try again."
            if on_sentence:
                on_sentence(msg)
            return msg
    


        # ── Step 1: announce if we're about to tool ────────────────────────────
        tools_requested = result.get("tools", [])
        response_text   = result.get("response", "")
        use_hud         = result.get("hud", False)
        awaiting        = result.get("awaiting_tool_result", False)

        print(f"[AI] thought: {result.get('thought', '')}")
        print(f"[AI] tools: {tools_requested}")
        print(f"[AI] response: {response_text[:100]}")
        print(f"[AI] hud: {use_hud} | awaiting: {awaiting}")

        # Speak the pre-tool response (e.g. "Let me search that for you")
        if response_text:
            _speak(response_text, on_sentence, hud, use_hud=use_hud and not awaiting)

        # ── Step 2: run tools ──────────────────────────────────────────────────
        if not tools_requested or not awaiting:
            return response_text

        tool_results = self._run_tools_parallel(tools_requested, messages)

        # ── Step 3: follow-up call with tool results ───────────────────────────
        tool_context = self._build_tool_context(tools_requested, tool_results)
        # CORRECT — flatten system prompt separately, keep full history
        followup_messages = [messages[0]] + [  # system prompt
            {"role": "user",      "content": messages[-1]["content"]},  # original question
            {"role": "assistant", "content": json.dumps(result)},       # first model turn
            {"role": "user",      "content": tool_context},             # tool results
        ]
        print(f"[AI] Follow-up call with {len(followup_messages)} messages")
        print("[AI] Calling model with tool results...")

        final_result = _call_lm(followup_messages, max_tokens=600)

        if not final_result:
            fallback = "I got the results but had trouble summarizing. Please try again."
            if on_sentence:
                on_sentence(fallback)
            return fallback

        final_text = final_result.get("response", "")
        final_hud  = True if len(final_text) > 80 else final_result.get("hud", False)

        # Inject images to HUD from any search results
        all_images = []
        for tr in tool_results:
            if hasattr(tr, "images"):
                all_images.extend(tr.images)

        _speak(final_text, on_sentence, hud, use_hud=final_hud, title="SENTINEL")

        if hud and all_images:
            def _imgs():
                time.sleep(0.5)
                for url in all_images[:3]:
                    hud.append_image(url)
            threading.Thread(target=_imgs, daemon=True).start()

        return final_text

    def _run_tools_parallel(self, tools_requested: list, messages: list) -> list:
        """
        Runs all requested tools in parallel threads.
        Returns list of ToolResult in same order.
        """
        results = [None] * len(tools_requested)

        # Pull original user question for search context
        original_question = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                original_question = msg["content"]
                break

        def _run(idx, tool_def):
            name  = tool_def.get("name", "")
            input_ = tool_def.get("input", "")
            print(f"[AI] Running tool '{name}' with input: '{input_}'")
            try:
                results[idx] = self._execute_tool(
                    name,
                    input_,
                    original_question
                )
            except Exception as e:
                print(f"[AI] Tool '{name}' error: {e}")
                results[idx] = ToolResult(text=f"Tool '{name}' failed: {e}", images=[])

        threads = [
            threading.Thread(target=_run, args=(i, t), daemon=True)
            for i, t in enumerate(tools_requested)
        ]
        for t in threads: t.start()
        for t in threads: t.join(timeout=60)

        return results

    def _build_tool_context(self, tools_requested: list, tool_results: list) -> str:
        parts = ["Here are the tool results. Now give your FINAL response to the user."]
        parts.append("Do NOT call any tools again. Set tools to [] and awaiting_tool_result to false.")
        for tool_def, result in zip(tools_requested, tool_results):
            name = tool_def.get("name", "unknown")
            text = result.text if result else "No result."
            parts.append(f"\n[{name.upper()} RESULT]\n{text}")
        return "\n".join(parts)

    def close(self):
        pass