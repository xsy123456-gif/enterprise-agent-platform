"""Skill domain models.

A Skill is a versioned, deterministic business capability: it has a clear
business goal, a typed input, a typed output (``DiagnosticResult``), and one or
more versioned DiagnosticPlans it can run.  It is NOT a prompt and needs no LLM.
"""

from dataclasses import dataclass, field

from app.commerce.contracts.subject import SubjectRef


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    version: str
    domain: str
    description: str
    plan_ids: tuple[str, ...] = ()
    default_plan_id: str = ""

    def __post_init__(self):
        object.__setattr__(self, "plan_ids", tuple(self.plan_ids or ()))
        if not self.skill_id:
            raise ValueError("skill_id is required")
        if not self.description:
            raise ValueError("skill description (business goal) is required")

    def supports(self, plan_id):
        return plan_id in self.plan_ids

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "domain": self.domain,
            "description": self.description,
            "plan_ids": list(self.plan_ids),
            "default_plan_id": self.default_plan_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillDefinition":
        return cls(
            skill_id=data["skill_id"],
            version=data["version"],
            domain=data.get("domain", ""),
            description=data.get("description", ""),
            plan_ids=tuple(data.get("plan_ids", ())),
            default_plan_id=data.get("default_plan_id", ""),
        )


@dataclass(frozen=True)
class SkillInput:
    """Typed input to a Skill: a subject and an optional explicit plan.

    ``subject`` is validated by the Skill (a SkillInput may be constructed with
    ``None`` subject; the Skill rejects it at execution).
    """

    subject: SubjectRef | None = None
    plan_id: str | None = None
    trace_id: str = ""


__all__ = ["SkillDefinition", "SkillInput"]
