"""
main.py — Sentinel entry point

Key fixes:
1. voice.bridge = bridge  (was missing — energy never reached widget)
2. speak_signal NOT connected to voice_of_ai.
   on_sentence calls voice.voice_of_ai() directly from the voice thread.
   Routing it through a Qt signal caused voice_of_ai to run on the main
   thread, which blocked processing of energy signals it was emitting,
   so widget got no energy updates until speech finished.
3. bridge passed to pipeline.process() → ai.respond() → _speak()
   so all HUD calls are Qt-signal-safe.
"""

import sys
import time
import threading

from PyQt6.QtWidgets import QApplication
from ui.bridge import UIBridge

from voice import voice
from voice.ears import listen
from voice.wake import wait_for_wake
from memory.memory_chat import ChatMemory
from core.ai import SentinelAI
from core.pipeline import SentinelPipeline
from ui.widget import SentinelWidget
from ui.menu import SentinelMenu
from ui.hud import HUD
from chat.window import ChatWindow

widget_ref   = [None]
chat_win_ref = [None]
stop_event   = threading.Event()


def run_voice_loop(pipeline, hud, bridge):
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
            last_wake = time.time()

            # "yes?" — call voice directly, we're already on the voice thread
            bridge.state_signal.emit("speaking")
            voice.voice_of_ai("yes?")
            bridge.state_signal.emit("listening")

            req = listen()
            if not req:
                bridge.state_signal.emit("speaking")
                voice.voice_of_ai("I didn't catch that. Please try again.")
                bridge.state_signal.emit("idle")
                print("No speech detected.")
                continue

            req = req.lower().strip()
            if len(req) < 2:
                continue

            print("You:", req)

            if "game mode on" in req:
                bridge.state_signal.emit("speaking")
                voice.voice_of_ai("Game mode on.")
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: widget_ref[0].set_game_mode(True))
                bridge.state_signal.emit("idle")
                continue

            if "game mode off" in req:
                bridge.state_signal.emit("speaking")
                voice.voice_of_ai("I'm back.")
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: widget_ref[0].set_game_mode(False))
                bridge.state_signal.emit("idle")
                continue

            # speak_fn: called from inside ai._speak() on this thread.
            # Calls voice_of_ai directly — NO Qt signal bounce.
            def speak_fn(text):
                bridge.state_signal.emit("speaking")
                voice.voice_of_ai(text)   # blocks until Piper finishes; energy flows

            full_response = pipeline.process(
                req,
                hud=hud,
                speak_fn=speak_fn,
                bridge=bridge,
            )
            bridge.state_signal.emit("idle")

            if full_response == "__handled__":
                if chat_win_ref[0]:
                    chat_win_ref[0].push_exchange(req, "Done.")
                continue

            if not full_response:
                continue

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
    bridge        = UIBridge()

    voice_ai = SentinelAI()
    chat_ai  = SentinelAI()
    pipeline = SentinelPipeline(voice_ai, shared_memory)

    hud = HUD(app)

    widget        = SentinelWidget()
    widget_ref[0] = widget

    def _on_chat_closed():
        widget.on_chat_closed_externally()

    chat_win        = ChatWindow(
        ai=chat_ai,
        chat_memory=shared_memory,
        on_close=_on_chat_closed,
    )
    chat_win_ref[0] = chat_win

    menu = SentinelMenu(widget_ref=widget, chat_win_ref=chat_win)
    widget.set_menu(menu)

    # ── CRITICAL: wire bridge into voice module ───────────────────────────────
    voice.bridge = bridge

    # ── Widget signals ────────────────────────────────────────────────────────
    bridge.state_signal.connect(widget.set_state)
    bridge.energy_signal.connect(widget.set_energy)
    # NOTE: speak_signal intentionally NOT connected to voice.voice_of_ai.
    #       Voice is called directly from the voice thread via speak_fn.
    #       Connecting it caused voice_of_ai to run on Qt's main thread,
    #       deadlocking energy signal delivery mid-speech.

    # ── HUD signals — all routed through bridge ───────────────────────────────
    bridge.hud_load_signal.connect(
        lambda sentences, title: hud.load_sentences(sentences, title)
    )
    bridge.hud_begin_signal.connect(hud.begin_sentence)
    bridge.hud_end_signal.connect(hud.end_sentence)
    bridge.hud_finish_signal.connect(hud.finish_all)
    bridge.hud_clear_signal.connect(hud.clear)
    bridge.hud_close_signal.connect(hud.close)
    bridge.hud_title_signal.connect(hud.set_title)
    bridge.hud_image_signal.connect(hud.append_image)

    threading.Thread(
        target=run_voice_loop,
        args=(pipeline, hud, bridge),
        daemon=True,
    ).start()

    print("Sentinel started.")
    exit_code = app.exec()
    stop_event.set()
    sys.exit(exit_code)