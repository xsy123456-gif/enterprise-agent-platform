"""Commerce Business Skills (Phase 10).

Deterministic, versioned business capabilities that resolve a versioned
DiagnosticPlan and execute it to produce a ``SkillResult`` wrapping a
``DiagnosticResult`` — without any LLM or prompt.
"""

from app.commerce.skills.definitions import build_business_skill_definitions
from app.commerce.skills.errors import (
    PlanNotActiveError,
    SkillError,
    SkillNotActiveError,
    SkillValidationError,
    UnknownPlanForSkill,
)
from app.commerce.skills.models import SkillDefinition, SkillInput, SkillResult
from app.commerce.skills.registry import (
    SKILL_ACTIVE,
    SKILL_DEPRECATED,
    SKILL_DISABLED,
    SKILL_DRAFT,
    SKILL_STATUSES,
    SKILL_VALIDATED,
    SkillRegistry,
)
from app.commerce.skills.skill import Skill
from app.commerce.skills.system import SkillSystem, build_skill_system
from app.commerce.skills.validation import (
    KNOWN_CAPABILITY_IDS,
    validate_skill_capabilities,
    validate_skill_plan_consistency,
)

__all__ = [
    "SkillDefinition",
    "SkillInput",
    "SkillResult",
    "Skill",
    "SkillRegistry",
    "SkillSystem",
    "build_skill_system",
    "build_business_skill_definitions",
    "SkillError",
    "SkillValidationError",
    "UnknownPlanForSkill",
    "PlanNotActiveError",
    "SkillNotActiveError",
    "SKILL_DRAFT",
    "SKILL_VALIDATED",
    "SKILL_ACTIVE",
    "SKILL_DEPRECATED",
    "SKILL_DISABLED",
    "SKILL_STATUSES",
    "KNOWN_CAPABILITY_IDS",
    "validate_skill_capabilities",
    "validate_skill_plan_consistency",
]
