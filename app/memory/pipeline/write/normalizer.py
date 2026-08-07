from dataclasses import replace

from app.memory.api.type_registry import MemoryType
from app.memory.errors import MemoryValidationError


class MemoryNormalizer:
    def normalize(self, candidate):
        raw_type = candidate.type.strip().lower()
        if raw_type not in MemoryType.values():
            raise MemoryValidationError(
                f"Unknown Memory type from candidate: {candidate.type!r}. "
                f"Allowed: {sorted(MemoryType.values())}"
            )
        return replace(
            candidate,
            type=raw_type,
            entity_id=candidate.entity_id.strip().lower().replace(" ", "_"),
            attribute=candidate.attribute.strip().lower().replace(" ", "_"),
        )
