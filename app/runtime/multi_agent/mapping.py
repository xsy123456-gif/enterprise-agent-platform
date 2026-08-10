"""Adapters from backend-neutral Runtime results to Multi-Agent contracts."""

import re

from app.runtime.contracts import ExecutionResult
from app.runtime.multi_agent.contracts import AgentExecutionResult
from app.runtime.multi_agent.models import (
    AgentError,
    AgentProvenance,
    AgentResultStatus,
)


class AgentResultMapper:
    """Maps Runtime output without exposing its state, events or backend objects."""

    STATUS_MAP = {
        "completed": AgentResultStatus.COMPLETED,
        "failed": AgentResultStatus.FAILED,
        "cancelled": AgentResultStatus.CANCELLED,
        "denied": AgentResultStatus.DENIED,
        "partial": AgentResultStatus.PARTIAL,
    }

    def map(self, result, request, node, *, confidence=None):
        if not isinstance(result, ExecutionResult):
            raise TypeError("result must be ExecutionResult")
        self._validate_identity(request, node)
        status = self.STATUS_MAP.get(result.status, AgentResultStatus.PARTIAL)
        errors = ()
        if status is AgentResultStatus.FAILED:
            errors = (AgentError(
                code="RUNTIME_EXECUTION_FAILED",
                category="runtime",
                message="Agent Runtime execution failed",
                retryable=False,
                details_ref=f"trace://{request.trace_id}",
            ),)
        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_execution_id=request.agent_execution_id,
            agent_id=node.agent_id,
            agent_version=self._artifact_version(node.artifact_id),
            artifact_id=node.artifact_id,
            artifact_hash=node.artifact_hash,
            status=status,
            output={"response": result.response} if result.response is not None else {},
            errors=errors,
            confidence=confidence,
            metadata={"runtime_task_id": result.task_id},
            provenance=self._provenance(request, node),
        )

    def map_error(self, error, request, node, *, retryable=False):
        if not isinstance(error, Exception):
            raise TypeError("error must be an Exception")
        self._validate_identity(request, node)
        safe_code = re.sub(
            r"(?<!^)(?=[A-Z])", "_", error.__class__.__name__
        ).upper()
        safe_code = re.sub(r"[^A-Z0-9]+", "_", safe_code).strip("_")
        safe_code = safe_code or "RUNTIME_ERROR"
        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_execution_id=request.agent_execution_id,
            agent_id=node.agent_id,
            agent_version=self._artifact_version(node.artifact_id),
            artifact_id=node.artifact_id,
            artifact_hash=node.artifact_hash,
            status=AgentResultStatus.FAILED,
            output={},
            errors=(AgentError(
                code=safe_code,
                category="runtime",
                message="Agent Runtime execution failed",
                retryable=bool(retryable),
                details_ref=f"trace://{request.trace_id}",
            ),),
            metadata={},
            provenance=self._provenance(request, node),
        )

    @staticmethod
    def _validate_identity(request, node):
        if request.target_agent != node.agent_id:
            raise ValueError("Invocation target does not match Agent node")
        if request.target_artifact_id != node.artifact_id:
            raise ValueError("Invocation artifact ID does not match Agent node")
        if request.target_artifact_hash != node.artifact_hash:
            raise ValueError("Invocation artifact hash does not match Agent node")

    @staticmethod
    def _artifact_version(artifact_id):
        parts = artifact_id.split(":", 2)
        if len(parts) < 2 or not parts[1]:
            raise ValueError("Artifact ID must include Agent version")
        return parts[1]

    @classmethod
    def _provenance(cls, request, node):
        return AgentProvenance(
            source_agent_id=node.agent_id,
            source_agent_version=cls._artifact_version(node.artifact_id),
            source_artifact_id=node.artifact_id,
            source_artifact_hash=node.artifact_hash,
            source_agent_execution_id=request.agent_execution_id,
        )
