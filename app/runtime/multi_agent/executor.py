"""Ports for executing Supervisor-owned Agent graphs.

No scheduler or backend implementation belongs to Group 1.  These ports make
the ownership boundary explicit without introducing a second Runtime.
"""

from abc import ABC, abstractmethod

from app.runtime.multi_agent.contracts import (
    AgentExecutionResult,
    AgentInvocationRequest,
)
from app.runtime.multi_agent.graph import AgentExecutionGraph
from app.runtime.multi_agent.models import AgentNode


class AgentRuntimeInvoker(ABC):
    """Supervisor-side port; implementations must delegate to GraphRuntime."""

    @abstractmethod
    def invoke(
        self,
        node: AgentNode,
        request: AgentInvocationRequest,
    ) -> AgentExecutionResult:
        pass


class SupervisorGraphRuntime(ABC):
    """Owns graph orchestration while Agent Runtimes remain isolated units."""

    @abstractmethod
    def execute(
        self,
        graph: AgentExecutionGraph,
        invocations: tuple[AgentInvocationRequest, ...],
    ) -> tuple[AgentExecutionResult, ...]:
        pass
