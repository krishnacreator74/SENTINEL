"""
tools.py — LLM-driven tools for Sentinel

Changes from previous version:
  - WebSearchTool.run() now returns a ToolResult(text, images) named tuple
    instead of a plain string, so ai.py can pass image URLs to the HUD.
  - Image URLs are extracted from web_search results via _extract_images().
  - run_tool() returns ToolResult — update callers in ai.py accordingly.

Architecture note:
  Tools return DATA. They never import or touch hud.py.
  ai.py is the bridge between tools and the HUD.
"""

import re
import json
import os
import httpx
from typing import NamedTuple

from web_search import search_and_extract
from config import MODEL_NAME

LM_STUDIO_URL   = "http://localhost:1234/v1/chat/completions"
MEMORY_FILE     = "user_memory.json"
SEARCH_HARD_CAP = 7


# ── Tool result container ──────────────────────────────────────────────────────
class ToolResult(NamedTuple):
    text:   str
    images: list[str]   # list of image URLs (may be empty)


# ── Helpers ────────────────────────────────────────────────────────────────────
def _load_user_context() -> str:
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
    specs = memory.get("specs") or memory.get("hardware") or memory.get("rig")
    if isinstance(specs, dict):
        parts.append("Rig: " + ", ".join(f"{k}={v}" for k, v in specs.items()))
    elif isinstance(specs, str):
        parts.append(f"Rig: {specs}")
    prefs = memory.get("preferences")
    if isinstance(prefs, list):
        parts.append("Preferences: " + ", ".join(prefs))
    elif isinstance(prefs, str):
        parts.append(f"Preferences: {prefs}")
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
    payload = {
        "model":       MODEL_NAME,
        "messages":    messages,
        "temperature": temperature,
        "stream":      False,
    }
    r = httpx.post(LM_STUDIO_URL, json=payload, timeout=60)
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def _extract_images(search_result: str) -> list[str]:
    """
    Pull image URLs out of raw search result text.
    web_search.py may embed image links in the result — grab up to 3.
    Filters out icons, logos, and tiny tracking pixels by extension heuristic.
    """
    # Match http(s) URLs ending in common image extensions
    pattern = re.compile(
        r'https?://[^\s\'"<>]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s\'"<>]*)?',
        re.IGNORECASE
    )
    found = pattern.findall(search_result)

    # Filter junk: very short URLs, known tracker/icon patterns
    skip_patterns = re.compile(
        r'(icon|logo|favicon|pixel|tracker|1x1|badge|avatar|thumb/\d{1,2}x)',
        re.IGNORECASE
    )
    clean = [u for u in found if not skip_patterns.search(u)]

    # Deduplicate while preserving order, take up to 3
    seen, out = set(), []
    for url in clean:
        if url not in seen:
            seen.add(url)
            out.append(url)
        if len(out) >= 3:
            break
    return out


def _ask_next_step(
    original_question: str,
    user_context: str,
    search_history: list[dict],
) -> tuple[str, str | None]:
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


# ── Base ───────────────────────────────────────────────────────────────────────
class Tool:
    name = "base"

    def detect(self, text: str) -> str | None:
        raise NotImplementedError

    def run(self, query: str, context: dict | None = None) -> ToolResult:
        raise NotImplementedError


# ── Web Search ─────────────────────────────────────────────────────────────────
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

    def run(self, query: str, context: dict | None = None) -> ToolResult:
        ctx               = context or {}
        original_question = ctx.get("original_question", query)
        user_context      = _load_user_context()

        if user_context:
            print(f"[Tool:search] User context: {user_context}")

        search_history: list[dict] = []
        all_images:     list[str]  = []
        current_query  = query

        for step in range(1, SEARCH_HARD_CAP + 1):
            print(f"[Tool:search] Step {step} — '{current_query}'")
            try:
                result = search_and_extract(current_query)
                print(f"[Tool:search] Got {len(result or '')} chars")
            except Exception as e:
                print(f"[Tool:search] Error: {e}")
                result = ""

            # Grab image URLs from this result batch
            if result:
                imgs = _extract_images(result)
                for img in imgs:
                    if img not in all_images:
                        all_images.append(img)

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

        text = _synthesise(original_question, user_context, search_history)
        # Cap images at 3 total
        return ToolResult(text=text, images=all_images[:3])


# ── Registry ───────────────────────────────────────────────────────────────────
TOOLS: list[Tool] = [
    WebSearchTool(),
]


def detect_tool(text: str) -> tuple[Tool, str] | tuple[None, None]:
    for tool in TOOLS:
        arg = tool.detect(text)
        if arg is not None:
            return tool, arg
    return None, None


def run_tool(tool: Tool, arg: str, original_question: str) -> ToolResult:
    """
    Returns ToolResult(text, images).
    In ai.py:
        result = run_tool(tool, arg, original_question)
        hud.show_text(result.text, title="SEARCH RESULTS")
        for url in result.images:
            hud.append_image(url)
    """
    return tool.run(arg, context={"original_question": original_question})