"""Document identity and versioning.

A stable document_id is derived from ``source_system`` + ``external_id`` so the
same external document never creates duplicate knowledge across syncs.
"""

import hashlib


def stable_document_id(source_system: str, external_id: str) -> str:
    key = f"{source_system}:{external_id}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"doc-{digest[:24]}"


def content_fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def is_version_changed(
    current_fingerprint: str | None, new_fingerprint: str
) -> bool:
    return current_fingerprint != new_fingerprint
