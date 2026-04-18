# web_search.py
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36"
}

# Words to strip from the front/anywhere before the real topic
STRIP_PHRASES = [
    "tell me", "search for me", "search for", "search", "can you", "would you",
    "find me", "look up", "give me", "show me", "i want to know",
    "please", "hey", "sentinel",
]

STRIP_WORDS = [
    "what's", "what is", "what are", "whats",
    "the", "a", "an", "me", "some",
    "latest", "newest", "current", "recent", "new",   # kept as search terms — added back below
    "right now", "right", "now", "currently",
    "only", "just", "like", "uh", "um", "er",
    "with date", "below 50 words", "in 50 words",
    "make sure", "make it", "also", "please",
    "on the market", "on market",
]

# Keywords we WANT to keep even if they appear in STRIP_WORDS above
KEEP_TERMS = {"latest", "newest", "current", "recent", "new", "now"}

def clean_query(raw: str) -> str:
    q = raw.strip().split("\n")[0][:200].lower()
    q = re.sub(r"[?!,\.;:]", "", q)

    for phrase in STRIP_PHRASES:
        q = q.replace(phrase, " ")

    tokens = q.split()
    tokens = [t for t in tokens if t in KEEP_TERMS or t not in STRIP_WORDS]
    q = " ".join(tokens).strip()

    # ── Append current date to bias DDG toward recent results ────────────────
    from datetime import datetime
    month_year = datetime.now().strftime("%B %Y")   # e.g. "March 2026"
    q = f"{q} {month_year}"

    print(f"[web_search] '{raw}' → '{q}'")
    return q


def search_ddgs(query, max_results=4):
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "link":  r.get("href", ""),
                    "body":  r.get("body", "")
                })
        print(f"[web_search] {len(results)} results found")
        return results
    except ImportError:
        print("[web_search] ERROR: pip install ddgs")
        return []
    except Exception as e:
        print(f"[web_search] DDGS error: {e}")
        return []


def fetch_page_text(url, max_chars=2000):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=6)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = " ".join(
            p.get_text(separator=" ").strip()
            for p in soup.find_all("p")
            if len(p.get_text().strip()) > 40
        )
        return text[:max_chars]
    except Exception as e:
        print(f"[web_search] fetch error: {e}")
        return ""


def search_and_extract(raw_query: str, max_results=4) -> str:
    query = clean_query(raw_query)
    if not query:
        return "No search results found."

    results = search_ddgs(query, max_results)
    if not results:
        return "No search results found."

    collected = ""
    for r in results:
        body = r.get("body", "").strip()
        if not body:
            body = fetch_page_text(r["link"])
        if body:
            collected += f"[{r['title']}]\n{body}\n\n"

    return collected[:5000] if collected else "Could not extract content."