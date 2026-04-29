"""
note_tool.py — Sentinel Tool wrapper for Note Taker.

This is the ONLY file in the note_taker module that knows about Sentinel.
It extends the Tool base class and delegates everything to the module's
public API (start / stop / is_active).

To register with Sentinel, add to TOOLS list in tools.py:
    from modules.note_taker.note_tool import NoteTakerTool
    TOOLS = [..., NoteTakerTool()]

Sentinel schema enum must include "note_taker" in the tools name enum.

Supported input_text values:
    "start"               — start with interactive region selector
    "stop"                — stop current session
    "status"              — check if running
    JSON: {"region": [x, y, w, h]}  — start with a specific region
"""

import json
import sys
import os

# Make sure Sentinel's root is importable regardless of working directory
_SENTINEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SENTINEL_ROOT not in sys.path:
    sys.path.insert(0, _SENTINEL_ROOT)

from tools import Tool, ToolResult
from modules.note_taker import start, stop, is_active


class NoteTakerTool(Tool):
    """
    Sentinel tool interface for the Note Taker module.

    Commands:
        start  — begin a session (shows region selector if no region given)
        stop   — end the current session and return notes path
        status — report whether a session is active
    """
    name = "note_taker"

    def run(self, input_text: str, context: dict | None = None) -> ToolResult:
        cmd = input_text.strip().lower()

        # ── start ──────────────────────────────────────────────────────────────
        if cmd == "start":
            result = start(region=None)
            return ToolResult(text=result, images=[])

        # ── start with explicit region ─────────────────────────────────────────
        if cmd.startswith("{"):
            try:
                params = json.loads(input_text)
                region = params.get("region")
                if region and len(region) == 4:
                    result = start(region=tuple(region))
                    return ToolResult(text=result, images=[])
            except json.JSONDecodeError:
                pass
            return ToolResult(
                text="Invalid JSON. Expected: {\"region\": [x, y, w, h]}",
                images=[],
            )

        # ── stop ───────────────────────────────────────────────────────────────
        if cmd == "stop":
            result = stop()
            return ToolResult(text=result, images=[])

        # ── status ─────────────────────────────────────────────────────────────
        if cmd == "status":
            active = is_active()
            msg    = "Note-taking is active." if active else "No active session."
            return ToolResult(text=msg, images=[])

        # ── unknown ────────────────────────────────────────────────────────────
        return ToolResult(
            text=(
                "Unknown note_taker command. "
                "Use: start | stop | status | {\"region\": [x, y, w, h]}"
            ),
            images=[],
        )