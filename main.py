import lmstudio as lms
from ears import listen
from commands import launch_app_from_command
import voice
import time
from wake import wait_for_wake
from widget import SentinelWidget
import threading
import numpy as np
from memory_chat import ChatMemory

chat_memory = ChatMemory()

buffer = ""

def run_sentinel():
    with lms.Client() as client:
        model = client.llm.model("google/gemma-3-1b")
        last_wake = 0
        saved_gate = None  # calibrate once, reuse forever

        while True:
            time.sleep(0.1)
            if time.time() - last_wake < 3:
                continue

            saved_gate = wait_for_wake(silence_gate=saved_gate)  # returns the gate it used

            last_wake = time.time()
            voice.voice_of_ai("yes?")
            req = listen()
            chat_memory.add_user(req)
            print("You:", req)

            if not req or req.strip() == "":
                print("No speech detected.")
                continue

            buffer = ""
            full_response = ""
            messages = chat_memory.get_messages()
            for fragment in model.respond_stream({"messages": messages}):
                text = fragment.content
                full_response += text
                print(text, end="", flush=True)
                buffer += text

                if "COMMAND:" in buffer and "\n" in buffer:
                    command = buffer.split("COMMAND:", 1)[1].strip()
                    full_command = "COMMAND: " + command
                    print(full_command)
                    launch_app_from_command(full_command)
                    buffer = ""
                    break

                if any(p in buffer for p in [".", "?", "!"]):
                    voice.voice_of_ai(buffer.strip())
                    buffer = ""

            print()

            chat_memory.add_assistant(full_response.strip())

            if req == "exit":
                break

widget = SentinelWidget()
voice.widget = widget

threading.Thread(target=run_sentinel, daemon=True).start()

print("Starting Sentinel...")
widget.run()
