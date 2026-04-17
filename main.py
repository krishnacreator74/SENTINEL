"""
main.py — Sentinel entry point

Everything Qt (widget, menu, HUD, chat) runs on the main thread.
Voice loop runs on a daemon thread.
Voice exchanges are mirrored into the chat window via push_exchange().
"""

import sys
import time
import threading

from PyQt6.QtWidgets import QApplication

import voice
from ears import listen
from wake import wait_for_wake
from router import fast_route, _add_close_hud_command
from memory_chat import ChatMemory
from ai import SentinelAI, build_system_prompt, run_memory_async
from widget import SentinelWidget
from menu import SentinelMenu
from hud import HUD
from chat.window import ChatWindow


def _dedup_roles(messages: list) -> list:
    fixed, last_role = [], None
    for msg in messages:
        if msg["role"] == last_role:
            continue
        fixed.append(msg)
        last_role = msg["role"]
    return fixed


widget_ref   = [None]
chat_win_ref = [None]


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

        # Game mode voice commands
        if "game mode on" in req:
            widget_ref[0].set_game_mode(True)
            voice.voice_of_ai("Game mode on.")
            continue
        if "game mode off" in req:
            widget_ref[0].set_game_mode(False)
            voice.voice_of_ai("I'm back.")
            continue

        if _add_close_hud_command(req, hud):
            continue

        if fast_route(req):
            # Mirror fast-route actions into chat too
            if chat_win_ref[0]:
                chat_win_ref[0].push_exchange(req, "Done.")
            continue

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

        # Mirror voice exchange into chat window
        if chat_win_ref[0]:
            chat_win_ref[0].push_exchange(req, full_response)

        if req == "exit":
            break


if __name__ == "__main__":
    app           = QApplication(sys.argv)
    shared_memory = ChatMemory()

    voice_ai = SentinelAI()
    chat_ai  = SentinelAI()

    hud = HUD(app)

    widget        = SentinelWidget()
    widget_ref[0] = widget

    def _on_chat_closed():
        widget.on_chat_closed_externally()

    chat_win          = ChatWindow(
        ai=chat_ai,
        chat_memory=shared_memory,
        on_close=_on_chat_closed,
    )
    chat_win_ref[0]   = chat_win

    menu = SentinelMenu(widget_ref=widget, chat_win_ref=chat_win)
    widget.set_menu(menu)

    voice.widget = widget
    voice.hud    = hud

    threading.Thread(
        target=run_voice_loop,
        args=(voice_ai, hud, shared_memory),
        daemon=True,
    ).start()

    print("Sentinel started.")
    sys.exit(app.exec())