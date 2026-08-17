"""Skill domain models.

A Skill is a versioned, deterministic business capability: it has a clear
business goal, a typed input, a typed output (``SkillResult`` wrapping a
``DiagnosticResult``), a capability contract, and one or more versioned
DiagnosticPlans it can run.  It is NOT a prompt and needs no LLM.
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
    required_capabilities: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "plan_ids", tuple(self.plan_ids or ()))
        object.__setattr__(self, "required_capabilities",
                           tuple(self.required_capabilities or ()))
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
            "required_capabilities": list(self.required_capabilities),
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
            required_capabilities=tuple(data.get("required_capabilities", ())),
        )


@dataclass(frozen=True)
class SkillInput:
    """Typed input to a Skill: a subject and an optional explicit plan.

    Carries NO tenant / principal / scope / permission: those are injected by
    the Runtime as the ``TrustedExecutionContext`` and can never be overridden
    by the input.
    """

    subject: SubjectRef | None = None
    plan_id: str | None = None
    trace_id: str = ""


@dataclass(frozen=True)
class SkillResult:
    """Typed output of a Skill execution."""

    skill_id: str
    skill_version: str
    plan_id: str
    plan_version: str
    diagnostic_result: object
    execution_id: str = ""
    trace_id: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "plan_id": self.plan_id,
            "plan_version": self.plan_version,
            "diagnostic_result": (
                self.diagnostic_result.to_dict()
                if hasattr(self.diagnostic_result, "to_dict")
                else self.diagnostic_result
            ),
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


__all__ = ["SkillDefinition", "SkillInput", "SkillResult"]

