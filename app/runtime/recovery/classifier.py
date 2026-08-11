"""Deterministic classification of normalized Agent errors."""

from app.runtime.multi_agent.contracts import AgentExecutionResult
from app.runtime.multi_agent.models import AgentResultStatus
from app.runtime.recovery.models import AgentFailure, FailureType


class FailureClassifier:
    TIMEOUT_MARKERS = ("TIMEOUT", "DEADLINE")
    TRANSIENT_MARKERS = ("NETWORK", "CONNECTION", "UNAVAILABLE", "RATE_LIMIT")
    POLICY_MARKERS = ("PERMISSION", "POLICY", "DENIED", "FORBIDDEN")
    VALIDATION_MARKERS = ("VALIDATION", "SCHEMA", "INVALID")
    DEPENDENCY_MARKERS = ("DEPENDENCY", "UPSTREAM")

    def classify(self, result, attempt_id):
        if not isinstance(result, AgentExecutionResult):
            raise TypeError("result must be AgentExecutionResult")
        if result.status not in {
            AgentResultStatus.FAILED,
            AgentResultStatus.DENIED,
            AgentResultStatus.CANCELLED,
        }:
            raise ValueError("Only failed Agent results can be classified")
        error = result.errors[0] if result.errors else None
        code = error.code.upper() if error else "UNKNOWN_FAILURE"
        category = error.category.upper() if error else "UNKNOWN"
        failure_type = self._type_for(code, category, result.status)
        retryable = self._retryable(failure_type, error)
        return AgentFailure(
            execution_id=result.execution_id,
            agent_execution_id=result.agent_execution_id,
            agent_id=result.agent_id,
            attempt_id=attempt_id,
            failure_type=failure_type,
            error_code=code,
            retryable=retryable,
            details_ref=error.details_ref if error else None,
        )

    def _type_for(self, code, category, status):
        combined = f"{code} {category}"
        if status is AgentResultStatus.DENIED or any(
            marker in combined for marker in self.POLICY_MARKERS
        ):
            return FailureType.POLICY
        if any(marker in combined for marker in self.TIMEOUT_MARKERS):
            return FailureType.TIMEOUT
        if any(marker in combined for marker in self.TRANSIENT_MARKERS):
            return FailureType.TRANSIENT
        if any(marker in combined for marker in self.VALIDATION_MARKERS):
            return FailureType.VALIDATION
        if any(marker in combined for marker in self.DEPENDENCY_MARKERS):
            return FailureType.DEPENDENCY
        if "PERMANENT" in combined:
            return FailureType.PERMANENT
        return FailureType.UNKNOWN

    @staticmethod
    def _retryable(failure_type, error):
        if failure_type in {FailureType.POLICY, FailureType.VALIDATION, FailureType.PERMANENT}:
            return False
        if failure_type in {FailureType.TIMEOUT, FailureType.TRANSIENT}:
            return True
        return bool(error.retryable) if error else False
