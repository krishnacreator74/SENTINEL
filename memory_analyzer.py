import json
import re
from memory_persistent import update_memory

def clean_json(text):

    # remove markdown code blocks
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)

    # trim spaces
    text = text.strip()

    return text


def analyze_and_store_memory(model, user_text):

    prompt = {
        "messages": [
            {
                "role": "system",
                "content": """
Extract long term user information.

Return ONLY JSON.

Example

User: I like games
Output:
{"interests":["games"]}

If nothing important exists return {}

Do not use markdown.
"""
            },
            {
                "role": "user",
                "content": user_text
            }
        ]
    }

    response = model.respond(prompt)

    raw = response.content
    print("Memory raw response:", raw)

    cleaned = clean_json(raw)

    try:
        data = json.loads(cleaned)

        if data:
            update_memory(data)
            print("Stored memory:", data)

    except Exception as e:
        print("Memory parse failed:", e)