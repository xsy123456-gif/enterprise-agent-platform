from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryIdentity:
    type: str
    entity_id: str
    attribute: str

    def __post_init__(self):
        for field_name in ("type", "entity_id", "attribute"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
            object.__setattr__(self, field_name, value.strip())

    @property
    def memory_key(self):
        return f"{self.type}:{self.entity_id}:{self.attribute}"
