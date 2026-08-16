"""Idempotency models + fingerprint (Phase 18.12.5)."""

import hashlib
import json
from dataclasses import dataclass, field

from app.core.time import utc_now


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    fingerprint: str
    result_reference: str = ""
    created_at: str = field(default_factory=utc_now)


def _canonical(value):
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def request_fingerprint(operation, resource_id, payload) -> str:
    serialized = json.dumps(
        _canonical({"operation": operation, "resource_id": resource_id,
                    "payload": payload}),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def is_valid_idempotency_key(key: str) -> bool:
    if not key or len(key) > 128:
        return False
    return all(c.isalnum() or c in "-_.:" for c in key)


__all__ = [
    "IdempotencyRecord",
    "request_fingerprint",
    "is_valid_idempotency_key",
]
