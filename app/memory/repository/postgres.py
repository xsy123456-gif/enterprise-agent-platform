import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

from app.memory.errors import (
    ConcurrentMemoryWrite, MemoryError, MemoryInvariantViolation, MemoryStorageError,
)
from app.memory.repository.base import MemoryRepository


TABLES = {
    "memory_events",
    "memory_items",
    "memory_relations",
    "memory_access_logs",
    "memory_processing_tasks",
    "memory_outbox",
}
REQUIRED_COLUMNS = {
    "memory_events": {
        "event_id", "trace_id", "task_id", "agent_id", "user_id", "tenant_id",
        "department_id", "event_type", "input", "output", "tool_results",
        "metadata", "status", "created_at", "processed_at",
        "idempotency_key", "attempt_count", "next_attempt_at", "locked_by",
        "lease_until", "error_code", "lock_token",
    },
    "memory_items": {
        "id", "memory_key", "type", "entity_id", "attribute", "content",
        "schema_version", "embedding", "importance",
        "embedding_space_id", "embedding_provider", "embedding_model",
        "embedding_version", "embedding_dimension",
        "confidence", "source", "tenant_id", "department_id", "user_id",
        "agent_id", "version", "status", "replaces_id", "replaced_by_id",
        "observation_count", "last_observed_at", "access_count",
        "last_accessed_at", "created_at", "updated_at",
    },
    "memory_relations": {
        "id", "source_id", "target_id", "relation_type", "created_at",
    },
    "memory_access_logs": {
        "id", "memory_id", "user_id", "agent_id", "trace_id", "query", "created_at",
    },
    "memory_processing_tasks": {
        "id", "event_id", "pipeline_stage", "status", "retry_count", "error",
        "created_at", "updated_at",
    },
    "memory_outbox": {
        "id", "event_type", "aggregate_id", "payload", "status", "attempt_count",
        "available_at", "created_at", "published_at", "last_error",
        "locked_by", "lease_until", "lock_token",
    },
}
RELATION_TYPES = {"REPLACES", "DERIVED_FROM", "MERGED_FROM", "CONFLICT_WITH"}

_tx_connection: ContextVar = ContextVar("_tx_connection", default=None)


def build_schema_sql(embedding_dimension):
    if not isinstance(embedding_dimension, int) or not 1 <= embedding_dimension <= 16000:
        raise ValueError("embedding_dimension must be an integer between 1 and 16000")
    vector_type = f"vector({embedding_dimension})"
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS memory_events (
  event_id text PRIMARY KEY, trace_id text NOT NULL, task_id text NOT NULL,
  agent_id text NOT NULL, user_id text NOT NULL, tenant_id text NOT NULL,
  department_id text, event_type text NOT NULL, input jsonb NOT NULL,
  output jsonb NOT NULL, tool_results jsonb NOT NULL, metadata jsonb NOT NULL,
  status text NOT NULL, error text, idempotency_key text,
  attempt_count integer NOT NULL DEFAULT 0,
  next_attempt_at timestamptz, locked_by text, lease_until timestamptz,
  error_code text, lock_token text, created_at timestamptz NOT NULL,
  processed_at timestamptz,
  CONSTRAINT memory_events_status_check CHECK (
    status IN ('received','processing','retry_wait','processed','rejected','dead_letter')
  ),
  CONSTRAINT memory_events_attempt_check CHECK (attempt_count >= 0),
  CONSTRAINT memory_events_processing_lease_check CHECK (
    (status = 'processing'
     AND locked_by IS NOT NULL
     AND lock_token IS NOT NULL
     AND lease_until IS NOT NULL)
    OR
    (status <> 'processing'
     AND locked_by IS NULL
     AND lock_token IS NULL
     AND lease_until IS NULL)
  ),
  CONSTRAINT memory_events_retry_wait_check CHECK (
    status <> 'retry_wait' OR next_attempt_at IS NOT NULL
  ),
  CONSTRAINT memory_events_terminal_check CHECK (
    status NOT IN ('processed','rejected','dead_letter') OR processed_at IS NOT NULL
  )
);
CREATE TABLE IF NOT EXISTS memory_outbox (
  id text PRIMARY KEY, event_type text NOT NULL, aggregate_id text NOT NULL,
  payload jsonb NOT NULL, status text NOT NULL DEFAULT 'pending',
  attempt_count integer NOT NULL DEFAULT 0, available_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz,
  last_error text, locked_by text, lease_until timestamptz, lock_token text,
  CONSTRAINT memory_outbox_status_check CHECK (
    status IN ('pending','processing','published','dead_letter')
  ),
  CONSTRAINT memory_outbox_attempt_check CHECK (attempt_count >= 0)
);
CREATE TABLE IF NOT EXISTS memory_items (
  id text PRIMARY KEY, memory_key text NOT NULL, type text NOT NULL,
  entity_id text NOT NULL, attribute text NOT NULL, schema_version integer NOT NULL DEFAULT 1,
  content jsonb NOT NULL, embedding {vector_type}, importance double precision NOT NULL,
  embedding_space_id text NOT NULL DEFAULT 'legacy-unknown',
  embedding_provider text NOT NULL DEFAULT 'legacy-unknown',
  embedding_model text, embedding_version text, embedding_dimension integer,
  confidence double precision NOT NULL, source text NOT NULL, tenant_id text NOT NULL,
  department_id text, user_id text NOT NULL, agent_id text NOT NULL,
  version integer NOT NULL CHECK (version > 0),
  status text NOT NULL CHECK (status IN ('active','replaced','conflict','archived')),
  replaces_id text, replaced_by_id text,
  observation_count integer NOT NULL DEFAULT 1 CHECK (observation_count >= 1),
  last_observed_at timestamptz,
  access_count integer NOT NULL DEFAULT 0 CHECK (access_count >= 0),
  last_accessed_at timestamptz,
  created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
  CHECK (confidence >= 0 AND confidence <= 1),
  CHECK (importance >= 0 AND importance <= 1)
);
CREATE TABLE IF NOT EXISTS memory_relations (
  id bigserial PRIMARY KEY, source_id text NOT NULL, target_id text NOT NULL,
  relation_type text NOT NULL CHECK (
    relation_type IN ('REPLACES','DERIVED_FROM','MERGED_FROM','CONFLICT_WITH')
  ),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS memory_access_logs (
  id bigserial PRIMARY KEY, memory_id text NOT NULL, user_id text NOT NULL,
  agent_id text NOT NULL, trace_id text, query text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS memory_processing_tasks (
  id bigserial PRIMARY KEY, event_id text NOT NULL UNIQUE,
  pipeline_stage text NOT NULL CHECK (pipeline_stage IN (
    'EXTRACTING','EVALUATING','NORMALIZING','PRE_DEDUP',
    'RESOLVING','FINE_DEDUP','RANKING','PERSISTING'
  )),
  status text NOT NULL, retry_count integer NOT NULL DEFAULT 0,
  error text, created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- Add missing columns first (before constraint repairs that depend on them)
ALTER TABLE memory_events ADD COLUMN IF NOT EXISTS idempotency_key text;
ALTER TABLE memory_events ADD COLUMN IF NOT EXISTS attempt_count integer NOT NULL DEFAULT 0;
ALTER TABLE memory_events ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;
ALTER TABLE memory_events ADD COLUMN IF NOT EXISTS locked_by text;
ALTER TABLE memory_events ADD COLUMN IF NOT EXISTS lease_until timestamptz;
ALTER TABLE memory_events ADD COLUMN IF NOT EXISTS error_code text;
ALTER TABLE memory_events ADD COLUMN IF NOT EXISTS lock_token text;
ALTER TABLE memory_events ADD COLUMN IF NOT EXISTS processed_at timestamptz;
ALTER TABLE memory_outbox ADD COLUMN IF NOT EXISTS locked_by text;
ALTER TABLE memory_outbox ADD COLUMN IF NOT EXISTS lease_until timestamptz;
ALTER TABLE memory_outbox ADD COLUMN IF NOT EXISTS lock_token text;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS embedding_model text;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS embedding_version text;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS embedding_space_id text
  NOT NULL DEFAULT 'legacy-unknown';
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS embedding_provider text
  NOT NULL DEFAULT 'legacy-unknown';
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS entity_id text;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS attribute text;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS schema_version integer NOT NULL DEFAULT 1;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS observation_count integer NOT NULL DEFAULT 1;
ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS last_observed_at timestamptz;
-- Repair legacy rows (after columns exist)
UPDATE memory_events SET locked_by=NULL, lease_until=NULL, lock_token=NULL
  WHERE status <> 'processing'
    AND (locked_by IS NOT NULL OR lease_until IS NOT NULL OR lock_token IS NOT NULL);
UPDATE memory_events SET next_attempt_at = COALESCE(next_attempt_at, created_at)
  WHERE status = 'retry_wait' AND next_attempt_at IS NULL;
UPDATE memory_events SET processed_at = COALESCE(processed_at, created_at)
  WHERE status IN ('processed','rejected','dead_letter') AND processed_at IS NULL;
UPDATE memory_events SET attempt_count = 0 WHERE attempt_count < 0;
UPDATE memory_items SET observation_count = 1
  WHERE observation_count IS NULL OR observation_count < 1;
UPDATE memory_items SET access_count = 0
  WHERE access_count IS NULL OR access_count < 0;
-- Add constraint checks last
ALTER TABLE memory_events DROP CONSTRAINT IF EXISTS memory_events_status_check;
ALTER TABLE memory_events ADD CONSTRAINT memory_events_status_check CHECK (
  status IN ('received','processing','retry_wait','processed','rejected','dead_letter')
);
ALTER TABLE memory_events DROP CONSTRAINT IF EXISTS memory_events_attempt_check;
ALTER TABLE memory_events ADD CONSTRAINT memory_events_attempt_check CHECK (
  attempt_count >= 0
);
ALTER TABLE memory_events DROP CONSTRAINT IF EXISTS memory_events_processing_lease_check;
ALTER TABLE memory_events ADD CONSTRAINT memory_events_processing_lease_check CHECK (
  (status = 'processing'
   AND locked_by IS NOT NULL
   AND lock_token IS NOT NULL
   AND lease_until IS NOT NULL)
  OR
  (status <> 'processing'
   AND locked_by IS NULL
   AND lock_token IS NULL
   AND lease_until IS NULL)
);
ALTER TABLE memory_events DROP CONSTRAINT IF EXISTS memory_events_retry_wait_check;
ALTER TABLE memory_events ADD CONSTRAINT memory_events_retry_wait_check CHECK (
  status <> 'retry_wait' OR next_attempt_at IS NOT NULL
);
ALTER TABLE memory_events DROP CONSTRAINT IF EXISTS memory_events_terminal_check;
ALTER TABLE memory_events ADD CONSTRAINT memory_events_terminal_check CHECK (
  status NOT IN ('processed','rejected','dead_letter') OR processed_at IS NOT NULL
);
ALTER TABLE memory_items DROP CONSTRAINT IF EXISTS memory_items_obs_count_check;
ALTER TABLE memory_items ADD CONSTRAINT memory_items_obs_count_check CHECK (
  observation_count >= 1
);
ALTER TABLE memory_items DROP CONSTRAINT IF EXISTS memory_items_acc_count_check;
ALTER TABLE memory_items ADD CONSTRAINT memory_items_acc_count_check CHECK (
  access_count >= 0
);
-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS memory_events_idempotency_uidx
  ON memory_events (tenant_id, event_type, idempotency_key)
  WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS memory_events_claim_idx
  ON memory_events (status, next_attempt_at, lease_until, created_at);
CREATE INDEX IF NOT EXISTS memory_outbox_dispatch_idx
  ON memory_outbox (status, available_at, created_at);
CREATE INDEX IF NOT EXISTS memory_items_scope_active_idx
  ON memory_items (tenant_id, department_id, user_id, agent_id, status);
CREATE INDEX IF NOT EXISTS memory_events_status_idx ON memory_events (status);
CREATE INDEX IF NOT EXISTS memory_relations_source_idx
  ON memory_relations (source_id, relation_type);
CREATE INDEX IF NOT EXISTS memory_access_logs_memory_idx
  ON memory_access_logs (memory_id, created_at DESC);
ALTER TABLE memory_items DROP CONSTRAINT IF EXISTS
  memory_items_memory_key_tenant_id_user_id_agent_id_version_key;
"""


class PostgresMemoryRepository(MemoryRepository):

    def __init__(self, connection_factory, embedding_dimension):
        self.connection_factory = connection_factory
        self.embedding_dimension = embedding_dimension

    @contextmanager
    def atomic_write(self):
        token = _tx_connection.get()
        if token is not None:
            yield
            return
        try:
            with self.connection_factory() as connection:
                token = _tx_connection.set(connection)
                try:
                    yield
                finally:
                    _tx_connection.reset(token)
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryStorageError(
                f"Repository atomic write failed: {exc}"
            ) from exc

    def initialize(self):
        with self.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(build_schema_sql(self.embedding_dimension))
                self._backfill_legacy_identity(cursor)
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS memory_items_scope_identity_version_uidx "
                    "ON memory_items (tenant_id, department_id, user_id, agent_id, type, "
                    "entity_id, attribute, version) NULLS NOT DISTINCT"
                )
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS memory_items_active_head_uidx "
                    "ON memory_items (tenant_id, department_id, user_id, agent_id, type, "
                    "entity_id, attribute) NULLS NOT DISTINCT WHERE status='active'"
                )
                cursor.execute(
                    "SELECT format_type(att.atttypid,att.atttypmod) "
                    "FROM pg_attribute att "
                    "JOIN pg_class relation ON relation.oid=att.attrelid "
                    "JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace "
                    "WHERE namespace.nspname=current_schema() "
                    "AND relation.relname='memory_items' "
                    "AND att.attname='embedding'"
                )
                current_type = cursor.fetchone()[0]
                expected_type = f"vector({self.embedding_dimension})"
                if current_type != expected_type:
                    cursor.execute(
                        "SELECT count(*) FROM memory_items WHERE embedding IS NOT NULL"
                    )
                    if cursor.fetchone()[0]:
                        raise RuntimeError(
                            "Cannot change Memory embedding dimension while existing "
                            "vectors require re-embedding"
                        )
                    cursor.execute("DROP INDEX IF EXISTS memory_items_embedding_hnsw_idx")
                    cursor.execute(
                        "ALTER TABLE memory_items ALTER COLUMN embedding "
                        f"TYPE vector({self.embedding_dimension}) "
                        f"USING embedding::vector({self.embedding_dimension})"
                    )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS memory_items_embedding_hnsw_idx "
                    "ON memory_items USING hnsw (embedding vector_cosine_ops)"
                )
        return self.validate_schema()

    def healthcheck(self):
        with self.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('server_version_num')::integer")
                version = cursor.fetchone()[0]
        if version < 160000:
            raise RuntimeError("Memory database requires PostgreSQL 16 or newer")
        return version

    def validate_schema(self):
        with self.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
                extension = cursor.fetchone()
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname=current_schema()"
                )
                tables = {row[0] for row in cursor.fetchall()}
                cursor.execute(
                    "SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() "
                    "AND indexname='memory_items_embedding_hnsw_idx'"
                )
                vector_index = cursor.fetchone()
                cursor.execute(
                    "SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() "
                    "AND indexname='memory_items_active_head_uidx'"
                )
                active_head_index = cursor.fetchone()
                cursor.execute(
                    "SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() "
                    "AND indexname='memory_items_scope_identity_version_uidx'"
                )
                version_index = cursor.fetchone()
                cursor.execute(
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema=current_schema() AND table_name = ANY(%s)",
                    (list(TABLES),),
                )
                columns = {}
                for table, column in cursor.fetchall():
                    columns.setdefault(table, set()).add(column)
                cursor.execute(
                    "SELECT format_type(att.atttypid,att.atttypmod) "
                    "FROM pg_attribute att "
                    "JOIN pg_class relation ON relation.oid=att.attrelid "
                    "JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace "
                    "WHERE namespace.nspname=current_schema() "
                    "AND relation.relname='memory_items' "
                    "AND att.attname='embedding'"
                )
                vector_type = cursor.fetchone()
        missing = TABLES - tables
        if not extension:
            raise RuntimeError("pgvector extension is not enabled")
        if missing:
            raise RuntimeError(f"Memory schema is missing tables: {sorted(missing)}")
        if not vector_index:
            raise RuntimeError("Memory vector index is missing")
        if not active_head_index:
            raise RuntimeError("Memory ACTIVE head unique index is missing")
        if not version_index:
            raise RuntimeError("Memory scope identity version unique index is missing")
        missing_columns = {
            table: sorted(required - columns.get(table, set()))
            for table, required in REQUIRED_COLUMNS.items()
            if required - columns.get(table, set())
        }
        if missing_columns:
            raise RuntimeError(
                f"Memory schema is missing required columns: {missing_columns}"
            )
        expected_vector_type = f"vector({self.embedding_dimension})"
        actual_vector_type = vector_type[0] if vector_type else None
        if actual_vector_type != expected_vector_type:
            raise RuntimeError(
                "Memory embedding dimension mismatch: "
                f"database={actual_vector_type}, configured={expected_vector_type}"
            )
        return {
            "pgvector_version": extension[0],
            "tables": tables,
            "vector_index": vector_index[0],
            "active_head_index": active_head_index[0],
            "version_index": version_index[0],
            "embedding_dimension": self.embedding_dimension,
            "vector_type": actual_vector_type,
        }

    @staticmethod
    def _parse_legacy_identity(memory_key, type_id):
        parts = memory_key.split(":") if isinstance(memory_key, str) else []
        if len(parts) != 3 or not all(parts) or parts[0] != type_id:
            raise RuntimeError(
                "Cannot safely backfill Memory identity: "
                f"memory_key={memory_key!r}, type={type_id!r}"
            )
        return parts[1], parts[2]

    def _backfill_legacy_identity(self, cursor):
        cursor.execute(
            "SELECT id, memory_key, type, entity_id, attribute "
            "FROM memory_items ORDER BY id"
        )
        rows = cursor.fetchall()
        for item_id, memory_key, type_id, entity_id, attribute in rows:
            if (entity_id is None) != (attribute is None):
                raise RuntimeError(
                    "Cannot safely backfill Memory identity: partial identity "
                    f"for id={item_id!r}"
                )
            if entity_id is None:
                entity_id, attribute = self._parse_legacy_identity(memory_key, type_id)
                cursor.execute(
                    "UPDATE memory_items SET entity_id=%s, attribute=%s WHERE id=%s",
                    (entity_id, attribute, item_id),
                )
            expected_key = f"{type_id}:{entity_id}:{attribute}"
            if memory_key != expected_key:
                raise RuntimeError(
                    "Memory identity does not match memory_key: "
                    f"id={item_id!r}, memory_key={memory_key!r}, "
                    f"expected={expected_key!r}"
                )
        cursor.execute("ALTER TABLE memory_items ALTER COLUMN entity_id SET NOT NULL")
        cursor.execute("ALTER TABLE memory_items ALTER COLUMN attribute SET NOT NULL")

    # ── Inbox Events ──────────────────────────────────────────────

    def save_event(self, event):
        sql = """INSERT INTO memory_events
        (event_id,trace_id,task_id,agent_id,user_id,tenant_id,department_id,
         event_type,input,output,tool_results,metadata,status,error,idempotency_key,
         attempt_count,next_attempt_at,locked_by,lease_until,error_code,lock_token,
         created_at,processed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (tenant_id,event_type,idempotency_key) WHERE idempotency_key IS NOT NULL
        DO UPDATE SET event_id=memory_events.event_id
        RETURNING event_id"""
        values = (
            event.event_id, event.trace_id, event.task_id, event.agent_id,
            event.user_id, event.tenant_id, event.department_id, event.source_kind,
            json.dumps({}), json.dumps({}), json.dumps([]),
            json.dumps(event.storage_metadata()), event.status,
            event.error, event.idempotency_key, event.attempt_count,
            event.next_attempt_at, event.locked_by, event.lease_until,
            event.error_code, getattr(event, "lock_token", None),
            event.created_at, event.processed_at,
        )
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                event_id = cursor.fetchone()[0]
        return event if event_id == event.event_id else self.get_event(event_id)

    def get_event(self, event_id):
        return self._fetch_object(
            "SELECT * FROM memory_events WHERE event_id=%s", (event_id,), "event"
        )

    def update_event(self, event):
        import warnings
        warnings.warn(
            "update_event is deprecated without fencing; use commit_event_result",
            DeprecationWarning, stacklevel=2,
        )
        self._execute(
            "UPDATE memory_events SET status=%s,error=%s,error_code=%s,attempt_count=%s,"
            "next_attempt_at=%s,locked_by=%s,lease_until=%s,lock_token=%s,"
            "processed_at=%s WHERE event_id=%s",
            (event.status, event.error, event.error_code, event.attempt_count,
             event.next_attempt_at, event.locked_by, event.lease_until,
             getattr(event, "lock_token", None), event.processed_at, event.event_id),
        )
        return event

    def claim_events(self, worker_id, limit, lease_seconds):
        lock_token = str(uuid.uuid4())
        sql = """WITH candidates AS (
          SELECT event_id FROM memory_events
          WHERE (status IN ('received','retry_wait') AND
                 (next_attempt_at IS NULL OR next_attempt_at <= now()))
             OR (status='processing' AND lease_until < now())
          ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT %s
        ) UPDATE memory_events event SET status='processing', locked_by=%s,
          lease_until=now() + (%s * interval '1 second'), lock_token=%s,
          attempt_count=event.attempt_count + 1
        FROM candidates WHERE event.event_id=candidates.event_id RETURNING event.*"""
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (limit, worker_id, lease_seconds, lock_token))
                columns = [item.name for item in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return [self._hydrate(row, "event") for row in rows]

    def renew_lease(self, event_id, worker_id, lock_token, lease_seconds):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_events SET lease_until=now() + (%s * interval '1 second') "
                    "WHERE event_id=%s AND status='processing' "
                    "AND locked_by=%s AND lock_token=%s AND lease_until > now()",
                    (lease_seconds, event_id, worker_id, lock_token),
                )
                return cursor.rowcount > 0

    def commit_event_result(self, event, worker_id, domain_events, lock_token):
        status = event.status
        base_sql = """UPDATE memory_events SET {set_clause}
            WHERE event_id=%s AND status='processing'
            AND locked_by=%s AND lock_token=%s AND lease_until > now()"""
        if status == "processed":
            set_clause = (
                "status='processed', processed_at=%s, "
                "error=NULL, error_code=NULL, next_attempt_at=NULL, "
                "locked_by=NULL, lease_until=NULL, lock_token=NULL"
            )
            params = (event.processed_at, event.event_id, worker_id, lock_token)
        elif status == "retry_wait":
            set_clause = (
                "status='retry_wait', next_attempt_at=%s, error=%s, error_code=%s, "
                "locked_by=NULL, lease_until=NULL, lock_token=NULL"
            )
            params = (event.next_attempt_at, event.error, event.error_code,
                      event.event_id, worker_id, lock_token)
        else:
            set_clause = (
                "status=%s, processed_at=%s, error=%s, error_code=%s, "
                "locked_by=NULL, lease_until=NULL, lock_token=NULL"
            )
            params = (status, event.processed_at, event.error, event.error_code,
                      event.event_id, worker_id, lock_token)
        sql = base_sql.format(set_clause=set_clause)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                if cursor.rowcount != 1:
                    raise ConcurrentMemoryWrite(
                        "Event result rejected: ownership lost "
                        "(lock_token mismatch, wrong worker, or lease expired)"
                    )
                for domain_event in domain_events:
                    cursor.execute(
                        "INSERT INTO memory_outbox (id,event_type,aggregate_id,payload) "
                        "VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT (id) DO NOTHING",
                        (domain_event.event_id, domain_event.event_type,
                         domain_event.aggregate_id, json.dumps(domain_event.payload)),
                    )

    def finalize_event(self, event, domain_events):
        import warnings
        warnings.warn(
            "finalize_event is deprecated; use commit_event_result for fenced inbox writes",
            DeprecationWarning, stacklevel=2,
        )
        lock_token = getattr(event, "lock_token", None)
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                if lock_token:
                    cursor.execute(
                        "UPDATE memory_events SET status=%s,processed_at=%s,locked_by=NULL,"
                        "lease_until=NULL,lock_token=NULL,error=NULL,error_code=NULL "
                        "WHERE event_id=%s AND status='processing' AND lock_token=%s",
                        (event.status, event.processed_at, event.event_id, lock_token),
                    )
                    if cursor.rowcount != 1:
                        raise ConcurrentMemoryWrite(
                            "Event finalization rejected: lock_token mismatch"
                        )
                else:
                    cursor.execute(
                        "UPDATE memory_events SET status=%s,processed_at=%s,locked_by=NULL,"
                        "lease_until=NULL,lock_token=NULL,error=NULL,error_code=NULL "
                        "WHERE event_id=%s",
                        (event.status, event.processed_at, event.event_id),
                    )
                for domain_event in domain_events:
                    cursor.execute(
                        "INSERT INTO memory_outbox (id,event_type,aggregate_id,payload) "
                        "VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT (id) DO NOTHING",
                        (domain_event.event_id, domain_event.event_type,
                         domain_event.aggregate_id, json.dumps(domain_event.payload)),
                    )

    # ── Outbox ─────────────────────────────────────────────────────

    def add_outbox(self, event):
        self._execute(
            "INSERT INTO memory_outbox (id,event_type,aggregate_id,payload) "
            "VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT (id) DO NOTHING",
            (event.event_id, event.event_type, event.aggregate_id,
             json.dumps(event.payload)),
        )

    def claim_outbox(self, limit, worker_id, lease_seconds=30):
        lock_token = str(uuid.uuid4())
        sql = """WITH candidates AS (
          SELECT id FROM memory_outbox
          WHERE
            (status='pending' AND available_at <= now())
            OR (status='processing' AND lease_until < now())
          ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT %s
        ) UPDATE memory_outbox SET status='processing', locked_by=%s,
          lock_token=%s, lease_until=now() + (%s * interval '1 second'),
          attempt_count=attempt_count + 1
        FROM candidates WHERE memory_outbox.id=candidates.id
        RETURNING memory_outbox.*"""
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (limit, worker_id, lock_token, lease_seconds))
                columns = [item.name for item in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def mark_outbox_published(self, outbox_id, worker_id, lock_token):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_outbox SET status='published',published_at=now(),"
                    "locked_by=NULL,lease_until=NULL,lock_token=NULL "
                    "WHERE id=%s AND status='processing' "
                    "AND locked_by=%s AND lock_token=%s AND lease_until > now()",
                    (outbox_id, worker_id, lock_token),
                )
                if cursor.rowcount != 1:
                    raise ConcurrentMemoryWrite("Outbox CAS mark_published: ownership lost")
                return True

    def retry_outbox(self, outbox_id, error, next_attempt_at, worker_id, lock_token):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_outbox SET status='pending',"
                    "last_error=%s,available_at=%s,locked_by=NULL,lease_until=NULL,lock_token=NULL "
                    "WHERE id=%s AND status='processing' "
                    "AND locked_by=%s AND lock_token=%s AND lease_until > now()",
                    (error, next_attempt_at, outbox_id, worker_id, lock_token),
                )
                if cursor.rowcount != 1:
                    raise ConcurrentMemoryWrite("Outbox CAS retry: ownership lost")
                return True

    def dead_letter_outbox(self, outbox_id, error, worker_id, lock_token):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_outbox SET status='dead_letter',last_error=%s,"
                    "locked_by=NULL,lease_until=NULL,lock_token=NULL "
                    "WHERE id=%s AND status='processing' "
                    "AND locked_by=%s AND lock_token=%s AND lease_until > now()",
                    (error, outbox_id, worker_id, lock_token),
                )
                if cursor.rowcount != 1:
                    raise ConcurrentMemoryWrite("Outbox CAS dead_letter: ownership lost")
                return True

    # ── Memory Items ──────────────────────────────────────────────

    def create_item(self, item, relations=None):
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._write_item(cursor, item, relations)
        return item

    def commit_resolution(self, item, expected_active_head_id, relations=None):
        lock_key = json.dumps([
            item.tenant_id, item.department_id, item.user_id, item.agent_id,
            item.type, item.entity_id, item.attribute,
        ], ensure_ascii=False, separators=(",", ":"))
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (lock_key,),
                )
                cursor.execute(
                    "SELECT id FROM memory_items WHERE tenant_id=%s "
                    "AND department_id IS NOT DISTINCT FROM %s AND user_id=%s "
                    "AND agent_id=%s AND type=%s AND entity_id=%s "
                    "AND attribute=%s AND status='active' FOR UPDATE",
                    (
                        item.tenant_id, item.department_id, item.user_id,
                        item.agent_id, item.type, item.entity_id, item.attribute,
                    ),
                )
                active_rows = cursor.fetchall()
                if len(active_rows) > 1:
                    raise MemoryInvariantViolation(
                        "Memory scope and identity have multiple ACTIVE heads"
                    )
                current_active_id = active_rows[0][0] if active_rows else None
                if current_active_id != expected_active_head_id:
                    raise ConcurrentMemoryWrite(
                        "ACTIVE head changed while committing Memory"
                    )
                cursor.execute(
                    "SELECT COALESCE(MAX(version),0) FROM memory_items "
                    "WHERE tenant_id=%s AND department_id IS NOT DISTINCT FROM %s "
                    "AND user_id=%s AND agent_id=%s AND type=%s "
                    "AND entity_id=%s AND attribute=%s",
                    (
                        item.tenant_id, item.department_id, item.user_id,
                        item.agent_id, item.type, item.entity_id, item.attribute,
                    ),
                )
                item.version = int(cursor.fetchone()[0]) + 1
                self._write_item(cursor, item, relations)
        return item

    def merge_observation(self, item, evaluation):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_items SET observation_count=observation_count+1, "
                    "last_observed_at=now(), updated_at=now(), "
                    "confidence=GREATEST(confidence, %s), "
                    "importance=GREATEST(importance, %s) "
                    "WHERE id=%s AND status='active'",
                    (evaluation.confidence, evaluation.importance, item.id),
                )
                if cursor.rowcount != 1:
                    raise ConcurrentMemoryWrite(
                        "Could not merge observation: item is no longer ACTIVE"
                    )
        return item

    def get_item(self, memory_id):
        return self._fetch_object(
            "SELECT * FROM memory_items WHERE id=%s", (memory_id,), "item"
        )

    def find_active_head(self, scope, identity):
        items = self._fetch_objects(
            "SELECT * FROM memory_items WHERE tenant_id=%s "
            "AND department_id IS NOT DISTINCT FROM %s AND user_id=%s "
            "AND agent_id=%s AND type=%s AND entity_id=%s AND attribute=%s "
            "AND status='active' ORDER BY version",
            (
                scope.tenant_id, scope.department_id, scope.user_id, scope.agent_id,
                identity.type, identity.entity_id, identity.attribute,
            ),
            "item",
        )
        if len(items) > 1:
            raise MemoryInvariantViolation(
                "Memory scope and identity have multiple ACTIVE heads"
            )
        return items[0] if items else None

    def get_latest_version(self, scope, identity):
        rows = self._fetch_rows(
            "SELECT COALESCE(MAX(version),0) AS latest_version FROM memory_items "
            "WHERE tenant_id=%s AND department_id IS NOT DISTINCT FROM %s "
            "AND user_id=%s AND agent_id=%s AND type=%s "
            "AND entity_id=%s AND attribute=%s",
            (
                scope.tenant_id, scope.department_id, scope.user_id, scope.agent_id,
                identity.type, identity.entity_id, identity.attribute,
            ),
        )
        return int(rows[0]["latest_version"])

    def search(self, request, query_embedding=None, embedding_space_id=None):
        if query_embedding is not None:
            return self.search_vector(request, query_embedding, embedding_space_id)
        return self.search_sql(request, request.query.split())

    def search_sql(self, request, keywords):
        sql = (
            "SELECT memory_items.* FROM memory_items WHERE tenant_id=%s "
            "AND user_id=%s AND agent_id=%s AND status='active'"
        )
        values = [request.scope.tenant_id, request.scope.user_id, request.scope.agent_id]
        sql, values = self._scope_query(sql, values, request)
        normalized = [keyword.strip() for keyword in keywords if keyword.strip()]
        if normalized:
            clauses = []
            for keyword in normalized:
                clauses.append("(memory_key ILIKE %s OR content::text ILIKE %s)")
                pattern = f"%{keyword}%"
                values.extend([pattern, pattern])
            sql += " AND (" + " OR ".join(clauses) + ")"
        sql += " ORDER BY importance DESC, confidence DESC LIMIT %s"
        values.append(request.limit * 4)
        items = [self._hydrate(row, "item") for row in self._fetch_rows(sql, tuple(values))]
        candidates = []
        for item in items:
            text = (
                f"{item.memory_key} "
                f"{json.dumps(item.content, ensure_ascii=False)}"
            ).lower()
            score = 1.0 if not normalized else sum(
                keyword.lower() in text for keyword in normalized
            ) / len(normalized)
            candidates.append((item, score))
        return candidates

    def search_vector(self, request, query_embedding, embedding_space_id=None):
        if not embedding_space_id:
            return []
        self._validate_embedding(query_embedding)
        sql = (
            "SELECT memory_items.*, "
            "1 - (embedding <=> %s::vector) AS semantic_similarity"
            " FROM memory_items WHERE tenant_id=%s AND user_id=%s "
            "AND agent_id=%s AND status='active'"
        )
        values = [query_embedding, request.scope.tenant_id, request.scope.user_id, request.scope.agent_id]
        sql, values = self._scope_query(sql, values, request)
        sql += (
            " AND embedding IS NOT NULL AND embedding_space_id=%s "
            "ORDER BY semantic_similarity DESC LIMIT %s"
        )
        values.extend([embedding_space_id, request.limit * 4])
        rows = self._fetch_rows(sql, tuple(values))
        results = []
        for row in rows:
            similarity = float(row.pop("semantic_similarity", 0.0))
            results.append((self._hydrate(row, "item"), similarity))
        return results

    @staticmethod
    def _scope_query(sql, values, request):
        sql += " AND department_id IS NOT DISTINCT FROM %s"
        values.append(request.scope.department_id)
        if request.types:
            sql += " AND type = ANY(%s)"
            values.append(request.types)
        return sql, values

    def link_replacement(self, old_id, new_id):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_items SET status='replaced',replaced_by_id=%s,"
                    "updated_at=now() WHERE id=%s", (new_id, old_id),
                )
                cursor.execute(
                    "INSERT INTO memory_relations(source_id,target_id,relation_type) "
                    "VALUES(%s,%s,'REPLACES')", (new_id, old_id),
                )

    def create_relation(self, source_id, target_id, relation_type):
        self._validate_relation_type(relation_type)
        self._execute(
            "INSERT INTO memory_relations(source_id,target_id,relation_type) "
            "VALUES(%s,%s,%s)", (source_id, target_id, relation_type),
        )

    def list_relations(self, source_id=None, target_id=None, relation_type=None):
        filters = []
        values = []
        if source_id is not None:
            filters.append("source_id=%s")
            values.append(source_id)
        if target_id is not None:
            filters.append("target_id=%s")
            values.append(target_id)
        if relation_type is not None:
            self._validate_relation_type(relation_type)
            filters.append("relation_type=%s")
            values.append(relation_type)
        sql = "SELECT * FROM memory_relations"
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY id"
        return self._fetch_rows(sql, tuple(values))

    def record_access(self, memory_id, request):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO memory_access_logs(memory_id,trace_id,user_id,agent_id,query) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (memory_id, request.trace_id, request.scope.user_id, request.scope.agent_id, request.query),
                )
                cursor.execute(
                    "UPDATE memory_items SET access_count=access_count+1, "
                    "last_accessed_at=now() WHERE id=%s",
                    (memory_id,),
                )

    def list_versions(self, scope, identity):
        return self._fetch_objects(
            "SELECT * FROM memory_items WHERE tenant_id=%s "
            "AND department_id IS NOT DISTINCT FROM %s AND user_id=%s "
            "AND agent_id=%s AND type=%s AND entity_id=%s AND attribute=%s "
            "ORDER BY version",
            (
                scope.tenant_id, scope.department_id, scope.user_id, scope.agent_id,
                identity.type, identity.entity_id, identity.attribute,
            ),
            "item",
        )

    def update_processing_task(self, event_id, stage, status, error=None):
        self._execute(
            """INSERT INTO memory_processing_tasks(event_id,pipeline_stage,status,error)
            VALUES(%s,%s,%s,%s)
            ON CONFLICT(event_id) DO UPDATE SET
              pipeline_stage=EXCLUDED.pipeline_stage,status=EXCLUDED.status,
              error=EXCLUDED.error,updated_at=now()""",
            (event_id, stage, status, error),
        )

    # ── Internal helpers ──────────────────────────────────────────

    def _insert_item(self, cursor, item):
        if item.embedding is not None:
            self._validate_embedding(item.embedding)
        cursor.execute(
            """INSERT INTO memory_items
            (id,memory_key,type,entity_id,attribute,schema_version,content,
             embedding,importance,embedding_space_id,embedding_provider,
             confidence,source,tenant_id,
             embedding_model,embedding_version,embedding_dimension,
             department_id,user_id,agent_id,version,status,replaces_id,replaced_by_id,
             observation_count,last_observed_at,access_count,last_accessed_at,
             created_at,updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                item.id, item.memory_key, item.type, item.entity_id, item.attribute,
                item.schema_version, json.dumps(item.content), item.embedding,
                item.importance, item.embedding_space_id, item.embedding_provider,
                item.confidence, item.source,
                item.tenant_id, item.embedding_model, item.embedding_version,
                item.embedding_dimension, item.department_id, item.user_id, item.agent_id,
                item.version, item.status, item.replaces_id, item.replaced_by_id,
                item.observation_count, item.last_observed_at, item.access_count,
                item.last_accessed_at, item.created_at, item.updated_at,
            ),
        )

    def _write_item(self, cursor, item, relations):
        for target_id, relation_type in relations or []:
            self._validate_relation_type(relation_type)
            if relation_type == "REPLACES":
                cursor.execute(
                    "UPDATE memory_items SET status='replaced',replaced_by_id=%s,"
                    "updated_at=now() WHERE id=%s AND status='active'",
                    (item.id, target_id),
                )
                if cursor.rowcount != 1:
                    raise ConcurrentMemoryWrite(
                        "Expected ACTIVE head is no longer replaceable"
                    )
        self._insert_item(cursor, item)
        for target_id, relation_type in relations or []:
            cursor.execute(
                "INSERT INTO memory_relations(source_id,target_id,relation_type) "
                "VALUES(%s,%s,%s)",
                (item.id, target_id, relation_type),
            )

    def _validate_embedding(self, embedding):
        if len(embedding) != self.embedding_dimension:
            raise ValueError(
                f"Expected embedding dimension {self.embedding_dimension}, got {len(embedding)}"
            )

    @staticmethod
    def _validate_relation_type(relation_type):
        if relation_type not in RELATION_TYPES:
            raise ValueError(f"Unsupported memory relation type: {relation_type}")

    def _execute(self, sql, values=()):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)

    def _fetch_rows(self, sql, values):
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                columns = [description.name for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @contextmanager
    def _connection(self):
        try:
            connection = _tx_connection.get(None)
            if connection is not None:
                yield connection
            else:
                with self.connection_factory() as connection:
                    yield connection
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryStorageError(
                f"Repository storage failed: {exc}"
            ) from exc

    def _fetch_objects(self, sql, values, kind):
        return [self._hydrate(row, kind) for row in self._fetch_rows(sql, values)]

    def _fetch_object(self, sql, values, kind):
        objects = self._fetch_objects(sql, values, kind)
        return objects[0] if objects else None

    @staticmethod
    def _hydrate(row, kind):
        if kind == "event":
            from app.memory.models.event import MemoryEvent
            return MemoryEvent.from_storage_record(row)
        from app.memory.models.item import MemoryItem
        embedding = row.get("embedding")
        if embedding is not None:
            if hasattr(embedding, "to_list"):
                row["embedding"] = embedding.to_list()
            elif hasattr(embedding, "tolist"):
                row["embedding"] = embedding.tolist()
        return MemoryItem(**row)
