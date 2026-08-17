"""Opaque pagination cursors (Phase 18.13.1).

The cursor is a base64-encoded JSON object — opaque to the client, never a raw
offset.  No encryption is needed; this only models the provider contract.
"""

import base64
import json

PAGE_SIZE_PARAM = "page_size"
NEXT_TOKEN_PARAM = "next_token"


def encode_cursor(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(token: str) -> dict | None:
    if not token:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(token.encode("ascii")))
    except Exception:
        return None


def paginate(items, page_size, token):
    """Return ``{"items": [...], "next_token": ...}`` for a list of records."""
    size = max(1, int(page_size))
    start = 0
    cursor = decode_cursor(token)
    if cursor is not None:
        start = int(cursor.get("offset", 0))
    batch = items[start:start + size]
    next_offset = start + len(batch)
    next_token = encode_cursor({"offset": next_offset}) if next_offset < len(items) else None
    return {"items": batch, "next_token": next_token}


__all__ = ["encode_cursor", "decode_cursor", "paginate"]
