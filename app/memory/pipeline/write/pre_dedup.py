import hashlib
import json


class MemoryPreDeduplicator:
    def __init__(self):
        self._seen = set()

    def accept(self, event, candidate):
        content = json.dumps(
            candidate.content, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        )
        value = (
            f"{event.user_id}|{event.agent_id}|{candidate.memory_key}|{content}"
        )
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        key = (event.event_id, digest)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True
