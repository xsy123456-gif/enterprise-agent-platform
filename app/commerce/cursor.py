"""Unified cursor-pagination codec shared by the Commerce Read Tools.

The cursor is an opaque, resource-bound token.  Decoding/validation failures are
NEVER silently reset to the first page — they raise a typed
``CommerceValidationError`` so the tool returns INVALID_REQUEST before any
canonical query.
"""

import base64
import json

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.query import PageInfo

MAX_PAGE_LIMIT = 100


def encode_cursor(context_key, offset):
    """Opaque cursor bound to ``context_key`` at the given 0-based offset."""
    payload = json.dumps({"k": context_key, "o": int(offset)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor, context_key):
    """Decode + validate a cursor for ``context_key``, returning the offset.

    An empty cursor means the first page (offset 0).  A malformed cursor or a
    cursor bound to a different context raises ``CommerceValidationError``.
    """
    if cursor in (None, ""):
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except Exception as error:  # noqa: BLE001 - any decode failure is malformed
        raise CommerceValidationError("invalid cursor") from error
    if not isinstance(data, dict) or data.get("k") != context_key:
        raise CommerceValidationError("cursor does not match query")
    offset = data.get("o")
    if not isinstance(offset, int) or offset < 0:
        raise CommerceValidationError("invalid cursor")
    return offset


def validate_page(page):
    if page.limit < 1 or page.limit > MAX_PAGE_LIMIT:
        raise CommerceValidationError(
            f"page limit must be between 1 and {MAX_PAGE_LIMIT}"
        )


def paginate(items, page, context_key):
    """Apply cursor pagination over ``items`` and return ``(page_items, PageInfo)``."""
    validate_page(page)
    offset = decode_cursor(page.cursor, context_key)
    page_items = list(items)[offset: offset + page.limit]
    next_offset = offset + len(page_items)
    next_cursor = (
        encode_cursor(context_key, next_offset) if next_offset < len(items) else None
    )
    return page_items, PageInfo(
        next_cursor=next_cursor, has_more=next_cursor is not None,
        returned_count=len(page_items),
    )


__all__ = [
    "MAX_PAGE_LIMIT",
    "encode_cursor",
    "decode_cursor",
    "validate_page",
    "paginate",
]
