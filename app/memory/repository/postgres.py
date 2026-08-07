import json

from app.memory.errors import ConcurrentMemoryWrite, MemoryInvariantViolation
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
  observation_count integer NOT NULL DEFAULT 1, last_observed_at timestamptz,
  access_count integer NOT NULL DEFAULT 0, last_accessed_at timestamptz,
  created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL
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
ALTER TABLE memory_items DROP CONSTRAINT IF EXISTS
  memory_items_memory_key_tenant_id_user_id_agent_id_version_key;
CREATE INDEX IF NOT EXISTS memory_items_scope_active_idx
  ON memory_items (tenant_id, department_id, user_id, agent_id, status);
CREATE INDEX IF NOT EXISTS memory_events_status_idx ON memory_events (status);
CREATE INDEX IF NOT EXISTS memory_relations_source_idx
  ON memory_relations (source_id, relation_type);
CREATE INDEX IF NOT EXISTS memory_access_logs_memory_idx
  ON memory_access_logs (memory_id, created_at DESC);
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
                    "SELECT format_type(attribute.atttypid,attribute.atttypmod) "
                    "FROM pg_attribute attribute "
                    "JOIN pg_class relation ON relation.oid=attribute.attrelid "
                    "JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace "
                    "WHERE namespace.nspname=current_schema() "
                    "AND relation.relname='memory_items' "
                    "AND attribute.attname='embedding'"
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

    def save_event(self, event):
        sql = """INSERT INTO memory_events
        (event_id,trace_id,task_id,agent_id,user_id,tenant_id,department_id,
         event_type,input,output,tool_results,metadata,status,error,created_at,processed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                %s,%s,%s,%s)"""
        values = (
            event.event_id, event.trace_id, event.task_id, event.agent_id,
            event.user_id, event.tenant_id, event.department_id, event.source_kind,
            json.dumps({}), json.dumps({}), json.dumps([]),
            json.dumps(event.storage_metadata()), event.status,
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
                self._write_item(cursor, item, relations)
        return item

    def commit_resolution(self, item, expected_active_head_id, relations=None):
        lock_key = json.dumps([
            item.tenant_id, item.department_id, item.user_id, item.agent_id,
            item.type, item.entity_id, item.attribute,
        ], ensure_ascii=False, separators=(",", ":"))
        with self.connection_factory() as connection:
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
            (memory_id, request.trace_id, request.scope.user_id, request.scope.agent_id, request.query),
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
            return MemoryEvent.from_storage_record(row)
        from app.memory.models.item import MemoryItem
        embedding = row.get("embedding")
        if embedding is not None:
            if hasattr(embedding, "to_list"):
                row["embedding"] = embedding.to_list()
            elif hasattr(embedding, "tolist"):
                row["embedding"] = embedding.tolist()
        return MemoryItem(**row)
