from app.runtime.governance.events import RuntimeEvent
from .models import ExecutionRecord, ExecutionStatus


class ExecutionManager:
    def __init__(self, store, checkpoint_store=None, event_bus=None, event_store=None,
                 artifact_resolver=None):
        self.store = store
        self.checkpoint_store = checkpoint_store
        self.event_bus = event_bus
        self.event_store = event_store
        self.artifact_resolver = artifact_resolver

    def create(self, state, artifact):
        record = ExecutionRecord(
            execution_id=state.execution_id or state.task_id,
            trace_id=state.trace_id, agent_id=state.agent_id,
            agent_version=state.agent_version, artifact_id=artifact.artifact_id,
            artifact_hash=artifact.artifact_hash, backend_type=artifact.backend_type,
            user_id=state.user_id, tenant_id=state.tenant_id,
        )
        self.store.create(record)
        self._emit(record, "execution.created", "created")
        return record

    def transition(self, execution_id, status, current_node=None):
        record = self.store.update_status(execution_id, status, current_node)
        event_name = {
            ExecutionStatus.RUNNING: "execution.started",
            ExecutionStatus.WAITING_APPROVAL: "execution.waiting",
            ExecutionStatus.WAITING_TOOL: "execution.waiting",
            ExecutionStatus.RESUMING: "execution.resumed",
            ExecutionStatus.COMPLETED: "execution.completed",
            ExecutionStatus.FAILED: "execution.failed",
            ExecutionStatus.CANCELLED: "execution.cancelled",
        }.get(record.status)
        if event_name:
            self._emit(record, event_name, record.status.value)
        return record

    def save_checkpoint(self, execution_id, state, current_node=None, pending_action=None):
        if self.checkpoint_store is None:
            return None
        checkpoint = self.checkpoint_store.save_checkpoint(
            execution_id, state, current_node=current_node,
            pending_action=pending_action,
            artifact_hash=self.store.get(execution_id).artifact_hash,
        )
        record = self.store.get(execution_id)
        if record:
            self._emit(record, "checkpoint.created", "created", {"node": current_node})
        return checkpoint

    def resume(self, execution_id, approval_result, runner):
        record = self.store.get(execution_id)
        if record is None:
            raise KeyError(execution_id)
        if record.status not in {ExecutionStatus.WAITING_APPROVAL, ExecutionStatus.FAILED}:
            raise ValueError(f"Execution is not resumable: {record.status.value}")
        self.transition(execution_id, ExecutionStatus.RESUMING)
        if self.checkpoint_store is not None:
            checkpoint = self.checkpoint_store.load_checkpoint(execution_id)
            if checkpoint is None:
                raise KeyError(f"Checkpoint not found: {execution_id}")
            checkpoint_hash = (
                checkpoint.get("artifact_hash")
                if isinstance(checkpoint, dict)
                else checkpoint.artifact_hash
            )
            if checkpoint_hash != record.artifact_hash:
                raise ValueError("Checkpoint artifact hash does not match execution")
            self._emit(record, "checkpoint.restored", "restored")
        self._emit(record, "execution.resumed", "resuming")
        artifact = (
            self.artifact_resolver.get_by_hash(record.artifact_hash)
            if self.artifact_resolver is not None else None
        )
        try:
            return (
                runner(checkpoint, approval_result, artifact)
                if artifact is not None else runner(checkpoint, approval_result)
            )
        except Exception:
            self.transition(execution_id, ExecutionStatus.FAILED)
            raise

    def _emit(self, record, event_type, status, payload=None):
        event = RuntimeEvent(
            event_type=event_type, execution_id=record.execution_id,
            trace_id=record.trace_id, agent_id=record.agent_id,
            agent_version=record.agent_version, artifact_id=record.artifact_id,
            artifact_hash=record.artifact_hash, backend_type=record.backend_type,
            status=status, payload=dict(payload or {}),
        )
        if self.event_store is not None:
            self.event_store.append(event)
        if self.event_bus is not None:
            self.event_bus.publish(event)
        return event
