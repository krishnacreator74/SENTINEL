import lmstudio as lms

with lms.Client() as client:
    model = client.llm.model("qwen/qwen3.5-9b")
    result = model.respond("Who are you, and what can you do?")
    print(result)
    while True:
        req = input("Enter ur Prompt:")
        result = model.respond(req)
        print(result)
        if req == "exit":
            break
