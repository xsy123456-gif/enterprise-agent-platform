"""Runtime-owned failure handling, retry execution and checkpoint reuse."""

import time

from app.runtime.governance.events import RuntimeEvent
from app.runtime.multi_agent.contracts import AgentExecutionResult
from app.runtime.multi_agent.models import AgentResultStatus
from app.runtime.multi_agent.mapping import AgentResultMapper
from app.runtime.recovery.classifier import FailureClassifier
from app.runtime.recovery.escalation import (
    FailureEscalationEvent,
    NullFailureEscalationBoundary,
)
from app.runtime.recovery.models import (
    AgentAttemptRecord,
    AttemptStatus,
    RecoveryAction,
    RecoveryOutcome,
)
from app.runtime.recovery.retry import RetryManager


class RecoveryManager:
    """Executes attempts without touching Agent state, Tool, Memory or Permission."""

    def __init__(
        self,
        classifier=None,
        retry_manager=None,
        checkpoint_store=None,
        escalation_boundary=None,
        event_bus=None,
        event_store=None,
        result_mapper=None,
        sleeper=None,
    ):
        self.classifier = classifier or FailureClassifier()
        self.retry_manager = retry_manager or RetryManager()
        self.checkpoint_store = checkpoint_store
        self.escalation_boundary = (
            escalation_boundary or NullFailureEscalationBoundary()
        )
        self.event_bus = event_bus
        self.event_store = event_store
        self.result_mapper = result_mapper or AgentResultMapper()
        self.sleeper = sleeper or time.sleep

    def execute(self, node, request, invoke, policy):
        attempts = []
        failures = []
        retrying = False
        while True:
            attempt = AgentAttemptRecord(
                agent_execution_id=request.agent_execution_id,
                attempt_number=len(attempts) + 1,
            )
            if retrying:
                self._restore_checkpoint(request, node)
                attempt = attempt.transition(AttemptStatus.RETRYING)
            attempt = attempt.transition(AttemptStatus.RUNNING)
            if retrying:
                self._emit(
                    "agent.retry.started", request, node,
                    attempt_id=attempt.attempt_id,
                    retry_number=attempt.attempt_number - 1,
                    recovery_action=RecoveryAction.RETRY.value,
                    status="running",
                )
            try:
                result = invoke()
                if not isinstance(result, AgentExecutionResult):
                    raise TypeError("Recovery invoke must return AgentExecutionResult")
            except Exception as error:
                result = self.result_mapper.map_error(error, request, node)
            if result.status is AgentResultStatus.COMPLETED:
                attempt = attempt.transition(AttemptStatus.SUCCESS)
                attempts.append(attempt)
                if retrying:
                    self._emit(
                        "agent.retry.completed", request, node,
                        attempt_id=attempt.attempt_id,
                        retry_number=attempt.attempt_number - 1,
                        recovery_action=RecoveryAction.RESUME.value,
                        status="completed",
                    )
                return RecoveryOutcome(
                    result=result, attempts=tuple(attempts), failures=tuple(failures),
                    action=RecoveryAction.RESUME,
                )
            failure = self.classifier.classify(result, attempt.attempt_id)
            attempt = attempt.transition(AttemptStatus.FAILED, failure.failure_id)
            attempts.append(attempt)
            failures.append(failure)
            self._emit(
                "agent.failure.detected", request, node,
                attempt_id=attempt.attempt_id, failure_id=failure.failure_id,
                retry_number=attempt.attempt_number - 1,
                status="failed",
            )
            decision = self.retry_manager.decide(failure, attempts, policy)
            if decision.action is RecoveryAction.RETRY:
                self._save_checkpoint(request, node, failure, decision.retry_number)
                self._emit(
                    "agent.retry.requested", request, node,
                    attempt_id=attempt.attempt_id, failure_id=failure.failure_id,
                    retry_number=decision.retry_number,
                    recovery_action=decision.action.value,
                    status="requested",
                )
                if decision.delay_seconds:
                    self.sleeper(decision.delay_seconds)
                retrying = True
                continue
            if decision.action is RecoveryAction.ESCALATE:
                escalation = FailureEscalationEvent.from_failure(
                    failure, decision.reason
                )
                self.escalation_boundary.request(escalation)
                self._emit(
                    "agent.escalation.required", request, node,
                    attempt_id=attempt.attempt_id, failure_id=failure.failure_id,
                    retry_number=decision.retry_number,
                    recovery_action=decision.action.value,
                    status="required",
                )
            return RecoveryOutcome(
                result=result, attempts=tuple(attempts), failures=tuple(failures),
                action=decision.action,
            )

    def _save_checkpoint(self, request, node, failure, retry_attempt):
        if self.checkpoint_store is None:
            return None
        return self.checkpoint_store.save_checkpoint(
            request.execution_id,
            {
                "execution_id": request.execution_id,
                "failed_agent_execution_id": request.agent_execution_id,
                "failed_node": node.agent_id,
                "retry_attempt": retry_attempt,
            },
            current_node=node.agent_id,
            pending_action={"recovery_action": RecoveryAction.RETRY.value},
            artifact_hash=node.artifact_hash,
            failed_agent_execution_id=request.agent_execution_id,
            failed_node=node.agent_id,
            retry_attempt=retry_attempt,
        )

    def _restore_checkpoint(self, request, node):
        if self.checkpoint_store is None:
            return None
        checkpoint = self.checkpoint_store.load_checkpoint(request.execution_id)
        if checkpoint is None:
            raise KeyError(f"Recovery checkpoint not found: {request.execution_id}")
        def value(name):
            return checkpoint.get(name) if isinstance(checkpoint, dict) else getattr(checkpoint, name)
        if value("failed_agent_execution_id") != request.agent_execution_id:
            raise ValueError("Recovery checkpoint Agent execution mismatch")
        if value("failed_node") != node.agent_id:
            raise ValueError("Recovery checkpoint node mismatch")
        if value("artifact_hash") != node.artifact_hash:
            raise ValueError("Recovery checkpoint Artifact hash mismatch")
        return checkpoint

    def _emit(
        self, event_type, request, node, *, attempt_id=None, failure_id=None,
        retry_number=None, recovery_action=None, status,
    ):
        event = RuntimeEvent(
            event_type=event_type,
            execution_id=request.execution_id,
            trace_id=request.trace_id,
            agent_id=node.agent_id,
            agent_version=self.result_mapper._artifact_version(node.artifact_id),
            artifact_id=node.artifact_id,
            artifact_hash=node.artifact_hash,
            backend_type="multi_agent",
            status=status,
            parent_agent_id=request.parent_agent,
            agent_execution_id=request.agent_execution_id,
            invocation_id=request.invocation_id,
            attempt_id=attempt_id,
            failure_id=failure_id,
            retry_number=retry_number,
            recovery_action=recovery_action,
        )
        if self.event_store is not None:
            self.event_store.append(event)
        if self.event_bus is not None:
            self.event_bus.publish(event)
        return event
