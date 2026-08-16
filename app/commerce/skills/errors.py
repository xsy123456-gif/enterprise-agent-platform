"""Skill errors."""

from app.commerce.contracts.errors import CommerceError


class SkillError(CommerceError):
    """A skill invocation failed."""


class UnknownPlanForSkill(SkillError):
    """A plan is not supported by the skill."""


class PlanNotActiveError(SkillError):
    """The selected plan has no ACTIVE version."""


__all__ = ["SkillError", "UnknownPlanForSkill", "PlanNotActiveError"]
