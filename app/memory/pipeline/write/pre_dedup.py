import hashlib
import json


class MemoryPreDeduplicator:
    """Pre-deduplication within a single event batch via SHA-256 exact-match.

    The dedup set is NOT stored on the instance; it is passed by the caller per event
    to avoid unbounded memory growth.
    """

    @staticmethod
    def accept(event, candidate, seen):
        content = json.dumps(
            candidate.content, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        )
        value = (
            f"{event.user_id}|{event.agent_id}|{candidate.memory_key}|{content}"
        )
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        key = (event.event_id, digest)
        if key in seen:
            return False
        seen.add(key)
        return True
