from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents.definition import AgentDefinition


class AgentStatus:
    DRAFT = "draft"
    VALIDATING = "validating"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    INACTIVE = "inactive"

    ALL = {
        DRAFT,
        VALIDATING,
        REVIEWING,
        APPROVED,
        ACTIVE,
        SUSPENDED,
        DEPRECATED,
        ARCHIVED,
        INACTIVE,
    }


@dataclass
class Capability:
    capability_id: str
    description: str = ""


@dataclass
class ToolBinding:
    capability_id: str
    tool_name: str
    required_permission: str
    risk_level: str


@dataclass
class Policy:
    policy_id: str
    permission_rules: list[str] = field(default_factory=list)
    data_scope: list[str] = field(default_factory=list)
    audit_level: str = "standard"


@dataclass
class Agent:
    agent_id: str
    name: str
    version: str
    description: str
    owner: str
    status: str
    capabilities: list[str]
    instance: Any
    policy_id: Optional[str] = None
    definition: Optional[AgentDefinition] = None

    @property
    def registry_key(self):
        return f"{self.agent_id}:{self.version}"
