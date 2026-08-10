from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
from threading import RLock

from app.storage.exceptions import NotFoundError, PersistenceError
from .models import ExecutionRecord, ExecutionStatus


class ExecutionStore(ABC):
    @abstractmethod
    def create(self, record): ...

    @abstractmethod
    def get(self, execution_id): ...

    @abstractmethod
    def update_status(self, execution_id, status, current_node=None): ...

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

    def update_status(self, execution_id, status, current_node=None):
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                raise NotFoundError(execution_id)
            updated = record.transition(status, current_node)
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
      artifact_id TEXT NOT NULL, user_id TEXT, tenant_id TEXT NOT NULL,
      status TEXT NOT NULL, current_node TEXT,
      created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
    );
    CREATE TABLE IF NOT EXISTS execution_history (
      id BIGSERIAL PRIMARY KEY, execution_id TEXT NOT NULL,
      status TEXT NOT NULL, current_node TEXT,
      recorded_at TIMESTAMPTZ NOT NULL
    );
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
                        "INSERT INTO executions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (record.execution_id, record.trace_id, record.agent_id,
                         record.agent_version, record.artifact_id, record.user_id,
                         record.tenant_id, record.status.value, record.current_node,
                         record.created_at, record.updated_at),
                    )
                    cursor.execute(
                        "INSERT INTO execution_history(execution_id,status,current_node,recorded_at) VALUES (%s,%s,%s,%s)",
                        (record.execution_id, record.status.value, record.current_node, record.updated_at),
                    )
            return record
        except Exception as error:
            raise PersistenceError(str(error)) from error

    def get(self, execution_id):
        row = self._fetchone(
            "SELECT execution_id,trace_id,agent_id,agent_version,artifact_id,user_id,tenant_id,status,current_node,created_at,updated_at FROM executions WHERE execution_id=%s",
            (execution_id,),
        )
        return self._record(row) if row else None

    def update_status(self, execution_id, status, current_node=None):
        current = self.get(execution_id)
        if current is None:
            raise NotFoundError(execution_id)
        updated = current.transition(status, current_node)
        try:
            with self.connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE executions SET status=%s,current_node=%s,updated_at=%s WHERE execution_id=%s",
                        (updated.status.value, updated.current_node, updated.updated_at, execution_id),
                    )
                    cursor.execute(
                        "INSERT INTO execution_history(execution_id,status,current_node,recorded_at) VALUES (%s,%s,%s,%s)",
                        (execution_id, updated.status.value, updated.current_node, updated.updated_at),
                    )
            return updated
        except Exception as error:
            raise PersistenceError(str(error)) from error

    def list_history(self, execution_id):
        current = self.get(execution_id)
        if current is None:
            return ()
        rows = self._fetchall(
            "SELECT status,current_node,recorded_at FROM execution_history WHERE execution_id=%s ORDER BY recorded_at",
            (execution_id,),
        )
        return tuple(
            ExecutionRecord(
                execution_id=current.execution_id, trace_id=current.trace_id,
                agent_id=current.agent_id, agent_version=current.agent_version,
                artifact_id=current.artifact_id, user_id=current.user_id,
                tenant_id=current.tenant_id, status=ExecutionStatus(row[0]),
                current_node=row[1], created_at=current.created_at,
                updated_at=row[2],
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
        values = list(row)
        if isinstance(values[7], str):
            values[7] = ExecutionStatus(values[7])
        return ExecutionRecord(*values)
