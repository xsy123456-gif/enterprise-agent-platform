"""Skill errors."""

from app.commerce.contracts.errors import CommerceError


class SkillError(CommerceError):
    """A skill invocation failed."""


class SkillValidationError(SkillError):
    """A skill definition failed capability / lifecycle validation."""


class UnknownPlanForSkill(SkillError):
    """A plan is not supported by the skill."""


class PlanNotActiveError(SkillError):
    """The selected plan has no ACTIVE version."""


class SkillNotActiveError(SkillError):
    """The selected skill has no ACTIVE version."""


__all__ = [
    "SkillError",
    "SkillValidationError",
    "UnknownPlanForSkill",
    "PlanNotActiveError",
    "SkillNotActiveError",
]
