"""
pipeline.py — SentinelPipeline
This module defines the SentinelPipeline class, which serves as the core processing unit for handling user requests, interacting with the AI model,
and managing the conversation history.The pipeline takes user input, constructs the appropriate message format for the AI,
and processes the AI's response to update the conversation memory and generate output for the UI.

Key components:
- SentinelPipeline: The main class that orchestrates the processing of user requests, interaction with the AI, and memory management.

Key functions:
- process: Takes a user request, checks for built-in commands, updates the conversation history, and calls the AI to generate a response. It also handles the integration with the HUD and UI bridge for thread-safe operations.
"""

from core.ai import build_system_prompt, run_memory_async
from system.router import _add_close_hud_command, fast_route


def _dedup_roles(messages: list) -> list:
    fixed, last_role = [], None
    for msg in messages:
        if msg["role"] == last_role:
            continue
        fixed.append(msg)
        last_role = msg["role"]
    return fixed


class SentinelPipeline:
    def __init__(self, ai, memory):
        self.ai     = ai
        self.memory = memory

    def process(self, req: str, speak_fn=None, bridge=None, emitter=None):
        # HUD close command
        if _add_close_hud_command(req, emitter):
            return "__handled__"
        
        # Fast route (built-in commands)
        if fast_route(req,emitter):
            return "__handled__"

        # Add user message
        if not self.memory.messages or self.memory.messages[-1]["role"] != "user":
            self.memory.add_user(req)

        # Build messages
        messages = _dedup_roles(
            [{"role": "system", "content": build_system_prompt()}]
            + self.memory.get_messages()
        )

        # Call AI — pass bridge so HUD signals are thread-safe
        result = self.ai.respond(
            messages,
            on_sentence=speak_fn,
            bridge=bridge,
        )

        if not result:
            return None

        full_response = result["text"]
        parsed_json   = result["raw"]

        if not full_response:
            return None

        run_memory_async(parsed_json)
        self.memory.add_assistant(full_response)

        return full_response