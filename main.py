"""
main.py — Sentinel entry point
This file initializes the application, sets up the main window,
and starts the voice processing loop in a separate thread. 
It also defines the communication bridge between the voice processing and the UI components.

Key components:
- UIBridge: Facilitates communication between the voice processing thread and the UI thread using Qt signals.
- run_voice_loop: The main loop that listens for wake words, processes voice commands, and interacts with the AI pipeline. It uses the UIBridge to update the UI state and HUD based on voice interactions.
"""

import os
import sys
import time
import threading

from PyQt6.QtWidgets import QApplication
from ui.bridge import UIBridge
from system.emitter import Emitter 
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
import logging

widget_ref   = [None]
chat_win_ref = [None]
stop_event   = threading.Event()

def ensure_log_dir():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

ensure_log_dir()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/sentinel.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ── Voice loop ────────────────────────────────────────────────────────────────


def run_voice_loop(pipeline, bridge, emitter):
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
                logging.error(f"Wake loop error: {e}")
                print("[Voice Loop Error]", e)
                break
            last_wake = time.time()

            # "yes?" — call voice directly, we're already on the voice thread
            emitter.emit("state", "speaking")
            voice.voice_of_ai("yes?", emitter, bridge)
            emitter.emit("state", "listening")

            req = listen()
            if not req:
                emitter.emit("state", "speaking")
                voice.voice_of_ai("I didn't catch that. Please try again.", emitter, bridge)
                emitter.emit("state", "idle")
                print("No speech detected.")
                continue

            req = req.lower().strip()
            if len(req) < 2:
                continue

            print("You:", req)

            if "game mode on" in req:
                emitter.emit("state", "speaking")
                voice.voice_of_ai("Game mode on.", emitter, bridge)
                emitter.emit("game_mode", True)
                emitter.emit("state", "idle")
                continue

            if "game mode off" in req:
                emitter.emit("state", "speaking")
                voice.voice_of_ai("I'm back.", emitter, bridge)
                emitter.emit("game_mode", False)
                emitter.emit("state", "idle")
                continue

            # speak_fn: called from inside ai._speak() on this thread.
            # Calls voice_of_ai directly — NO Qt signal bounce.
            def speak_fn(text):
                emitter.emit("state", "speaking")
                voice.voice_of_ai(text, emitter, bridge)   # blocks until Piper finishes; energy flows

            full_response = pipeline.process(
                req,
                speak_fn=speak_fn,
                bridge=bridge,
                emitter=emitter,
            )
            emitter.emit("state", "idle")

            if full_response == "__handled__":
                emitter.emit("chat_update", req, "Done.")
                continue

            if not full_response:
                continue

            emitter.emit("chat_update", req, full_response)

            if req == "exit":
                emitter.emit("exit_app")
                stop_event.set()
                break

    except Exception as e:
        logging.error(f"Voice loop error: {e}")
        print("[Voice Loop Error]", e)


if __name__ == "__main__":
    app           = QApplication(sys.argv)
    shared_memory = ChatMemory()
    bridge        = UIBridge()
    emitter = Emitter()

    # ── Emitter signals → Bridge → UI ─────────────────────────────────────────
    emitter.on("state", lambda s: bridge.state_signal.emit(s))
    emitter.on("energy", lambda e: bridge.energy_signal.emit(e))
    emitter.on("game_mode", lambda val: bridge.game_mode_signal.emit(val))
    emitter.on("hud_close", lambda: bridge.hud_close_signal.emit())
    emitter.on("chat_update", lambda req, res: bridge.chat_signal.emit(req, res))
    emitter.on("exit_app", lambda:  bridge.close_app_signal.emit())

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
    bridge.chat_signal.connect(chat_win.push_exchange)
    bridge.close_app_signal.connect(app.quit)

    threading.Thread(
        target=run_voice_loop,
        args=(pipeline, bridge, emitter),
        daemon=True,
    ).start()

    print("Sentinel started.")
    logging.info("Sentinel started.")
    exit_code = app.exec()
    stop_event.set()
    sys.exit(exit_code)