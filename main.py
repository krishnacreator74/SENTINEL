import lmstudio as lms

with lms.Client() as client:
    model = client.llm.model("qwen/qwen3.5-9b")
    for fragment in model.respond_stream("Who are you, and what can you do?"):
        print(fragment.content, end= "", flush=True)
    print()
    while True:
        req = input("Enter ur Prompt:")
        result = model.respond(req)
        print(result)
        print()
        if req == "exit":
            break
