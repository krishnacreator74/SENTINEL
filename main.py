"""
main.py — Sentinel entry point
This file initializes the Sentinel application, setting up the AI pipeline, voice interface, chat interface, and HUD. It starts the main event loop and the voice processing thread.
"""

import sys
import time
import threading
from core.pipeline import SentinelPipeline
from PyQt6.QtWidgets import QApplication

from voice import voice
from voice.ears import listen
from voice.wake import wait_for_wake
from memory.memory_chat import ChatMemory
from ai import SentinelAI
from widget import SentinelWidget
from menu import SentinelMenu
from hud import HUD
from chat.window import ChatWindow

widget_ref   = [None]
chat_win_ref = [None]
stop_event = threading.Event()

def run_voice_loop(pipeline, hud):
    last_wake  = 0
    saved_gate = None

    try:

        while not stop_event.is_set():
            time.sleep(0.1)
            if time.time() - last_wake < 3:
                continue

            try:
                saved_gate = wait_for_wake(silence_gate=saved_gate)
            except Exception as e:
                print("[Voice Loop Error]", e)
                break
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

            widget_ref[0].set_listening()

            widget_ref[0].set_speaking()
                        
            full_response = pipeline.process(
                req,
                hud=hud,
                speak_fn=voice.voice_of_ai
            )

            widget_ref[0].set_idle()

            # If handled by router, skip AI/chat
            if full_response == "__handled__":
                if chat_win_ref[0]:
                    chat_win_ref[0].push_exchange(req, "Done.")
                continue

            if not full_response:
                continue

            # Mirror voice exchange into chat window
            if chat_win_ref[0]:
                chat_win_ref[0].push_exchange(req, full_response)

            if req == "exit":
                stop_event.set()
                break
    except Exception as e:
        print("[Wake Error]", e)


if __name__ == "__main__":
    app           = QApplication(sys.argv)
    shared_memory = ChatMemory()

    voice_ai = SentinelAI()
    chat_ai  = SentinelAI()
    pipeline = SentinelPipeline(voice_ai, shared_memory)

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
        args=(pipeline, hud),
        daemon=True,
    ).start()

    print("Sentinel started.")
    exit_code = app.exec()
    stop_event.set()
    sys.exit(exit_code)