import lmstudio as lms

from commands import launch_app_from_command


with lms.Client() as client:
    model = client.llm.model("qwen/qwen3.5-9b")
    for fragment in model.respond_stream("Who are you, and what can you do?"):
        print(fragment.content, end= "", flush=True)
    print()
    while True:
        req = input("Enter ur Prompt:")
        result = model.respond(req)
        if(result.content.startswith("COMMAND: ")):
            launch_app_from_command(result.content)
            
        else:
            print(result)
        print()
        if req == "exit":
            break
