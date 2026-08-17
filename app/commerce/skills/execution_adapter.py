"""Diagnostic skill execution adapter (Phase 18.2).

Bridges the Employee Agent's Skill execution into the Runtime Foundation's
single Execution Plane.  This is a *thin* adapter: it wraps ``SkillSystem.run``
(which drives the deterministic ``PlanExecutor``) inside the ``ExecutionManager``
lifecycle, so a user-initiated Commerce Agent run produces a durable
``ExecutionRecord``.  It adds no new execution logic.
"""

import hashlib
import uuid
from dataclasses import dataclass
from types import SimpleNamespace

from app.commerce.domain.base import utc_now
from app.runtime.execution import ExecutionStatus


@dataclass(frozen=True)
class SkillExecutionContext:
    """Runtime-injected execution identity (§9.3)."""

    execution_id: str
    trace_id: str
    tenant_id: str
    agent_id: str
    agent_version: str
    principal_id: str = ""
    artifact_id: str = ""
    artifact_hash: str = ""
    started_at: str = ""

    def __post_init__(self):
        if not self.execution_id:
            object.__setattr__(self, "execution_id", uuid.uuid4().hex)
        if not self.started_at:
            object.__setattr__(self, "started_at", utc_now())


class DiagnosticSkillExecutionAdapter:
    """Runtime Node -> SkillSystem.run() -> PlanExecutor, under the ExecutionManager."""

    def __init__(self, skill_system, execution_manager=None):
        self.skill_system = skill_system
        self.execution_manager = execution_manager

    def execute(self, context: SkillExecutionContext, skill_id, subject,
                trusted_context=None, fact_executor=None, plan_id=None,
                skill_version=None):
        record = self._start(context, skill_id)
        try:
            result = self.skill_system.diagnose(
                skill_id, subject,
                trusted_context=trusted_context,
                fact_executor=fact_executor,
                plan_id=plan_id,
                execution_id=context.execution_id,
                skill_version=skill_version,
            )
        except Exception:
            self._finish(context, record, ExecutionStatus.FAILED)
            raise
        self._finish(context, record, ExecutionStatus.COMPLETED)
        return result

    def _start(self, context, skill_id):
        if self.execution_manager is None:
            return None
        from app.runtime.contracts.state import AgentRuntimeState

        state = AgentRuntimeState(
            task_id=context.execution_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            agent_id=context.agent_id,
            agent_version=context.agent_version,
            execution_id=context.execution_id,
            user_id=context.principal_id,
        )
        artifact_hash = context.artifact_hash or hashlib.sha256(
            f"{context.agent_id}:{context.agent_version}:{skill_id}".encode("utf-8")
        ).hexdigest()
        artifact = SimpleNamespace(
            artifact_id=context.artifact_id
            or f"{context.agent_id}:{context.agent_version}",
            artifact_hash=artifact_hash,
            backend_type="skill",
        )
        record = self.execution_manager.create(state, artifact)
        self.execution_manager.transition(record.execution_id,
                                          ExecutionStatus.RUNNING)
        return record

    def _finish(self, context, record, status):
        if record is not None:
            self.execution_manager.transition(record.execution_id, status)


__all__ = ["SkillExecutionContext", "DiagnosticSkillExecutionAdapter"]
