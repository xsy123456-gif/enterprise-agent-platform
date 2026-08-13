"""Effective filter construction — ACL before retrieval.

The effective filter is the intersection of:

    Requested business filters
    ∩ Authorized scope
    ∩ System policy

It is platform-neutral; the adapter is responsible for mapping it onto the
concrete backend (e.g. Qdrant payload filters with ``_acl.*`` prefixes).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EffectiveFilter:
    tenant_id: str
    knowledge_types: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    stores: tuple[str, ...] = ()
    departments: tuple[str, ...] = ()
    security_level: str = "public"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "tenant_id": self.tenant_id,
            "knowledge_types": list(self.knowledge_types),
            "regions": list(self.regions),
            "stores": list(self.stores),
            "departments": list(self.departments),
            "security_level": self.security_level,
            "extra": dict(self.extra),
        }


def _intersect(requested, authorized):
    """Requested ∩ Authorized.

    An empty requested set means "no preference" (defer to authorized).
    An empty authorized set means "nothing is permitted".
    """
    if requested is None or len(requested) == 0:
        return tuple(authorized)
    if authorized is None or len(authorized) == 0:
        return ()
    return tuple(item for item in requested if item in authorized)


def intersect_lists(requested: list[str] | None, authorized: tuple[str, ...]) -> tuple[str, ...]:
    return _intersect(requested, authorized)
