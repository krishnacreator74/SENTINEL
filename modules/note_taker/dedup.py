"""
dedup.py — Two-layer deduplication for Note Taker.

Layer 1: Exact hash filter  — O(1), catches identical text instantly.
Layer 2: Fuzzy similarity   — catches reworded duplicates per topic heading.

The dedup state is scoped to a single session. Create a new
DedupStore() at session start. Discard it at session end.

Usage:
    store = DedupStore()
    if not store.is_duplicate(heading, fact_text):
        # write the note
        pass
"""

import re
from collections import defaultdict
from difflib import SequenceMatcher

from . import config


# ── Text normalizer ────────────────────────────────────────────────────────────
def normalize(text: str) -> str:
    """
    Lowercase, strip punctuation, collapse whitespace.
    Used before hashing AND before similarity comparison so minor
    surface differences (punctuation, capitalisation) don't create
    false negatives.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text)        # collapse whitespace
    return text.strip()


# ── Similarity function ────────────────────────────────────────────────────────
def similarity(a: str, b: str) -> float:
    """
    Token-set ratio similarity between two strings.
    Handles word order differences better than raw SequenceMatcher.

    Example:
        "binary search runs in O log n"
        "binary search has time complexity O log n"
        → high score because token overlap is large

    Returns float between 0.0 and 1.0.
    """
    # Token set: compare sorted unique tokens to handle reordering
    tokens_a = set(normalize(a).split())
    tokens_b = set(normalize(b).split())

    # Jaccard on token sets — fast and good for short facts
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = len(tokens_a & tokens_b)
    union        = len(tokens_a | tokens_b)
    jaccard      = intersection / union

    # Also run SequenceMatcher on normalized strings for character-level coverage
    seq = SequenceMatcher(None, normalize(a), normalize(b)).ratio()

    # Take the max — if either method thinks it is similar, it probably is
    return max(jaccard, seq)


# ── Dedup store ────────────────────────────────────────────────────────────────
class DedupStore:
    """
    Session-scoped deduplication store.

    Maintains:
        _seen_hashes  — set of hash(normalized_text) for O(1) exact lookup
        _topic_facts  — dict of heading -> list of normalized fact strings
                        for per-topic fuzzy comparison

    Facts are compared within their topic heading only.
    This prevents cross-topic false positives and keeps the inner
    comparison loop small as the session grows.
    """

    def __init__(self):
        self._seen_hashes: set         = set()
        self._topic_facts: dict        = defaultdict(list)

    def _hash(self, text: str) -> str:
        return str(hash(normalize(text)))

    def is_duplicate(self, heading: str, fact: str) -> bool:
        """
        Returns True if this fact is a duplicate of something already stored
        under this heading.

        Layer 1 — exact hash check (O(1))
        Layer 2 — fuzzy similarity against existing facts for this heading only
        """
        norm = normalize(fact)
        h    = self._hash(norm)

        # Layer 1: exact match
        if h in self._seen_hashes:
            return True

        # Layer 2: fuzzy match within topic
        for existing in self._topic_facts[heading]:
            if similarity(norm, existing) >= config.SIMILARITY_THRESHOLD:
                return True

        # Not a duplicate — register it
        self._seen_hashes.add(h)
        self._topic_facts[heading].append(norm)
        return False

    def filter_box(self, heading: str, lines: list[str]) -> list[str]:
        """
        Given a list of fact lines for a heading, return only the lines
        that are NOT duplicates. Registers non-duplicates as it goes.

        Returns empty list if all lines are duplicates.
        """
        return [line for line in lines if not self.is_duplicate(heading, line)]

    def known_headings(self) -> list[str]:
        """Return all topic headings seen so far this session."""
        return list(self._topic_facts.keys())

    def fact_count(self) -> int:
        """Total unique facts stored across all topics."""
        return sum(len(v) for v in self._topic_facts.values())

    def compact_summary(self) -> str:
        """
        Serialize known facts into a compact string for injection into
        the LLM prompt. Keeps token cost low — one line per topic.

        Example output:
            PRODUCT MARKET EXPANSION: improvements to existing tech, radio preloaded music
            INDUSTRIAL TRANSFORMATIONS: healthcare, transportation, banking
        """
        if not self._topic_facts:
            return "(none yet)"

        lines = []
        for heading, facts in self._topic_facts.items():
            # Truncate long fact lists to keep context tight
            sample = facts[:8]
            lines.append(f"{heading.upper()}: {', '.join(sample)}")
        return "\n".join(lines)