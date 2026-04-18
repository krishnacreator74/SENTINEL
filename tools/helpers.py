import re
import httpx
from config import MODEL_NAME

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"


def llm(messages: list, temperature: float = 0.3) -> str:
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    r = httpx.post(LM_STUDIO_URL, json=payload, timeout=60)
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def extract_images(text: str) -> list[str]:
    pattern = re.compile(
        r'https?://[^\s\'"<>]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s\'"<>]*)?',
        re.IGNORECASE,
    )
    skip = re.compile(
        r'(icon|logo|favicon|pixel|tracker|1x1|badge|avatar|thumb/\d{1,2}x)',
        re.IGNORECASE,
    )

    seen, out = set(), []
    for url in pattern.findall(text):
        if skip.search(url) or url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= 3:
            break
    return out