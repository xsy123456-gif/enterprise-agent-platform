"""Agent lifecycle validation (Phase 12.1).

Validation mirrors the frozen Skill lifecycle and enforces (§6):

1. the manifest is structurally legal;
2. every declared skill exists (and has an ACTIVE version) in the SkillRegistry;
3. every declared capability exists in the platform capability whitelist.

The lifecycle states themselves live in ``app.commerce.agents.domain``
(``AGENT_*``); the ``AgentRegistry`` owns the state transitions.
"""

from app.commerce.agents.domain import (
    AGENT_ACTIVE,
    AGENT_DEPRECATED,
    AGENT_DISABLED,
    AGENT_DRAFT,
    AGENT_STATUSES,
    AGENT_VALIDATED,
)
from app.commerce.agents.errors import (
    AgentValidationError,
    UnknownSkillForAgent,
)

# The platform commerce capabilities an agent may declare.  This is a *declared*
# surface only — actual authorization is Identity -> Permission -> Governance.
KNOWN_AGENT_CAPABILITY_IDS = frozenset({
    "commerce.store.read",
    "commerce.catalog.read",
    "commerce.metrics.read",
    "commerce.inventory.read",
    "commerce.review.read",
    "commerce.review_insight.read",
    "commerce.advertising.read",
})


def validate_manifest_structure(manifest):
    if not manifest.skills:
        raise AgentValidationError(
            f"agent {manifest.agent_id!r} declares no skills"
        )
    if manifest.default_skill and manifest.default_skill not in manifest.skills:
        raise AgentValidationError(
            f"agent {manifest.agent_id!r} default_skill {manifest.default_skill!r} "
            f"is not in its skills"
        )


def validate_agent_skills(manifest, skill_registry):
    if skill_registry is None:
        return
    for skill_id in manifest.skills:
        try:
            skill_registry.get(skill_id)
            skill_registry.get_active_skill(skill_id)
        except Exception as error:  # noqa: BLE001 - re-raised as typed agent error
            raise UnknownSkillForAgent(
                f"agent {manifest.agent_id!r} references unknown/inactive "
                f"skill {skill_id!r}"
            ) from error


def validate_agent_capabilities(manifest, known_capability_ids):
    if known_capability_ids is None:
        return
    unknown = set(manifest.required_capabilities) - set(known_capability_ids)
    if unknown:
        raise AgentValidationError(
            f"agent {manifest.agent_id!r} declares unknown capabilities: "
            f"{sorted(unknown)}"
        )


def validate_agent(definition, manifest, skill_registry=None,
                   known_capability_ids=None):
    """Run all Phase 12.1 lifecycle checks; raise a typed error on failure."""
    validate_manifest_structure(manifest)
    validate_agent_skills(manifest, skill_registry)
    validate_agent_capabilities(manifest, known_capability_ids)
    return definition


__all__ = [
    "KNOWN_AGENT_CAPABILITY_IDS",
    "validate_manifest_structure",
    "validate_agent_skills",
    "validate_agent_capabilities",
    "validate_agent",
    "AGENT_STATUSES",
    "AGENT_DRAFT",
    "AGENT_VALIDATED",
    "AGENT_ACTIVE",
    "AGENT_DEPRECATED",
    "AGENT_DISABLED",
]
