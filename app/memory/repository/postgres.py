import json

from app.memory.repository.base import MemoryRepository


TABLES = {
    "memory_events",
    "memory_items",
    "memory_relations",
    "memory_access_logs",
    "memory_processing_tasks",
}
REQUIRED_COLUMNS = {
    "memory_events": {
        "event_id", "trace_id", "task_id", "agent_id", "user_id", "tenant_id",
        "department_id", "event_type", "input", "output", "tool_results",
        "metadata", "status", "created_at", "processed_at",
    },
    "memory_items": {
        "id", "memory_key", "type", "content", "embedding", "importance",
        "confidence", "source", "tenant_id", "department_id", "user_id",
        "agent_id", "version", "status", "replaces_id", "replaced_by_id",
        "access_count", "last_accessed_at", "created_at", "updated_at",
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
}
RELATION_TYPES = {"REPLACES", "DERIVED_FROM", "MERGED_FROM", "CONFLICT_WITH"}


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
  status text NOT NULL CHECK (status IN ('received','processing','processed','failed')),
  error text, created_at timestamptz NOT NULL, processed_at timestamptz
);
CREATE TABLE IF NOT EXISTS memory_items (
  id text PRIMARY KEY, memory_key text NOT NULL, type text NOT NULL,
  content jsonb NOT NULL, embedding {vector_type}, importance double precision NOT NULL,
  confidence double precision NOT NULL, source text NOT NULL, tenant_id text NOT NULL,
  department_id text, user_id text NOT NULL, agent_id text NOT NULL,
  version integer NOT NULL CHECK (version > 0),
  status text NOT NULL CHECK (status IN ('active','replaced','conflict','archived')),
  replaces_id text, replaced_by_id text, access_count integer NOT NULL DEFAULT 0,
  last_accessed_at timestamptz, created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  UNIQUE(memory_key, tenant_id, user_id, agent_id, version)
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
CREATE INDEX IF NOT EXISTS memory_items_scope_active_idx
  ON memory_items (tenant_id, user_id, agent_id, status);
CREATE INDEX IF NOT EXISTS memory_events_status_idx ON memory_events (status);
CREATE INDEX IF NOT EXISTS memory_relations_source_idx
  ON memory_relations (source_id, relation_type);
CREATE INDEX IF NOT EXISTS memory_access_logs_memory_idx
  ON memory_access_logs (memory_id, created_at DESC);
CREATE INDEX IF NOT EXISTS memory_items_embedding_hnsw_idx
  ON memory_items USING hnsw (embedding vector_cosine_ops);
"""


class PostgresMemoryRepository(MemoryRepository):
    """Transactional PostgreSQL + pgvector implementation of MemoryRepository."""

    def __init__(self, connection_factory, embedding_dimension):
        self.connection_factory = connection_factory
        self.embedding_dimension = embedding_dimension

    def initialize(self):
        with self.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(build_schema_sql(self.embedding_dimension))
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
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema=current_schema() AND table_name = ANY(%s)",
                    (list(TABLES),),
                )
                columns = {}
                for table, column in cursor.fetchall():
                    columns.setdefault(table, set()).add(column)
                cursor.execute(
                    "SELECT format_type(attribute.atttypid,attribute.atttypmod) "
                    "FROM pg_attribute attribute "
                    "JOIN pg_class relation ON relation.oid=attribute.attrelid "
                    "JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace "
                    "WHERE namespace.nspname=current_schema() "
                    "AND relation.relname='memory_items' "
                    "AND attribute.attname='embedding'"
                )
                vector_type = cursor.fetchone()
        missing = TABLES - tables
        if not extension:
            raise RuntimeError("pgvector extension is not enabled")
        if missing:
            raise RuntimeError(f"Memory schema is missing tables: {sorted(missing)}")
        if not vector_index:
            raise RuntimeError("Memory vector index is missing")
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
            "embedding_dimension": self.embedding_dimension,
            "vector_type": actual_vector_type,
        }

    def save_event(self, event):
        sql = """INSERT INTO memory_events
        (event_id,trace_id,task_id,agent_id,user_id,tenant_id,department_id,
         event_type,input,output,tool_results,metadata,status,error,created_at,processed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                %s,%s,%s,%s)"""
        values = (
            event.event_id, event.trace_id, event.task_id, event.agent_id,
            event.user_id, event.tenant_id, event.department_id, event.event_type,
            json.dumps(event.input), json.dumps(event.output),
            json.dumps(event.tool_results), json.dumps(event.metadata), event.status,
            event.error, event.created_at, event.processed_at,
        )
        self._execute(sql, values)
        return event

    def get_event(self, event_id):
        return self._fetch_object(
            "SELECT * FROM memory_events WHERE event_id=%s", (event_id,), "event"
        )

    def update_event(self, event):
        self._execute(
            "UPDATE memory_events SET status=%s,error=%s,processed_at=%s WHERE event_id=%s",
            (event.status, event.error, event.processed_at, event.event_id),
        )
        return event

    def create_item(self, item, relations=None):
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._insert_item(cursor, item)
                for target_id, relation_type in relations or []:
                    self._validate_relation_type(relation_type)
                    cursor.execute(
                        "INSERT INTO memory_relations(source_id,target_id,relation_type) "
                        "VALUES(%s,%s,%s)",
                        (item.id, target_id, relation_type),
                    )
                    if relation_type == "REPLACES":
                        cursor.execute(
                            "UPDATE memory_items SET status='replaced',replaced_by_id=%s,"
                            "updated_at=now() WHERE id=%s",
                            (item.id, target_id),
                        )
        return item

    def get_item(self, memory_id):
        return self._fetch_object(
            "SELECT * FROM memory_items WHERE id=%s", (memory_id,), "item"
        )

    def find_latest(self, memory_key, tenant_id, user_id, agent_id):
        return self._fetch_object(
            "SELECT * FROM memory_items WHERE memory_key=%s AND tenant_id=%s "
            "AND user_id=%s AND agent_id=%s ORDER BY version DESC LIMIT 1",
            (memory_key, tenant_id, user_id, agent_id), "item",
        )

    def search(self, request, query_embedding=None):
        vector_search = query_embedding is not None
        select = "SELECT memory_items.*"
        values = []
        if vector_search:
            self._validate_embedding(query_embedding)
            select += ", 1 - (embedding <=> %s::vector) AS semantic_similarity"
            values.append(query_embedding)
        sql = select + (
            " FROM memory_items WHERE tenant_id=%s AND user_id=%s "
            "AND agent_id=%s AND status='active'"
        )
        values.extend([request.tenant_id, request.user_id, request.agent_id])
        if request.department_id is not None:
            sql += " AND department_id=%s"
            values.append(request.department_id)
        if request.types:
            sql += " AND type = ANY(%s)"
            values.append(request.types)
        if vector_search:
            sql += " AND embedding IS NOT NULL ORDER BY semantic_similarity DESC"
        else:
            sql += " ORDER BY importance DESC, confidence DESC"
        sql += " LIMIT %s"
        values.append(request.limit * 4)
        rows = self._fetch_rows(sql, tuple(values))
        results = []
        for row in rows:
            similarity = float(row.pop("semantic_similarity", 0.0))
            results.append((self._hydrate(row, "item"), similarity))
        return results

    def link_replacement(self, old_id, new_id):
        with self.connection_factory() as connection:
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
        self._execute(
            "INSERT INTO memory_access_logs(memory_id,trace_id,user_id,agent_id,query) "
            "VALUES(%s,%s,%s,%s,%s)",
            (memory_id, request.trace_id, request.user_id, request.agent_id, request.query),
        )

    def list_versions(self, memory_key, tenant_id, user_id, agent_id):
        return self._fetch_objects(
            "SELECT * FROM memory_items WHERE memory_key=%s AND tenant_id=%s "
            "AND user_id=%s AND agent_id=%s ORDER BY version",
            (memory_key, tenant_id, user_id, agent_id), "item",
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

    def _insert_item(self, cursor, item):
        if item.embedding is not None:
            self._validate_embedding(item.embedding)
        cursor.execute(
            """INSERT INTO memory_items
            (id,memory_key,type,content,embedding,importance,confidence,source,tenant_id,
             department_id,user_id,agent_id,version,status,replaces_id,replaced_by_id,
             access_count,last_accessed_at,created_at,updated_at)
            VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                item.id, item.memory_key, item.type, json.dumps(item.content),
                item.embedding, item.importance, item.confidence, item.source,
                item.tenant_id, item.department_id, item.user_id, item.agent_id,
                item.version, item.status, item.replaces_id, item.replaced_by_id,
                item.access_count, item.last_accessed_at, item.created_at, item.updated_at,
            ),
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
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)

    def _fetch_rows(self, sql, values):
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                columns = [description.name for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _fetch_objects(self, sql, values, kind):
        return [self._hydrate(row, kind) for row in self._fetch_rows(sql, values)]

    def _fetch_object(self, sql, values, kind):
        objects = self._fetch_objects(sql, values, kind)
        return objects[0] if objects else None

    @staticmethod
    def _hydrate(row, kind):
        if kind == "event":
            from app.memory.models.event import MemoryEvent
            return MemoryEvent(**row)
        from app.memory.models.item import MemoryItem
        embedding = row.get("embedding")
        if embedding is not None and hasattr(embedding, "tolist"):
            row["embedding"] = embedding.tolist()
        return MemoryItem(**row)
