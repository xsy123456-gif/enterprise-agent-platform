from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentManifest:
    agent_id: Optional[str]
    version: Optional[str]
    name: Optional[str]
    description: Optional[str]
    owner: Optional[str]
    capabilities: list[str]
    tools: list[str]
    memory_policy: dict[str, list[str]]
    policy_ref: Optional[str]
    runtime: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
