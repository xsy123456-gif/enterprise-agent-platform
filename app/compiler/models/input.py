from dataclasses import dataclass
from typing import Any

from app.agents.definition import AgentDefinition


@dataclass(frozen=True)
class CompileInput:
    """All control-plane dependencies required to compile one Agent."""

    agent_definition: AgentDefinition
    capability_catalog: Any
    tool_registry: Any
    policy_registry: Any
    compiler_version: str

    def __post_init__(self):
        if not self.compiler_version:
            raise ValueError("compiler_version is required")
