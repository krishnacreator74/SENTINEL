"""
llm.py — LLM interaction for Note Taker.

Responsibilities:
  - lm_call()     raw HTTP call to LM Studio, returns plain text
  - write_note()  builds the prompt, calls lm_call, returns raw model output
  - parse_boxes() parses model output into (heading, lines) pairs
                  handles BOTH box-border format AND plain heading format

NOTE: response_format: text is passed on every call to bypass whatever
structured output schema LM Studio has loaded globally.
"""

import re
import datetime
import httpx
from PIL import Image

from . import config
from .capture import to_b64


# ── Raw LLM call ───────────────────────────────────────────────────────────────
def lm_call(messages: list[dict], max_tokens: int = 600) -> str:
    try:
        timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)
        payload = {
            "model":           config.MODEL_NAME,
            "messages":        messages,
            "max_tokens":      max_tokens,
            "temperature":     0.25,
            "response_format": {"type": "text"},
        }
        resp = httpx.post(config.LM_STUDIO_URL, json=payload, timeout=timeout)
        resp.raise_for_status()

        raw = resp.json()["choices"][0]["message"]["content"]
        if not raw or not raw.strip():
            print("[LM] Empty response")
            return ""

        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return raw.strip()

    except httpx.ReadTimeout:
        print("[LM] Read timeout")
        return ""
    except Exception as e:
        print(f"[LM error] {e}")
        return ""


# ── Prompt builder ─────────────────────────────────────────────────────────────
def write_note(
    speech:  str,
    img:     Image.Image,
    known:   str,
    diagram: str | None,
) -> str:
    ts   = datetime.datetime.now().strftime("%H:%M")
    b64  = to_b64(img)
    diag = f"Diagram saved as: {diagram}." if diagram else ""

    example = (
        "┌─ EXAMPLE TOPIC ───────────────────────────┐\n"
        "First concrete fact about this topic.\n"
        "Second concrete fact.\n"
        ">> Key insight or direct quote from speaker.\n"
        "└───────────────────────────────────────────┘"
    )

    instruction = (
        f"You are in NOTE MODE. Extract NEW lecture content from the screen and speech.\n\n"
        f"Time: [{ts}]. {diag}\n\n"
        f"SPEECH FROM LECTURER:\n{speech if speech else '(silence)'}\n\n"
        f"ALREADY KNOWN — do NOT include anything from this list:\n{known}\n\n"
        f"OUTPUT FORMAT — copy this structure exactly, every single time:\n\n"
        f"{example}\n\n"
        f"STRICT RULES:\n"
        f"1. Every topic MUST use the box borders shown above. No plain headings ever.\n"
        f"2. One box per concept. Never merge two topics.\n"
        f"3. Max 5 lines inside each box.\n"
        f"4. Plain text only inside boxes. No markdown. No asterisks. No bullets.\n"
        f"5. [DIAGRAM: filename] goes OUTSIDE and AFTER the relevant box.\n"
        f"6. If nothing genuinely new to note, reply with exactly one word: SKIP\n"
        f"7. Do NOT output JSON. Do NOT copy the ALREADY KNOWN section back out."
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are SENTINEL in NOTE MODE. "
                "You MUST use box borders for every topic. "
                "No JSON. No plain headings. No markdown. "
                "If nothing new, output exactly: SKIP"
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": instruction},
            ],
        },
    ]

    return lm_call(messages, max_tokens=700).strip()


# ── Box parser — handles both formats ─────────────────────────────────────────
def parse_boxes(raw: str) -> list[tuple[str, list[str]]]:
    """
    Parse model output into (heading, lines) tuples.

    Tries Format A (box borders) first.
    Falls back to Format B (plain CAPS headings) if no borders found.
    Both formats go through dedup. Neither bypasses it.

    [DIAGRAM: ...] lines come back as ("__meta__", [line]) — written through
    without dedup since they are file references, not facts.
    """
    box_results = _parse_box_format(raw)
    if box_results:
        # Filter out lone __meta__ results so we know real boxes were found
        real_boxes = [r for r in box_results if r[0] != "__meta__"]
        if real_boxes:
            return box_results

    print("[Parser] No box borders found — falling back to plain heading parser.")
    return _parse_plain_format(raw)


def _parse_box_format(raw: str) -> list[tuple[str, list[str]]]:
    results  = []
    heading  = None
    buf      = []
    in_box   = False
    meta_buf = []

    for line in raw.splitlines():
        stripped = line.strip()

        if stripped.startswith("┌") and stripped.endswith("┐"):
            inner   = re.sub(r"^┌─?\s*", "", stripped)
            inner   = re.sub(r"\s*─+┐$", "", inner)
            heading = inner.strip().upper()
            buf     = []
            in_box  = True
            continue

        if stripped.startswith("└") and in_box:
            if heading and buf:
                results.append((heading, buf))
            heading = None
            buf     = []
            in_box  = False
            continue

        if in_box:
            if stripped:
                buf.append(stripped)
        else:
            if stripped:
                meta_buf.append(stripped)

    if meta_buf:
        results.append(("__meta__", meta_buf))

    return results


def _parse_plain_format(raw: str) -> list[tuple[str, list[str]]]:
    """
    Parse plain HEADING IN CAPS / fact lines format.
    Heading detected by: mostly uppercase, 2+ words, not a >> insight line.
    """
    results  = []
    heading  = None
    buf      = []
    meta_buf = []

    def _is_heading(line: str) -> bool:
        if line.startswith(">>"):
            return False
        if line.startswith("[DIAGRAM"):
            return False
        clean = re.sub(r"[^a-zA-Z\s]", "", line).strip()
        if not clean or len(clean.split()) < 2:
            return False
        upper_ratio = sum(1 for c in clean if c.isupper()) / max(len(clean.replace(" ", "")), 1)
        return upper_ratio > 0.75

    def _flush():
        if heading and buf:
            results.append((heading, list(buf)))

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("[DIAGRAM"):
            _flush()
            heading = None
            buf     = []
            meta_buf.append(stripped)
            continue

        if _is_heading(stripped):
            _flush()
            heading = stripped.upper()
            buf     = []
        else:
            if heading:
                buf.append(stripped)
            else:
                meta_buf.append(stripped)

    _flush()

    if meta_buf:
        results.append(("__meta__", meta_buf))

    return results


def is_skip(text: str) -> bool:
    return not text or text.strip().upper() == "SKIP" or len(text.strip()) < 3