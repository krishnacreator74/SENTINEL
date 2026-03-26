"""
tools.py — LLM-driven tools for Sentinel

Each tool:
  - has a detect() function that checks if the model wants to use it
  - has a run() function that executes it and returns a result string
  - is registered in TOOLS so ai.py can iterate over them

Adding a new tool later: just add a new class and register it in TOOLS.
"""

import re
from web_search import search_and_extract

# ── Base ──────────────────────────────────────────────────────────────────────
class Tool:
    name = "base"

    def detect(self, text: str) -> str | None:
        """Return the argument/query if this tool was triggered, else None."""
        raise NotImplementedError

    def run(self, query: str) -> str:
        """Execute the tool and return a result string."""
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

    def run(self, query: str) -> str:
        print(f"[Tool:search] Running: '{query}'")
        try:
            result = search_and_extract(query)
            print(f"[Tool:search] Got {len(result)} chars")
            return result or f"No results found for '{query}'."
        except Exception as e:
            print(f"[Tool:search] Error: {e}")
            return f"Search failed: {e}"

# ── Registry ──────────────────────────────────────────────────────────────────
TOOLS: list[Tool] = [
    WebSearchTool(),
    # Add more tools here as Sentinel grows, e.g.:
    # FileReadTool(), CalendarTool(), etc.
]

def detect_tool(text: str) -> tuple[Tool, str] | tuple[None, None]:
    """Check all tools. Return (tool, argument) for the first match."""
    for tool in TOOLS:
        arg = tool.detect(text)
        if arg is not None:
            return tool, arg
    return None, None