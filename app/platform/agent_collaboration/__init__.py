"""Enterprise Multi-Agent Collaboration Runtime (Phase 14).

Lets multiple agents decompose a complex task, delegate sub-tasks, share
controlled context and aggregate results — all through the collaboration
runtime (never by importing another agent) and under governance.
"""

from app.platform.agent_collaboration.aggregator import (
    AgentResultAggregator,
    AgentResultItem,
    AggregatedAgentResult,
    Conflict,
    ConflictResolver,
)
from app.platform.agent_collaboration.audit import (
    CollaborationAuditLogger,
    CollaborationAuditRecord,
)
from app.platform.agent_collaboration.context import (
    AgentContextEnvelope,
    AgentContextProvider,
)
from app.platform.agent_collaboration.delegation import DelegationExecutor
from app.platform.agent_collaboration.domain import (
    AgentDelegationRequest,
    AgentDelegationResult,
    CollaborationTask,
)
from app.platform.agent_collaboration.errors import (
    AgentUnavailableError,
    CollaborationError,
    ContextAccessDeniedError,
    CycleDetectedError,
    DelegationDeniedError,
    MaxDepthExceededError,
)
from app.platform.agent_collaboration.evaluation import (
    CollaborationEvaluation,
    CollaborationEvaluationStore,
    CollaborationSummary,
)
from app.platform.agent_collaboration.governance import (
    AgentCollaborationPolicy,
    CollaborationAccessControl,
)
from app.platform.agent_collaboration.orchestrator import MultiAgentOrchestrator
from app.platform.agent_collaboration.protocol import (
    AgentMessage,
    AgentMessageProtocol,
)
from app.platform.agent_collaboration.task_graph import (
    AgentTask,
    AgentTaskGraph,
    GraphValidator,
)

__all__ = [
    "CollaborationTask",
    "AgentDelegationRequest",
    "AgentDelegationResult",
    "AgentMessage",
    "AgentMessageProtocol",
    "AgentTask",
    "AgentTaskGraph",
    "GraphValidator",
    "DelegationExecutor",
    "MultiAgentOrchestrator",
    "AgentContextEnvelope",
    "AgentContextProvider",
    "AgentResultItem",
    "AggregatedAgentResult",
    "Conflict",
    "ConflictResolver",
    "AgentResultAggregator",
    "AgentCollaborationPolicy",
    "CollaborationAccessControl",
    "CollaborationEvaluation",
    "CollaborationSummary",
    "CollaborationEvaluationStore",
    "CollaborationAuditRecord",
    "CollaborationAuditLogger",
    "CollaborationError",
    "CycleDetectedError",
    "MaxDepthExceededError",
    "DelegationDeniedError",
    "ContextAccessDeniedError",
    "AgentUnavailableError",
]
