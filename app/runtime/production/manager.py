from dataclasses import replace
from threading import RLock

from .models import (
    AgentHealthStatus,
    DeadLetterRecord,
    EventDeliveryRecord,
    EventDeliveryStatus,
    ProductionExecutionPermit,
    QuotaUsage,
    utc_now,
)


class EventDeliveryManager:
    """Persist-first, failure-isolated RuntimeEvent consumer delivery."""

    def __init__(self, event_store, consumers=(), max_attempts=3):
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.event_store = event_store
        self.max_attempts = max_attempts
        self._consumers = {}
        self._deliveries = {}
        self._dead_letters = []
        self._lock = RLock()
        for consumer in consumers:
            self.register(consumer)

    def register(self, consumer, consumer_id=None):
        if not callable(getattr(consumer, "handle", None)):
            raise TypeError("consumer must provide handle(event)")
        identity = consumer_id or getattr(
            consumer, "consumer_id", consumer.__class__.__name__
        )
        if not identity:
            raise ValueError("consumer_id is required")
        if identity in self._consumers:
            raise ValueError(f"Consumer already registered: {identity}")
        self._consumers[identity] = consumer
        return consumer

    def publish(self, event):
        """Persist an event once, then independently deliver to every consumer."""
        self.event_store.append(event)
        return tuple(
            self._deliver(event, consumer_id, consumer)
            for consumer_id, consumer in tuple(self._consumers.items())
        )

    def get_delivery(self, event_id, consumer_id):
        return self._deliveries.get((event_id, consumer_id))

    def list_dead_letters(self):
        return tuple(self._dead_letters)

    def _deliver(self, event, consumer_id, consumer):
        key = (event.event_id, consumer_id)
        record = EventDeliveryRecord(event.event_id, consumer_id)
        with self._lock:
            self._deliveries[key] = record
        while record.attempts < self.max_attempts:
            attempt = record.attempts + 1
            try:
                consumer.handle(event)
            except Exception as error:
                record = replace(
                    record,
                    status=EventDeliveryStatus.FAILED,
                    attempts=attempt,
                    last_error=self._safe_error(error),
                    updated_at=utc_now(),
                )
                with self._lock:
                    self._deliveries[key] = record
                continue
            record = replace(
                record,
                status=EventDeliveryStatus.DELIVERED,
                attempts=attempt,
                last_error=None,
                updated_at=utc_now(),
            )
            with self._lock:
                self._deliveries[key] = record
            return record

        record = replace(
            record,
            status=EventDeliveryStatus.DEAD_LETTER,
            updated_at=utc_now(),
        )
        dead_letter = DeadLetterRecord(
            event=event,
            consumer_id=consumer_id,
            attempts=record.attempts,
            error=record.last_error or "consumer delivery failed",
        )
        with self._lock:
            self._deliveries[key] = record
            self._dead_letters.append(dead_letter)
        return record

    @staticmethod
    def _safe_error(error):
        value = str(error)[:256]
        if any(name in value.lower() for name in ("password", "secret", "token", "api_key")):
            return "redacted consumer failure"
        return value


class ProductionRuntimeManager:
    """Control-plane preflight; it never executes Agents or Runtime backends."""

    def __init__(self, lifecycle, deployments, capacity, health):
        self.lifecycle = lifecycle
        self.deployments = deployments
        self.capacity = capacity
        self.health = health

    def prepare_new_execution(
        self,
        *,
        agent_id,
        execution_id,
        routing_key,
        required_tools=(),
        expected_usage=None,
    ) -> ProductionExecutionPermit:
        self.lifecycle.assert_new_execution_allowed(agent_id)
        binding = self.deployments.select(agent_id, routing_key)
        report = self.health.check(agent_id, binding, required_tools)
        if report.status is AgentHealthStatus.UNAVAILABLE:
            raise RuntimeError(
                f"Agent Runtime is unavailable: {','.join(report.reasons)}"
            )
        decision = self.capacity.acquire(
            agent_id, execution_id, expected_usage or QuotaUsage()
        )
        if not decision.allowed:
            raise RuntimeError(f"Agent execution rejected by quota: {decision.reason}")
        return ProductionExecutionPermit(
            agent_id=agent_id,
            artifact=binding,
            quota_decision=decision,
            runtime_health=report,
            runtime_policy_version=decision.quota_snapshot["policy_version"],
        )

    def complete_execution(self, agent_id, execution_id, usage=None):
        try:
            return self.capacity.check_usage(agent_id, usage or QuotaUsage())
        finally:
            self.capacity.release(agent_id, execution_id)

    def assert_resume_allowed(self, agent_id, artifact_id, artifact_hash):
        self.lifecycle.assert_resume_allowed(agent_id)
        artifact = self.deployments.artifact_repository.get(artifact_id)
        if artifact is None or getattr(artifact, "artifact_hash", None) != artifact_hash:
            raise ValueError("Existing execution artifact identity is unavailable")
        return artifact
