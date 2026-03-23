import time
import threading

import voice
from ears import listen
from wake import wait_for_wake
from widget import SentinelWidget
from router import fast_route, needs_search
from memory_chat import ChatMemory
from ai import (
    SentinelAI,
    get_web_context,
    build_system_prompt,
    validate_messages,
    run_memory_async,
)

# ── Main loop ────────────────────────────────────────────────────────────────
def run_sentinel():
    ai          = SentinelAI()
    chat_memory = ChatMemory()
    last_wake   = 0
    saved_gate  = None

    while True:
        time.sleep(0.1)
        if time.time() - last_wake < 3:
            continue

        # Wait for wake word
        saved_gate = wait_for_wake(silence_gate=saved_gate)
        last_wake  = time.time()

        voice.voice_of_ai("yes?")
        req = listen()
        if not req:
            print("No speech detected.")
            continue

        req = req.lower().strip()
        if len(req) < 2:
            print("No speech detected.")
            continue

        print("You:", req)

        # Fast local commands (open apps, etc.)
        if fast_route(req):
            continue

        # Add user turn (guard against duplicate roles)
        if not chat_memory.messages or chat_memory.messages[-1]["role"] != "user":
            chat_memory.add_user(req)

        # Optionally fetch live web context before the LLM speaks
        web_context = ""
        if needs_search(req):
            voice.voice_of_ai("Searching...")
            web_context = get_web_context(req)

        # Build the full message list
        messages = validate_messages(
            [{"role": "system", "content": build_system_prompt(web_context)}]
            + chat_memory.get_messages()
        )

        # Stream response — speak each sentence as it arrives
        full_response = ai.respond_stream(
            messages,
            on_sentence=voice.voice_of_ai,
        )

        if not full_response:
            continue

        # Persist memory and chat history
        run_memory_async(req, full_response)
        chat_memory.add_assistant(full_response)

        if req == "exit":
            break

    ai.close()

# ── Entry point ───────────────────────────────────────────────────────────────
widget       = SentinelWidget()
voice.widget = widget

threading.Thread(target=run_sentinel, daemon=True).start()

print("Starting Sentinel...")
widget.run()
