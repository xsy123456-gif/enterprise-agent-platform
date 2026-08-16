"""Skill router contracts (Phase 12.3)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillRoutingRequest:
    message: str
    available_skills: tuple[str, ...] = ()
    context: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "available_skills", tuple(self.available_skills or ()))
        object.__setattr__(self, "context", dict(self.context or {}))


@dataclass(frozen=True)
class SkillRoutingResult:
    selected_skill: str = ""
    confidence: float = 0.0
    alternatives: tuple[str, ...] = ()
    reason: str = ""
    layer: str = ""
    subject: Any = None

    def __post_init__(self):
        object.__setattr__(self, "alternatives", tuple(self.alternatives or ()))


__all__ = ["SkillRoutingRequest", "SkillRoutingResult"]
