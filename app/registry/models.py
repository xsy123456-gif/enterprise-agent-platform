from dataclasses import dataclass, field
from typing import Any, Optional


class AgentStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"

    ALL = {ACTIVE, INACTIVE, DEPRECATED}


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

    @property
    def registry_key(self):
        return f"{self.agent_id}:{self.version}"
