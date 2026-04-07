import sys
import time
import threading

import voice
from ears import listen
from wake import wait_for_wake
from widget import SentinelWidget
from router import fast_route, _add_close_hud_command
from memory_chat import ChatMemory
from ai import (
    SentinelAI,
    build_system_prompt,
    run_memory_async,
)

def _dedup_roles(messages: list) -> list:
    """Drop consecutive messages with the same role."""
    fixed, last_role = [], None
    for msg in messages:
        if msg["role"] == last_role:
            continue
        fixed.append(msg)
        last_role = msg["role"]
    return fixed

# ── Sentinel main loop ────────────────────────────────────────────────────────
def run_sentinel(hud=None):
    ai          = SentinelAI()
    chat_memory = ChatMemory()
    last_wake   = 0
    saved_gate  = None

    while True:
        time.sleep(0.1)
        if time.time() - last_wake < 3:
            continue

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

        # Voice close command — handled before anything else
        if _add_close_hud_command(req, hud):
            continue

        # Fast local commands (open apps, etc.)
        if fast_route(req):
            continue

        if not chat_memory.messages or chat_memory.messages[-1]["role"] != "user":
            chat_memory.add_user(req + " /no_think")

        messages = _dedup_roles(
            [{"role": "system", "content": build_system_prompt()}]
            + chat_memory.get_messages()
        )

        full_response = ai.respond_stream(
            messages,
            on_sentence=voice.voice_of_ai,
            hud=hud,
        )

        if not full_response:
            continue

        run_memory_async(req, full_response)
        chat_memory.add_assistant(full_response)

        if req == "exit":
            break

    ai.close()

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Qt must have its own thread — tkinter owns the main thread
    qt_ready = threading.Event()
    hud_ref  = [None]

    def _qt_thread():
        from PyQt6.QtWidgets import QApplication
        from hud import HUD
        qt_app     = QApplication(sys.argv)
        hud_ref[0] = HUD(qt_app)
        qt_ready.set()          # unblock main thread
        qt_app.exec()           # Qt event loop — runs until HUD is closed

    qt_t = threading.Thread(target=_qt_thread, daemon=True)
    qt_t.start()
    qt_ready.wait()             # wait until HUD is actually ready

    hud          = hud_ref[0]
    widget       = SentinelWidget()
    voice.widget = widget
    voice.hud    = hud

    threading.Thread(target=run_sentinel, args=(hud,), daemon=True).start()

    print("Starting Sentinel...")
    widget.run()                # tkinter mainloop — blocks main thread (correct)