import lmstudio as lms
from ears import listen
from commands import launch_app_from_command
import voice
import time
from wake import wait_for_wake
from widget import SentinelWidget
import threading
import numpy as np

buffer = ""

def run_sentinel():

    with lms.Client() as client:
        # model = client.llm.model("qwen/qwen3.5-9b")
        model = client.llm.model("google/gemma-3-1b")


        # for fragment in model.respond_stream("Who are you, and what can you do?"):
        #     print(fragment.content, end= "", flush=True)

        #     buffer += fragment.content


        #     if "." in buffer or "?" in buffer or "!" in buffer:
        #         voice_of_ai(buffer.strip())
        #         buffer = ""
        last_wake = 0
        
        while True:
            time.sleep(1)

            if time.time() - last_wake < 3:
                continue
            
            wait_for_wake()
            last_wake = time.time()
            voice.voice_of_ai("yes?")
            # continue
            req = listen()
            print("You:", req)
                
            if not req or req.strip() == "":
                print("No speech detected.")
                continue

            buffer = ""

            for fragment in model.respond_stream(req):

                text = fragment.content

                print(text, end="", flush=True)

                buffer += text

                # detect commands
                if "COMMAND:" in buffer and "\n" in buffer:
                    command = buffer.split("COMMAND:", 1)[1].strip()
                    full_command = "COMMAND: " + command

                    print(full_command)
                    launch_app_from_command(full_command)

                    buffer = ""
                    break

                # sentence boundary for speech
                if any(p in buffer for p in [".", "?", "!"]):
                    voice.voice_of_ai(buffer.strip())
                    buffer = ""


            print()
            if req == "exit":
                break

widget = SentinelWidget()
voice.widget = widget

threading.Thread(target=run_sentinel, daemon=True).start()

print("Starting Sentinel...")
widget.run()
