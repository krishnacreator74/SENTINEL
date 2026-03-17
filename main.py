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
from router import fast_route

memory_counter = 0
MEMORY_INTERVAL = 5

chat_memory = ChatMemory()

buffer = ""

import re

def clean_for_voice(text):
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*", "", text)
    text = text.replace("e.g.", "for example")
    text = text.replace("i.e.", "that is")
    return text

def run_sentinel():
    
    with lms.Client() as client:
        model = client.llm.model(MODEL_NAME)
        last_wake = 0
        saved_gate = None  # calibrate once, reuse forever
        memory = load_memory()
        memory_counter = 0
        MEMORY_INTERVAL = 5
        while True:
            time.sleep(0.1)
            if time.time() - last_wake < 3:
                continue

            saved_gate = wait_for_wake(silence_gate=saved_gate)  # returns the gate it used

            last_wake = time.time()
            voice.voice_of_ai("yes?")
            req = listen()
            if req:
                req = req.lower().strip()
            
            print("You:", req)
            
            if fast_route(req):
                continue

            chat_memory.add_user(req)

            if not req or len(req.strip()) < 2:
                print("No speech detected.")
                continue

            buffer = ""
            full_response = ""

            messages = [
                {
                "role": "system",
                "content": SYSTEM_PROMPT + "\n\nKnown user information:\n" + json.dumps(memory, indent=2)
                }
            ] + chat_memory.get_messages()

            for fragment in model.respond_stream({
                "messages": messages,
                "temperature": TEMPERATURE,
                "top_p": TOP_P,
                "top_k": TOP_K
                }):

                text = fragment.content
                full_response += text
                print(text, end="", flush=True)
                buffer += text

                # if "COMMAND:" in buffer and "\n" in buffer:

                #     command = buffer.split("COMMAND:",1)[1].split("\n")[0].strip()

                #     user_text = req.lower()

                #     allowed_triggers = [
                #                 "open",
                #                 "launch",
                #                 "start",
                #                 "run",
                #                 "sleep",
                #                 "shutdown",
                #                 "restart",
                #                 "lock"
                #             ]

                #     if any(t in user_text for t in allowed_triggers):

                #         print("Executing command:", command)
                #         launch_app_from_command("COMMAND: " + command)

                #     else:
                #         print("Ignoring hallucinated command:", command)

                #     buffer = ""
                #     break

                if any(p in buffer for p in [".", "?", "!"]):
                    voice.voice_of_ai(clean_for_voice(buffer.strip()))
                    buffer = ""

            print()

            if buffer.strip():
                voice.voice_of_ai(clean_for_voice(buffer.strip()))
            
            if "COMMAND:" in full_response:
                continue

            memory_counter += 1

            if memory_counter >= MEMORY_INTERVAL:

                analyze_and_store_memory(model, req)
                memory = load_memory()

                memory_counter = 0

            chat_memory.add_assistant(full_response.strip())

            if req == "exit":
                break

widget = SentinelWidget()
voice.widget = widget

threading.Thread(target=run_sentinel, daemon=True).start()

print("Starting Sentinel...")
widget.run()
