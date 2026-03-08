import lmstudio as lms
from ears import listen
from commands import launch_app_from_command
from voice import voice_of_ai
import time
from wake import wait_for_wake

buffer = ""

with lms.Client() as client:
    model = client.llm.model("qwen/qwen3.5-9b")
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
        voice_of_ai("yes?")

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
            if buffer.startswith("COMMAND:") and len(buffer.split()) >= 3:
                launch_app_from_command(buffer.strip())
                buffer = ""
                break

            # sentence boundary for speech
            if any(p in buffer for p in [".", "?", "!"]):
                voice_of_ai(buffer.strip())
                buffer = ""


        print()
        if req == "exit":
            break
