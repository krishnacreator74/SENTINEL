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
from tools.context_helpers import load_user_context
from tools.web_search import search_and_extract
from system.config import MODEL_NAME
from tools.helpers import llm, extract_images
class ToolResult(NamedTuple):
    text: str
    images: list[str]

LM_STUDIO_URL   = "http://localhost:1234/v1/chat/completions"
MEMORY_FILE     = "user_memory.json"
SEARCH_HARD_CAP = 7

# ── Base tool ──────────────────────────────────────────────────────────────────
class Tool:
    name = "base"

    def run(self, input_text: str, context: dict | None = None) -> ToolResult:
        raise NotImplementedError


# ── Web Search ─────────────────────────────────────────────────────────────────
class WebSearchTool(Tool):
    name = "search"

    def run(self, input_text: str, context: dict | None = None) -> ToolResult:
        ctx               = context or {}
        original_question = ctx.get("original_question", input_text)
        user_context      = load_user_context()

        search_history: list[dict] = []
        all_images:     list[str]  = []
        current_query  = input_text

        for step in range(1, SEARCH_HARD_CAP + 1):
            print(f"[Search] Step {step} — '{current_query}'")
            try:
                result = search_and_extract(current_query)
            except Exception as e:
                print(f"[Search] Error: {e}")
                result = ""

            if result:
                for img in extract_images(result):
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

        raw = llm([
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
        return llm([
            {"role": "system", "content": "You are Sentinel. Plain text only. No markdown, no bullet points, no asterisks. Concise spoken style. 3-5 sentences max."},
            {"role": "user",   "content": f'Answer: "{original_question}"{ctx_line}\n\nResults:\n{results_block}\n\nBe specific. No filler.'},
        ])


# ── Open App ───────────────────────────────────────────────────────────────────
class OpenAppTool(Tool):
    name = "open_app"

    def run(self, input_text: str, context: dict | None = None) -> ToolResult:
        # Delegates to your existing launcher logic
        try:
            from system.commands import launch_app_from_command
            launch_app_from_command(f"open {input_text}")
            return ToolResult(text=f"Opened {input_text}.", images=[])
        except Exception as e:
            return ToolResult(text=f"Could not open {input_text}: {e}", images=[])


# ── System Command ─────────────────────────────────────────────────────────────
class SystemCommandTool(Tool):
    name = "system_command"

    def run(self, input_text: str, context: dict | None = None) -> ToolResult:
        import subprocess
        ALLOWED = {
            "shutdown":  ["shutdown", "/s", "/t", "5"],
            "restart":   ["shutdown", "/r", "/t", "5"],
            "sleep":     ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
            "lock":      ["rundll32.exe", "user32.dll,LockWorkStation"],
        }
        cmd = input_text.lower().strip()
        if cmd in ALLOWED:
            subprocess.run(ALLOWED[cmd])
            return ToolResult(text=f"Executed system command: {cmd}.", images=[])
        return ToolResult(text=f"Unknown system command: {cmd}.", images=[])


# ── Registry ───────────────────────────────────────────────────────────────────
TOOLS: dict[str, Tool] = {}

def register_tool(tool: Tool):
    TOOLS[tool.name] = tool


# ── Register tools ──
register_tool(WebSearchTool())
register_tool(OpenAppTool())
register_tool(SystemCommandTool())


def run_tool_by_name(name: str, input_text: str, original_question: str = "") -> ToolResult:
    tool = TOOLS.get(name)

    if tool is None:
        return ToolResult(text=f"Unknown tool: '{name}'.", images=[])

    try:
        return tool.run(
            input_text,
            context={"original_question": original_question}
        )
    except Exception as e:
        return ToolResult(
            text=f"Tool '{name}' failed: {e}",
            images=[]
        )