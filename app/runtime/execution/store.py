from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
import json
from threading import RLock

from app.storage.exceptions import NotFoundError, PersistenceError
from .models import ExecutionRecord, ExecutionStatus


class ExecutionStore(ABC):
    @abstractmethod
    def create(self, record): ...

    @abstractmethod
    def get(self, execution_id): ...

    @abstractmethod
    def update_status(self, execution_id, status, current_node=None,
                      authorization_id=None): ...

    @abstractmethod
    def list_history(self, execution_id): ...


class InMemoryExecutionStore(ExecutionStore):
    """Test provider only; production wiring must inject PostgreSQL."""

    def __init__(self):
        self._records = {}
        self._history = {}
        self._lock = RLock()

    def create(self, record):
        with self._lock:
            if record.execution_id in self._records:
                raise ValueError(f"Execution already exists: {record.execution_id}")
            self._records[record.execution_id] = deepcopy(record)
            self._history[record.execution_id] = [deepcopy(record)]
            return deepcopy(record)

    def get(self, execution_id):
        with self._lock:
            record = self._records.get(execution_id)
            return deepcopy(record) if record is not None else None

    def update_status(self, execution_id, status, current_node=None,
                      authorization_id=None):
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                raise NotFoundError(execution_id)
            updated = record.transition(status, current_node, authorization_id)
            self._records[execution_id] = updated
            self._history[execution_id].append(deepcopy(updated))
            return deepcopy(updated)

    def list_history(self, execution_id):
        with self._lock:
            return tuple(deepcopy(self._history.get(execution_id, ())))


class PostgresExecutionStore(ExecutionStore):
    """PostgreSQL provider for the execution lifecycle boundary."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS executions (
      execution_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL,
      agent_id TEXT NOT NULL, agent_version TEXT NOT NULL,
      artifact_id TEXT NOT NULL, artifact_hash TEXT NOT NULL,
      backend_type TEXT NOT NULL, user_id TEXT, tenant_id TEXT NOT NULL,
      status TEXT NOT NULL, current_node TEXT,
      authorization_id TEXT,
      deployment_version TEXT NOT NULL DEFAULT 'unmanaged',
      runtime_policy_version TEXT NOT NULL DEFAULT 'unmanaged',
      quota_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
    );
    CREATE TABLE IF NOT EXISTS execution_history (
      id BIGSERIAL PRIMARY KEY, execution_id TEXT NOT NULL,
      status TEXT NOT NULL, current_node TEXT,
      authorization_id TEXT,
      deployment_version TEXT NOT NULL DEFAULT 'unmanaged',
      runtime_policy_version TEXT NOT NULL DEFAULT 'unmanaged',
      quota_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
      recorded_at TIMESTAMPTZ NOT NULL
    );
    ALTER TABLE executions ADD COLUMN IF NOT EXISTS authorization_id TEXT;
    ALTER TABLE execution_history ADD COLUMN IF NOT EXISTS authorization_id TEXT;
    ALTER TABLE executions ADD COLUMN IF NOT EXISTS deployment_version TEXT NOT NULL DEFAULT 'unmanaged';
    ALTER TABLE executions ADD COLUMN IF NOT EXISTS runtime_policy_version TEXT NOT NULL DEFAULT 'unmanaged';
    ALTER TABLE executions ADD COLUMN IF NOT EXISTS quota_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
    ALTER TABLE execution_history ADD COLUMN IF NOT EXISTS deployment_version TEXT NOT NULL DEFAULT 'unmanaged';
    ALTER TABLE execution_history ADD COLUMN IF NOT EXISTS runtime_policy_version TEXT NOT NULL DEFAULT 'unmanaged';
    ALTER TABLE execution_history ADD COLUMN IF NOT EXISTS quota_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
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

    def create(self, record):
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO executions(execution_id,trace_id,agent_id,agent_version,artifact_id,artifact_hash,backend_type,user_id,tenant_id,status,current_node,authorization_id,deployment_version,runtime_policy_version,quota_snapshot,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                        (record.execution_id, record.trace_id, record.agent_id,
                         record.agent_version, record.artifact_id, record.artifact_hash,
                         record.backend_type, record.user_id, record.tenant_id,
                         record.status.value, record.current_node,
                         record.authorization_id,
                         record.deployment_version, record.runtime_policy_version,
                         json.dumps(record.quota_snapshot),
                         record.created_at, record.updated_at),
                    )
                    cursor.execute(
                        "INSERT INTO execution_history(execution_id,status,current_node,authorization_id,deployment_version,runtime_policy_version,quota_snapshot,recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                        (record.execution_id, record.status.value, record.current_node,
                         record.authorization_id, record.deployment_version,
                         record.runtime_policy_version,
                         json.dumps(record.quota_snapshot), record.updated_at),
                    )
            return record
        except Exception as error:
            raise PersistenceError(str(error)) from error

    def get(self, execution_id):
        row = self._fetchone(
            "SELECT execution_id,trace_id,agent_id,agent_version,artifact_id,artifact_hash,backend_type,user_id,tenant_id,status,current_node,authorization_id,deployment_version,runtime_policy_version,quota_snapshot,created_at,updated_at FROM executions WHERE execution_id=%s",
            (execution_id,),
        )
        return self._record(row) if row else None

    def update_status(self, execution_id, status, current_node=None,
                      authorization_id=None):
        current = self.get(execution_id)
        if current is None:
            raise NotFoundError(execution_id)
        updated = current.transition(status, current_node, authorization_id)
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE executions SET status=%s,current_node=%s,authorization_id=%s,deployment_version=%s,runtime_policy_version=%s,quota_snapshot=%s::jsonb,updated_at=%s WHERE execution_id=%s",
                        (updated.status.value, updated.current_node,
                         updated.authorization_id, updated.deployment_version,
                         updated.runtime_policy_version,
                         json.dumps(updated.quota_snapshot), updated.updated_at,
                         execution_id),
                    )
                    cursor.execute(
                        "INSERT INTO execution_history(execution_id,status,current_node,authorization_id,deployment_version,runtime_policy_version,quota_snapshot,recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                        (execution_id, updated.status.value, updated.current_node,
                         updated.authorization_id, updated.deployment_version,
                         updated.runtime_policy_version,
                         json.dumps(updated.quota_snapshot), updated.updated_at),
                    )
            return updated
        except Exception as error:
            raise PersistenceError(str(error)) from error

    def list_history(self, execution_id):
        current = self.get(execution_id)
        if current is None:
            return ()
        rows = self._fetchall(
            "SELECT status,current_node,authorization_id,deployment_version,runtime_policy_version,quota_snapshot,recorded_at FROM execution_history WHERE execution_id=%s ORDER BY recorded_at",
            (execution_id,),
        )
        return tuple(
            ExecutionRecord(
                execution_id=current.execution_id, trace_id=current.trace_id,
                agent_id=current.agent_id, agent_version=current.agent_version,
                artifact_id=current.artifact_id, artifact_hash=current.artifact_hash,
                backend_type=current.backend_type, user_id=current.user_id,
                tenant_id=current.tenant_id, status=ExecutionStatus(row[0]),
                current_node=row[1], created_at=current.created_at,
                authorization_id=row[2], deployment_version=row[3],
                runtime_policy_version=row[4],
                quota_snapshot=self._json_value(row[5]), updated_at=row[6],
            )
            for row in rows
        )

    def _fetchone(self, sql, params):
        rows = self._fetchall(sql, params)
        return rows[0] if rows else None

    def _fetchall(self, sql, params):
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    return cursor.fetchall()
        except Exception as error:
            raise PersistenceError(str(error)) from error

    @staticmethod
    def _record(row):
        return ExecutionRecord(
            execution_id=row[0], trace_id=row[1], agent_id=row[2],
            agent_version=row[3], artifact_id=row[4], artifact_hash=row[5],
            backend_type=row[6], user_id=row[7], tenant_id=row[8],
            status=ExecutionStatus(row[9]), current_node=row[10],
            authorization_id=row[11], deployment_version=row[12],
            runtime_policy_version=row[13],
            quota_snapshot=PostgresExecutionStore._json_value(row[14]),
            created_at=row[15], updated_at=row[16],
        )

    @staticmethod
    def _json_value(value):
        return json.loads(value) if isinstance(value, str) else dict(value or {})
