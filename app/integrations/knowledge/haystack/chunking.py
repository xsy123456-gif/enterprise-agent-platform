"""Chunking strategy per document type (Chinese-friendly).

Haystack's ``DocumentSplitter`` with ``sentence``/``word`` requires NLTK and is
English-oriented, so we provide a platform-owned character-window splitter that
is deterministic and works for CJK text.  It is a plain function, not a
third-party fork.
"""

import re

# (chunk_size, overlap) per document_type; characters for CJK text.
_STRATEGIES = {
    "faq": (200, 0),
    "policy": (400, 40),
    "sop": (400, 40),
    "product_knowledge": (300, 30),
    "default": (300, 30),
}


def _clean(text):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text(content: str, document_type: str) -> list[str]:
    """Return non-overlapping-ish character-window chunks (stable order)."""
    cleaned = _clean(content)
    if not cleaned:
        return []
    size, overlap = _STRATEGIES.get(document_type, _STRATEGIES["default"])
    size = max(1, size)
    overlap = max(0, min(overlap, size - 1))

    chunks = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = start + size
        chunks.append(cleaned[start:end])
        if end >= length:
            break
        start = end - overlap
    return chunks
