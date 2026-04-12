"""
main.py — Sentinel entry point

Everything Qt (widget, HUD, chat) runs on the main thread via QApplication.
The voice loop runs on a daemon thread.
Both voice and chat share one ChatMemory instance.
"""

import sys
import time
import threading

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

import voice
from ears import listen
from wake import wait_for_wake
from router import fast_route, _add_close_hud_command
from memory_chat import ChatMemory
from ai import SentinelAI, build_system_prompt, run_memory_async
from widget import SentinelWidget
from hud import HUD
from chat import ChatWindow


def _dedup_roles(messages: list) -> list:
    fixed, last_role = [], None
    for msg in messages:
        if msg["role"] == last_role:
            continue
        fixed.append(msg)
        last_role = msg["role"]
    return fixed


def run_voice_loop(ai, hud, shared_memory: ChatMemory):
    last_wake  = 0
    saved_gate = None

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
            continue

        print("You:", req)

        # Game mode toggle
        if "game mode on" in req:
            widget_ref[0].set_game_mode(True)
            voice.voice_of_ai("Game mode on. I'll stay quiet.")
            continue
        if "game mode off" in req:
            widget_ref[0].set_game_mode(False)
            voice.voice_of_ai("I'm back.")
            continue

        if _add_close_hud_command(req, hud):
            continue

        if fast_route(req):
            continue

        # Update widget state
        widget_ref[0].set_listening()

        if not shared_memory.messages or shared_memory.messages[-1]["role"] != "user":
            shared_memory.add_user(req)

        messages = _dedup_roles(
            [{"role": "system", "content": build_system_prompt()}]
            + shared_memory.get_messages()
        )

        widget_ref[0].set_speaking()

        full_response = ai.respond(
            messages,
            on_sentence=voice.voice_of_ai,
            hud=hud,
        )

        widget_ref[0].set_idle()

        if not full_response:
            continue

        run_memory_async(req, full_response)
        shared_memory.add_assistant(full_response)

        if req == "exit":
            break


# Module-level ref so voice loop can reach widget
widget_ref = [None]


if __name__ == "__main__":
    app           = QApplication(sys.argv)
    shared_memory = ChatMemory()

    # ── AI instances ──────────────────────────────────────────────────────────
    voice_ai = SentinelAI()
    chat_ai  = SentinelAI()

    # ── HUD ───────────────────────────────────────────────────────────────────
    hud = HUD(app)

    # ── Widget ────────────────────────────────────────────────────────────────
    widget       = SentinelWidget()
    widget_ref[0] = widget

    # ── Chat window ───────────────────────────────────────────────────────────
    def _on_chat_closed():
        widget.on_chat_closed_externally()

    chat_win = ChatWindow(
        ai=chat_ai,
        chat_memory=shared_memory,
        on_close=_on_chat_closed,
    )
    widget.set_chat_window(chat_win)

    # ── Voice wiring ──────────────────────────────────────────────────────────
    voice.widget = widget
    voice.hud    = hud

    # ── Voice loop on daemon thread ───────────────────────────────────────────
    threading.Thread(
        target=run_voice_loop,
        args=(voice_ai, hud, shared_memory),
        daemon=True,
    ).start()

    print("Sentinel started.")
    sys.exit(app.exec())