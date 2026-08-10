from copy import deepcopy
from dataclasses import dataclass
import json

from app.storage.exceptions import NotFoundError, PersistenceError


@dataclass(frozen=True)
class ExecutionCheckpoint:
    execution_id: str
    graph_state: dict
    current_node: str | None = None
    pending_action: dict | None = None
    approval_id: str | None = None
    artifact_hash: str | None = None


class InMemoryExecutionCheckpointStore:
    """Governance-owned execution checkpoint; independent from Memory storage."""

    def __init__(self):
        self._items = {}

    def save(self, checkpoint: ExecutionCheckpoint):
        self._items[checkpoint.execution_id] = deepcopy(checkpoint)

    def save_checkpoint(self, execution_id, graph_state, current_node=None,
                        pending_action=None, artifact_hash=None):
        checkpoint = ExecutionCheckpoint(
            execution_id=execution_id,
            graph_state=(graph_state.to_dict() if hasattr(graph_state, "to_dict") else dict(graph_state)),
            current_node=current_node,
            pending_action=pending_action,
            artifact_hash=artifact_hash,
        )
        self.save(checkpoint)
        return deepcopy(checkpoint)

    def load(self, execution_id: str):
        item = self._items.get(execution_id)
        return deepcopy(item) if item is not None else None

    def load_checkpoint(self, execution_id):
        return self.load(execution_id)

    def delete(self, execution_id: str):
        self._items.pop(execution_id, None)


class PersistentCheckpointStore:
    """PostgreSQL checkpoint provider for durable execution."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS execution_checkpoints (
      id BIGSERIAL PRIMARY KEY,
      execution_id TEXT NOT NULL,
      checkpoint_data JSONB NOT NULL,
      node TEXT,
      pending_action JSONB,
      artifact_hash TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS execution_checkpoints_execution_idx
      ON execution_checkpoints(execution_id, created_at DESC);
    ALTER TABLE execution_checkpoints
      ADD COLUMN IF NOT EXISTS artifact_hash TEXT;
    """

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def initialize_schema(self):
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    for statement in self.SCHEMA.split(";"):
                        if statement.strip():
                            cursor.execute(statement)
        except Exception as error:
            raise PersistenceError(str(error)) from error

    def save_checkpoint(self, execution_id, graph_state, current_node=None,
                        pending_action=None, artifact_hash=None):
        if not execution_id:
            raise ValueError("execution_id is required")
        if not artifact_hash:
            raise ValueError("artifact_hash is required for durable checkpoint")
        payload = graph_state.to_dict() if hasattr(graph_state, "to_dict") else dict(graph_state)
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO execution_checkpoints(execution_id,checkpoint_data,node,pending_action,artifact_hash) VALUES (%s,%s,%s,%s,%s) RETURNING id,created_at",
                        (execution_id, json.dumps(payload), current_node,
                         json.dumps(pending_action) if pending_action is not None else None,
                         artifact_hash),
                    )
                    row = cursor.fetchone()
            return {"id": row[0], "execution_id": execution_id,
                    "graph_state": payload, "current_node": current_node,
                    "pending_action": pending_action,
                    "artifact_hash": artifact_hash, "created_at": row[1]}
        except Exception as error:
            raise PersistenceError(str(error)) from error

    def load_checkpoint(self, execution_id):
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id,execution_id,checkpoint_data,node,pending_action,artifact_hash,created_at FROM execution_checkpoints WHERE execution_id=%s ORDER BY created_at DESC LIMIT 1",
                        (execution_id,),
                    )
                    row = cursor.fetchone()
            if row is None:
                return None
            data = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            action = row[4] if isinstance(row[4], dict) or row[4] is None else json.loads(row[4])
            return {"id": row[0], "execution_id": row[1], "graph_state": data,
                    "current_node": row[3], "pending_action": action,
                    "artifact_hash": row[5], "created_at": row[6]}
        except Exception as error:
            raise PersistenceError(str(error)) from error

    def delete_checkpoint(self, execution_id):
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM execution_checkpoints WHERE execution_id=%s",
                        (execution_id,),
                    )
        except Exception as error:
            raise PersistenceError(str(error)) from error

    # Compatibility with the runtime CheckpointStore port.
    def save(self, execution_id, state):
        metadata = getattr(state, "metadata", {}) or {}
        return self.save_checkpoint(
            execution_id, state, getattr(state, "current_node", None),
            artifact_hash=metadata.get("artifact_hash"),
        )

    def load(self, execution_id):
        checkpoint = self.load_checkpoint(execution_id)
        return checkpoint["graph_state"] if checkpoint else None

    def delete(self, execution_id):
        self.delete_checkpoint(execution_id)
