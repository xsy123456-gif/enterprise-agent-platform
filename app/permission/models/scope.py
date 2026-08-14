"""Permission scope — structured, extensible dimension/value model."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScopeGrant:
    dimension: str
    values: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self):
        object.__setattr__(self, "values", frozenset(self.values or ()))

    def to_dict(self):
        return {"dimension": self.dimension, "values": sorted(self.values)}


@dataclass(frozen=True)
class PermissionScope:
    grants: tuple[ScopeGrant, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "grants", tuple(self.grants or ()))

    def values_for(self, dimension: str) -> frozenset[str]:
        for grant in self.grants:
            if grant.dimension == dimension:
                return grant.values
        return frozenset()

    def has_dimension(self, dimension: str) -> bool:
        return any(g.dimension == dimension for g in self.grants)

    def to_dict(self):
        return {"grants": [g.to_dict() for g in self.grants]}
