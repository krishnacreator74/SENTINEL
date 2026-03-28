"""
tools.py — LLM-driven tools for Sentinel

Each tool:
  - has a detect() function that checks if the model wants to use it
  - has a run() function that executes it and returns a result string
  - is registered in TOOLS so ai.py can iterate over them

WebSearchTool is autonomous:
  - The LLM decides how many searches to run (says DONE when satisfied)
  - SEARCH_HARD_CAP is a safety net only — LLM controls depth in practice
  - User context (rig specs, preferences etc.) is read from user_memory.json
    via the existing memory system — no profile logic lives here

Adding a new tool: subclass Tool, implement detect() + run(), add to TOOLS.
"""

import re
import json
import os
import httpx

from web_search import search_and_extract
from config import MODEL_NAME

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MEMORY_FILE    = "user_memory.json"
SEARCH_HARD_CAP = 7   # absolute maximum searches — LLM normally stops before this


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_user_context() -> str:
    """
    Read user_memory.json and flatten it into a short string for LLM prompts.
    Returns an empty string if the file doesn't exist or has nothing useful.
    """
    if not os.path.exists(MEMORY_FILE):
        return ""
    try:
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
    except Exception:
        return ""

    if not memory:
        return ""

    parts = []

    # Hardware / rig specs
    specs = memory.get("specs") or memory.get("hardware") or memory.get("rig")
    if isinstance(specs, dict):
        parts.append("Rig: " + ", ".join(f"{k}={v}" for k, v in specs.items()))
    elif isinstance(specs, str):
        parts.append(f"Rig: {specs}")

    # Preferences
    prefs = memory.get("preferences")
    if isinstance(prefs, list):
        parts.append("Preferences: " + ", ".join(prefs))
    elif isinstance(prefs, str):
        parts.append(f"Preferences: {prefs}")

    # Anything else that looks like a simple string or short list
    skip_keys = {"specs", "hardware", "rig", "preferences"}
    for key, val in memory.items():
        if key in skip_keys:
            continue
        if isinstance(val, str):
            parts.append(f"{key}: {val}")
        elif isinstance(val, list) and all(isinstance(i, str) for i in val):
            parts.append(f"{key}: {', '.join(val)}")

    return " | ".join(parts)


def _llm(messages: list[dict], temperature: float = 0.3) -> str:
    """Thin wrapper around LM Studio — returns the assistant reply as a string."""
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    r = httpx.post(LM_STUDIO_URL, json=payload, timeout=60)
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    # Strip <think>...</think> blocks some models emit
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def _ask_next_step(
    original_question: str,
    user_context: str,
    search_history: list[dict],
) -> tuple[str, str | None]:
    """
    Ask the LLM what to do after the latest search.

    Returns:
      ("done",   None)           — enough info, stop
      ("search", "<next query>") — keep going with this query
    """
    history_block = "\n".join(
        f"  Search {i+1}: \"{h['query']}\"\n"
        f"  Result ({len(h['result'])} chars): {h['result'][:400]}..."
        for i, h in enumerate(search_history)
    )
    user_ctx_line = f"\nUser context: {user_context}" if user_context else ""

    system = "You are a research sub-agent. Be concise. Follow the reply format exactly."
    user   = f"""Question: "{original_question}"{user_ctx_line}

Searches so far:
{history_block}

What next? Reply with exactly one of:

  DONE
    (you have enough to answer well)

  NEXT_QUERY: <query>
    (you need more info — use a different angle or broader/narrower terms;
     never repeat a query already tried)

No explanation. Just DONE or NEXT_QUERY: <query>."""

    raw = _llm([{"role": "system", "content": system},
                {"role": "user",   "content": user}])

    if raw.upper().startswith("DONE"):
        return "done", None

    m = re.match(r"NEXT_QUERY:\s*(.+)", raw, re.IGNORECASE)
    if m:
        return "search", m.group(1).strip()

    print(f"[Tool:search] Unexpected LLM output: '{raw}' — treating as DONE")
    return "done", None


def _synthesise(
    original_question: str,
    user_context: str,
    search_history: list[dict],
) -> str:
    """Turn all gathered search results into a final answer."""
    if not any(h["result"] for h in search_history):
        return f"I couldn't find useful information for: \"{original_question}\"."

    results_block = "\n\n".join(
        f"[Search {i+1}: \"{h['query']}\"]\n{h['result'][:1000]}"
        for i, h in enumerate(search_history)
    )
    user_ctx_line = f"\nUser context: {user_context}" if user_context else ""

    system = "You are Sentinel, a helpful AI assistant. Answer clearly and directly."
    user   = f"""Answer this question:
"{original_question}"{user_ctx_line}

Web search results:
{results_block}

If exact info wasn't found, use the closest data available and relate it to the
user's hardware/preferences if known. Be specific. No filler."""

    return _llm([{"role": "system", "content": system},
                 {"role": "user",   "content": user}])


# ── Base ──────────────────────────────────────────────────────────────────────

class Tool:
    name = "base"

    def detect(self, text: str) -> str | None:
        """Return the argument/query if this tool was triggered, else None."""
        raise NotImplementedError

    def run(self, query: str, context: dict | None = None) -> str:
        """Execute and return a result string."""
        raise NotImplementedError


# ── Web Search ────────────────────────────────────────────────────────────────

_SEARCH_RE = re.compile(r"SEARCH:\s*(.+?)(?:\n|$)", re.IGNORECASE)


class WebSearchTool(Tool):
    name = "web_search"

    def detect(self, text: str) -> str | None:
        m = _SEARCH_RE.search(text)
        if not m:
            return None
        query = m.group(1).strip().replace("_", " ")
        words = [w for w in query.split() if len(w) > 1]
        if len(words) < 2:
            print(f"[Tool:search] Rejected vague query: '{query}'")
            return None
        return " ".join(words)

    def run(self, query: str, context: dict | None = None) -> str:
        """
        Autonomous multi-step search. The LLM decides when to stop (DONE).
        SEARCH_HARD_CAP is only a safety net.

        context:
          "original_question": str  — the full user message (used in synthesis)
        """
        ctx               = context or {}
        original_question = ctx.get("original_question", query)
        user_context      = _load_user_context()   # always pulled fresh from memory

        if user_context:
            print(f"[Tool:search] User context: {user_context}")

        search_history: list[dict] = []
        current_query = query

        for step in range(1, SEARCH_HARD_CAP + 1):
            print(f"[Tool:search] Step {step} — '{current_query}'")
            try:
                result = search_and_extract(current_query)
                print(f"[Tool:search] Got {len(result or '')} chars")
            except Exception as e:
                print(f"[Tool:search] Error: {e}")
                result = ""

            search_history.append({"query": current_query, "result": result or ""})

            action, next_query = _ask_next_step(
                original_question, user_context, search_history
            )

            if action == "done" or next_query is None:
                print(f"[Tool:search] LLM satisfied after {step} step(s).")
                break

            if step == SEARCH_HARD_CAP:
                print(f"[Tool:search] Hit hard cap ({SEARCH_HARD_CAP}).")
                break

            current_query = next_query

        return _synthesise(original_question, user_context, search_history)


# ── Registry ──────────────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    WebSearchTool(),
    # Add more tools here, e.g. FileReadTool(), CalendarTool()
]


def detect_tool(text: str) -> tuple[Tool, str] | tuple[None, None]:
    """Return (tool, argument) for the first matching tool, or (None, None)."""
    for tool in TOOLS:
        arg = tool.detect(text)
        if arg is not None:
            return tool, arg
    return None, None


def run_tool(tool: Tool, arg: str, original_question: str) -> str:
    """
    Call from ai.py instead of tool.run() directly.
    Passes the full user question so the tool can use it for synthesis.

    Usage in ai.py:
        from tools import detect_tool, run_tool

        tool, arg = detect_tool(model_output)
        if tool:
            result = run_tool(tool, arg, original_question=user_message)
    """
    return tool.run(arg, context={"original_question": original_question})