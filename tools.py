"""
tools.py — Tool registry for Sentinel (structured output version).

Adding a new tool:
  1. Create a class extending Tool
  2. Set name = "your_tool_name"  (must match enum in JSON schema)
  3. Implement run(input, context) -> ToolResult
  4. Add instance to TOOLS list at the bottom

ai.py calls run_tool_by_name(name, input, original_question=...)
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
    images: list[str]


# ── Shared helpers ─────────────────────────────────────────────────────────────
def _load_user_context() -> str:
    if not os.path.exists(MEMORY_FILE):
        return ""
    try:
        with open(MEMORY_FILE) as f:
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
    skip = {"specs", "hardware", "rig", "preferences"}
    for k, v in memory.items():
        if k in skip:
            continue
        if isinstance(v, str):
            parts.append(f"{k}: {v}")
        elif isinstance(v, list) and all(isinstance(i, str) for i in v):
            parts.append(f"{k}: {', '.join(v)}")
    return " | ".join(parts)


def _llm(messages: list, temperature: float = 0.3) -> str:
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


def _extract_images(text: str) -> list[str]:
    pattern = re.compile(
        r'https?://[^\s\'"<>]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s\'"<>]*)?',
        re.IGNORECASE,
    )
    skip = re.compile(
        r'(icon|logo|favicon|pixel|tracker|1x1|badge|avatar|thumb/\d{1,2}x)',
        re.IGNORECASE,
    )
    seen, out = set(), []
    for url in pattern.findall(text):
        if skip.search(url) or url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= 3:
            break
    return out


# ── Base tool ──────────────────────────────────────────────────────────────────
class Tool:
    name = "base"

    def run(self, input_: str, context: dict | None = None) -> ToolResult:
        raise NotImplementedError


# ── Web Search ─────────────────────────────────────────────────────────────────
class WebSearchTool(Tool):
    name = "search"

    def run(self, input_: str, context: dict | None = None) -> ToolResult:
        ctx               = context or {}
        original_question = ctx.get("original_question", input_)
        user_context      = _load_user_context()

        search_history: list[dict] = []
        all_images:     list[str]  = []
        current_query  = input_

        for step in range(1, SEARCH_HARD_CAP + 1):
            print(f"[Search] Step {step} — '{current_query}'")
            try:
                result = search_and_extract(current_query)
            except Exception as e:
                print(f"[Search] Error: {e}")
                result = ""

            if result:
                for img in _extract_images(result):
                    if img not in all_images:
                        all_images.append(img)

            search_history.append({"query": current_query, "result": result or ""})
            action, next_query = self._ask_next_step(
                original_question, user_context, search_history
            )

            if action == "done" or next_query is None or step == SEARCH_HARD_CAP:
                break
            current_query = next_query

        text = self._synthesise(original_question, user_context, search_history)
        return ToolResult(text=text, images=all_images[:3])

    def _ask_next_step(self, original_question, user_context, search_history):
        history_block = "\n".join(
            f"  Search {i+1}: \"{h['query']}\"\n"
            f"  Result ({len(h['result'])} chars): {h['result'][:400]}..."
            for i, h in enumerate(search_history)
        )
        ctx_line = f"\nUser context: {user_context}" if user_context else ""
        user = f"""Question: "{original_question}"{ctx_line}

Searches so far:
{history_block}

Reply with exactly one of:
  DONE
  NEXT_QUERY: <query>"""

        raw = _llm([
            {"role": "system", "content": "You are a research sub-agent. Be concise. Follow the reply format exactly."},
            {"role": "user",   "content": user},
        ])
        if raw.upper().startswith("DONE"):
            return "done", None
        m = re.match(r"NEXT_QUERY:\s*(.+)", raw, re.IGNORECASE)
        if m:
            return "search", m.group(1).strip()
        return "done", None

    def _synthesise(self, original_question, user_context, search_history):
        if not any(h["result"] for h in search_history):
            return f"I couldn't find useful information for: \"{original_question}\"."
        results_block = "\n\n".join(
            f"[Search {i+1}: \"{h['query']}\"]\n{h['result'][:1000]}"
            for i, h in enumerate(search_history)
        )
        ctx_line = f"\nUser context: {user_context}" if user_context else ""
        return _llm([
            {"role": "system", "content": "You are Sentinel. Plain text only. No markdown, no bullet points, no asterisks. Concise spoken style. 3-5 sentences max."},
            {"role": "user",   "content": f'Answer: "{original_question}"{ctx_line}\n\nResults:\n{results_block}\n\nBe specific. No filler.'},
        ])


# ── Open App ───────────────────────────────────────────────────────────────────
class OpenAppTool(Tool):
    name = "open_app"

    def run(self, input_: str, context: dict | None = None) -> ToolResult:
        # Delegates to your existing launcher logic
        try:
            from app_launcher import find_and_open_app
            find_and_open_app(input_)
            return ToolResult(text=f"Opened {input_}.", images=[])
        except Exception as e:
            return ToolResult(text=f"Could not open {input_}: {e}", images=[])


# ── System Command ─────────────────────────────────────────────────────────────
class SystemCommandTool(Tool):
    name = "system_command"

    def run(self, input_: str, context: dict | None = None) -> ToolResult:
        import subprocess
        ALLOWED = {
            "shutdown":  ["shutdown", "/s", "/t", "5"],
            "restart":   ["shutdown", "/r", "/t", "5"],
            "sleep":     ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
            "lock":      ["rundll32.exe", "user32.dll,LockWorkStation"],
        }
        cmd = input_.lower().strip()
        if cmd in ALLOWED:
            subprocess.run(ALLOWED[cmd])
            return ToolResult(text=f"Executed system command: {cmd}.", images=[])
        return ToolResult(text=f"Unknown system command: {cmd}.", images=[])


# ── Registry ───────────────────────────────────────────────────────────────────
TOOLS: dict[str, Tool] = {t.name: t for t in [
    WebSearchTool(),
    OpenAppTool(),
    SystemCommandTool(),
]}


def run_tool_by_name(name: str, input_: str, original_question: str = "") -> ToolResult:
    tool = TOOLS.get(name)
    if tool is None:
        return ToolResult(text=f"Unknown tool: '{name}'.", images=[])
    return tool.run(input_, context={"original_question": original_question})