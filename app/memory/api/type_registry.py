"""Memory type registry — frozen set of supported Memory types.

External callers use these types via MemoryType Enum.
Internal pipelines validate candidates against this registry.
"""

from enum import Enum


class MemoryType(str, Enum):
    PROFILE = "profile"
    PREFERENCE = "preference"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    ACTIVE_TASK = "active_task"
    PERSON = "person"
    CUSTOMER = "customer"
    FACT = "fact"

    @classmethod
    def values(cls) -> set[str]:
        return {member.value for member in cls}

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls._value2member_map_


MemoryTypeRegistry = MemoryType
_KNOWN_TYPES = MemoryType.values()


def validate_type(value: str) -> str:
    """Normalize and validate a type string against the registry."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Memory type must be a non-empty string")
    normalized = value.strip().lower()
    if normalized not in _KNOWN_TYPES:
        raise ValueError(
            f"Unknown Memory type: {value!r}. Allowed: {sorted(_KNOWN_TYPES)}"
        )
    return normalized
