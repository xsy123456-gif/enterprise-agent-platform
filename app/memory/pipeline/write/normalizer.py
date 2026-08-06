from dataclasses import replace


class MemoryNormalizer:
    def normalize(self, candidate):
        return replace(
            candidate,
            type=candidate.type.strip().lower(),
            entity_id=candidate.entity_id.strip().lower().replace(" ", "_"),
            attribute=candidate.attribute.strip().lower().replace(" ", "_"),
        )
