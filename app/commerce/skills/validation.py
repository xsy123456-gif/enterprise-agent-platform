"""Skill validation: capability contract + plan consistency."""

from app.commerce.skills.errors import SkillValidationError

# The six Platform commerce capabilities a Skill may declare.
KNOWN_CAPABILITY_IDS = frozenset({
    "commerce.store.read",
    "commerce.catalog.read",
    "commerce.metrics.read",
    "commerce.inventory.read",
    "commerce.review.read",
    "commerce.advertising.read",
})


def validate_skill_capabilities(definition):
    """A Skill must not declare a capability that does not exist."""
    unknown = set(definition.required_capabilities) - KNOWN_CAPABILITY_IDS
    if unknown:
        raise SkillValidationError(
            f"skill {definition.skill_id!r} declares unknown capabilities: "
            f"{sorted(unknown)}"
        )


def validate_skill_plan_consistency(definition, plan_registry):
    """A Skill's required_capabilities must equal the union of its plans'
    required_capabilities."""
    if plan_registry is None:
        return
    plan_capabilities = set()
    for plan_id in definition.plan_ids:
        plan = plan_registry.get_definition(plan_id)
        plan_capabilities.update(plan.required_capabilities)
    declared = set(definition.required_capabilities)
    if declared != plan_capabilities:
        raise SkillValidationError(
            f"skill {definition.skill_id!r} declares capabilities "
            f"{sorted(declared)} but its plans require {sorted(plan_capabilities)}"
        )


__all__ = [
    "KNOWN_CAPABILITY_IDS",
    "validate_skill_capabilities",
    "validate_skill_plan_consistency",
]
