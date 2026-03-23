# main.py
import lmstudio as lms
from ears import listen
from commands import launch_app_from_command
from memory_persistent import load_memory
import voice
import time
from wake import wait_for_wake
from widget import SentinelWidget
import threading
import numpy as np
from memory_chat import ChatMemory
from memory_analyzer import analyze_and_store_memory
from config import SYSTEM_PROMPT, MODEL_NAME, TEMPERATURE, TOP_P, TOP_K
import json
import re
from router import fast_route
from web_search import search_and_extract

# ── Constants ────────────────────────────────────────────────────────────────
MEMORY_INTERVAL = 5

SEARCH_KEYWORDS = [
    "news", "latest", "today", "current", "recent", "now",
    "who is", "what happened", "price of", "weather", "score",
    "released", "announced", "update", "2025", "2026",
    "gaming", "sports", "stock", "election", "war", "launch"
]

# ── Globals ──────────────────────────────────────────────────────────────────
chat_memory = ChatMemory()

# ── Helpers ──────────────────────────────────────────────────────────────────
def clean_for_voice(text):
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*",   "", text)
    text = text.replace("e.g.", "for example")
    text = text.replace("i.e.", "that is")
    return text

def validate_messages(messages):
    fixed, last_role = [], None
    for msg in messages:
        if msg["role"] == last_role:
            continue
        fixed.append(msg)
        last_role = msg["role"]
    return fixed

def needs_search(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in SEARCH_KEYWORDS)

def run_memory_async(combined):
    def task():
        with lms.Client() as client:
            model = client.llm.model(MODEL_NAME)
            analyze_and_store_memory(model, combined)
    threading.Thread(target=task, daemon=True).start()

# ── Main loop ────────────────────────────────────────────────────────────────
def run_sentinel():
    with lms.Client() as client:
        model = client.llm.model(MODEL_NAME)
        last_wake  = 0
        saved_gate = None
        memory_counter = 0

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

            # Fast local commands (open apps, etc.)
            if fast_route(req):
                continue

            # Deduplicate chat history
            if not chat_memory.messages or chat_memory.messages[-1]["role"] != "user":
                chat_memory.add_user(req)

            # ── Pre-search (BEFORE the LLM speaks) ───────────────────────────
            web_context = ""
            if needs_search(req):
                voice.voice_of_ai("Searching...")
                web_context = search_and_extract(req)
                print(f"[Search] Got {len(web_context)} chars")

            # ── Build system prompt ───────────────────────────────────────────
            memory = load_memory()
            sys_content = (
                SYSTEM_PROMPT
                + "\n\nKnown user information:\n"
                + json.dumps(memory, indent=2)
            )
            if web_context:
                sys_content += (
                    "\n\nReal-time web data — use this to answer accurately. "
                    "Do NOT emit 'SEARCH:' in your reply:\n"
                    + web_context
                )

            messages = validate_messages(
                [{"role": "system", "content": sys_content}]
                + chat_memory.get_messages()
            )

            # ── Stream LLM response ───────────────────────────────────────────
            buffer        = ""
            full_response = ""

            try:
                for fragment in model.respond_stream({
                    "messages":    messages,
                    "temperature": TEMPERATURE,
                    "top_p":       TOP_P,
                    "top_k":       TOP_K
                }):
                    text = fragment.content

                    # Hard-stop if the model still tries to search
                    if "SEARCH:" in full_response + text:
                        print("[main] Model tried to emit SEARCH: — suppressed.")
                        break

                    full_response += text
                    buffer        += text
                    print(text, end="", flush=True)

                    if re.search(r"[.!?]", buffer):
                        voice.voice_of_ai(clean_for_voice(buffer.strip()))
                        buffer = ""

            except Exception as e:
                print(f"[main] Model error: {e}")
                continue

            # Flush any remaining buffer
            if buffer.strip():
                voice.voice_of_ai(clean_for_voice(buffer.strip()))
            print()

            # ── Memory & history ──────────────────────────────────────────────
            memory_counter += 1
            run_memory_async(f"User: {req}\nAssistant: {full_response}")
            chat_memory.add_assistant(full_response.strip())

            if req == "exit":
                break

# ── Entry point ───────────────────────────────────────────────────────────────
widget       = SentinelWidget()
voice.widget = widget

threading.Thread(target=run_sentinel, daemon=True).start()

print("Starting Sentinel...")
widget.run()