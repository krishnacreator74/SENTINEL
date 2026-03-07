import lmstudio as lms
from ears import listen
from commands import launch_app_from_command
from voice import voice_of_ai
import time

buffer = ""

with lms.Client() as client:
    model = client.llm.model("qwen/qwen3.5-9b")
    # for fragment in model.respond_stream("Who are you, and what can you do?"):
    #     print(fragment.content, end= "", flush=True)

    #     buffer += fragment.content


    #     if "." in buffer or "?" in buffer or "!" in buffer:
    #         voice_of_ai(buffer.strip())
    #         buffer = ""

    
    while True:
        time.sleep(0.5)

        req = listen()
        print("You:", req)

        WAKE_WORDS = ["sentinel", "central", "you sent", "your center"]

        if not any(w in req for w in WAKE_WORDS):
            continue

        # remove wake word
        req = req.replace("sentinel", "").strip()

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
