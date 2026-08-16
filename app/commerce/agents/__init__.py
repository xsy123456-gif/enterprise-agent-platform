"""Employee Agent Runtime Layer (Phase 12).

The business Agent application layer built on the frozen Runtime / Skill / Plan /
Tool / Diagnostic foundation.  An Agent is the business *entry point*: it routes
a user message to a Skill, never calls Tools/Repository directly and never
performs business reasoning itself.
"""

from app.commerce.agents.domain import (
    AGENT_ACTIVE,
    AGENT_DEPRECATED,
    AGENT_DISABLED,
    AGENT_DRAFT,
    AGENT_STATUSES,
    AGENT_VALIDATED,
    RESPONSE_ANSWER,
    RESPONSE_CLARIFICATION,
    RESPONSE_DIAGNOSTIC,
    RESPONSE_ERROR,
    RESPONSE_TYPES,
    SESSION_ACTIVE,
    SESSION_CLOSED,
    SESSION_COMPLETED,
    SESSION_CREATED,
    SESSION_FAILED,
    SESSION_STATUSES,
    SESSION_WAITING,
    AgentDefinition,
    AgentRequest,
    AgentResponse,
    AgentSession,
)
from app.commerce.agents.errors import (
    AgentError,
    AgentManifestError,
    AgentNotActiveError,
    AgentValidationError,
    UnknownSkillForAgent,
)
from app.commerce.agents.lifecycle import (
    KNOWN_AGENT_CAPABILITY_IDS,
    validate_agent,
    validate_agent_capabilities,
    validate_agent_skills,
    validate_manifest_structure,
)
from app.commerce.agents.manifest import AgentManifest
from app.commerce.agents.registry import AgentRegistry

__all__ = [
    "AgentDefinition",
    "AgentManifest",
    "AgentSession",
    "AgentRequest",
    "AgentResponse",
    "AgentRegistry",
    "AgentError",
    "AgentValidationError",
    "AgentNotActiveError",
    "AgentManifestError",
    "UnknownSkillForAgent",
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
    "SESSION_STATUSES",
    "SESSION_CREATED",
    "SESSION_ACTIVE",
    "SESSION_WAITING",
    "SESSION_COMPLETED",
    "SESSION_FAILED",
    "SESSION_CLOSED",
    "RESPONSE_TYPES",
    "RESPONSE_ANSWER",
    "RESPONSE_DIAGNOSTIC",
    "RESPONSE_CLARIFICATION",
    "RESPONSE_ERROR",
]
