# SentinelPipeline: A Modular AI Interaction Pipeline
# This file defines the SentinelPipeline class, which encapsulates the process of handling user input, generating AI responses, and updating memory.
# The pipeline is designed to be modular and reusable across different interfaces (e.g., voice, chat).

from ai import build_system_prompt, run_memory_async
from router import _add_close_hud_command, fast_route

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
        self.ai = ai
        self.memory = memory

    def process(self, req: str, hud=None, speak_fn=None):
        
        #Hud 
        if _add_close_hud_command(req, hud):
            return "__handled__"

        # Fast route
        if fast_route(req):
            return "__handled__"
        
        # Add user message
        if not self.memory.messages or self.memory.messages[-1]["role"] != "user":
            self.memory.add_user(req)

        # Build messages
        messages = _dedup_roles(
            [{"role": "system", "content": build_system_prompt()}]
            + self.memory.get_messages()
        )

        # Call AI
        result = self.ai.respond(
            messages,
            on_sentence=speak_fn,
            hud=hud,
        )

        if not result:
            return None

        full_response = result["text"]
        parsed_json   = result["raw"]

        if not full_response:
            return None

        # Memory update
        run_memory_async(parsed_json)
        self.memory.add_assistant(full_response)

        return full_response