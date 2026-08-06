from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentDefinition:
    agent_id: str
    version: str
    system_prompt: str
    capabilities: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    memory_policy: Optional[str] = None
    memory_read: list[str] = field(default_factory=list)
    memory_write: list[str] = field(default_factory=list)
    policy_ref: Optional[str] = None
    runtime: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "system_prompt": self.system_prompt,
            "capabilities": list(self.capabilities),
            "allowed_tools": list(self.allowed_tools),
            "memory_policy": self.memory_policy,
            "memory_read": list(self.memory_read),
            "memory_write": list(self.memory_write),
            "policy_ref": self.policy_ref,
            "runtime": dict(self.runtime),
        }
