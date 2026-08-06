import json

from app.memory.repository.base import MemoryRepository


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS memory_events (
  event_id text PRIMARY KEY, trace_id text NOT NULL, task_id text NOT NULL,
  agent_id text NOT NULL, user_id text NOT NULL, tenant_id text NOT NULL,
  department_id text, event_type text NOT NULL, input jsonb NOT NULL,
  output jsonb NOT NULL, tool_results jsonb NOT NULL, metadata jsonb NOT NULL,
  status text NOT NULL, error text, created_at timestamptz NOT NULL,
  processed_at timestamptz
);
CREATE TABLE IF NOT EXISTS memory_items (
  id text PRIMARY KEY, memory_key text NOT NULL, type text NOT NULL,
  content jsonb NOT NULL, embedding vector, importance double precision NOT NULL,
  confidence double precision NOT NULL, source text NOT NULL, tenant_id text NOT NULL,
  department_id text, user_id text NOT NULL, agent_id text NOT NULL,
  version integer NOT NULL, status text NOT NULL, replaces_id text,
  replaced_by_id text, access_count integer NOT NULL DEFAULT 0,
  last_accessed_at timestamptz, created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  UNIQUE(memory_key, tenant_id, user_id, agent_id, version)
);
CREATE TABLE IF NOT EXISTS memory_relations (
  id bigserial PRIMARY KEY, source_id text NOT NULL, target_id text NOT NULL,
  relation_type text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS memory_access_logs (
  id bigserial PRIMARY KEY, memory_id text NOT NULL, trace_id text,
  user_id text NOT NULL, agent_id text NOT NULL, accessed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS memory_processing_tasks (
  event_id text PRIMARY KEY, stage text NOT NULL, status text NOT NULL,
  error text, updated_at timestamptz NOT NULL DEFAULT now()
);
"""


class PostgresMemoryRepository(MemoryRepository):
    """DB-API repository. A psycopg connection factory can be injected by deployment."""

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def initialize(self):
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(SCHEMA_SQL)

    def save_event(self, event):
        sql = """INSERT INTO memory_events VALUES
        (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s)"""
        values = (event.event_id, event.trace_id, event.task_id, event.agent_id,
                  event.user_id, event.tenant_id, event.department_id, event.event_type,
                  json.dumps(event.input), json.dumps(event.output), json.dumps(event.tool_results),
                  json.dumps(event.metadata), event.status, event.error, event.created_at, event.processed_at)
        self._execute(sql, values)
        return event

    def get_event(self, event_id):
        return self._fetch_object("SELECT * FROM memory_events WHERE event_id=%s", (event_id,), "event")

    def update_event(self, event):
        self._execute("UPDATE memory_events SET status=%s,error=%s,processed_at=%s WHERE event_id=%s",
                      (event.status, event.error, event.processed_at, event.event_id))
        return event

    def create_item(self, item):
        sql = """INSERT INTO memory_items
        (id,memory_key,type,content,embedding,importance,confidence,source,tenant_id,
         department_id,user_id,agent_id,version,status,replaces_id,replaced_by_id,
         access_count,last_accessed_at,created_at,updated_at)
        VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        values = (item.id, item.memory_key, item.type, json.dumps(item.content), item.embedding,
                  item.importance, item.confidence, item.source, item.tenant_id,
                  item.department_id, item.user_id, item.agent_id, item.version, item.status,
                  item.replaces_id, item.replaced_by_id, item.access_count,
                  item.last_accessed_at, item.created_at, item.updated_at)
        self._execute(sql, values)
        return item

    def get_item(self, memory_id):
        return self._fetch_object("SELECT * FROM memory_items WHERE id=%s", (memory_id,), "item")

    def find_latest(self, memory_key, tenant_id, user_id, agent_id):
        return self._fetch_object(
            "SELECT * FROM memory_items WHERE memory_key=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s ORDER BY version DESC LIMIT 1",
            (memory_key, tenant_id, user_id, agent_id), "item")

    def search(self, request, query_embedding=None):
        sql = "SELECT * FROM memory_items WHERE tenant_id=%s AND user_id=%s AND agent_id=%s AND status='active'"
        values = [request.tenant_id, request.user_id, request.agent_id]
        if request.department_id is not None:
            sql += " AND department_id=%s"; values.append(request.department_id)
        if request.types:
            sql += " AND type = ANY(%s)"; values.append(request.types)
        if query_embedding:
            sql += " ORDER BY embedding <=> %s::vector"; values.append(query_embedding)
        else:
            sql += " ORDER BY importance DESC, confidence DESC"
        sql += " LIMIT %s"; values.append(request.limit * 4)
        items = self._fetch_objects(sql, tuple(values), "item")
        return [(item, 0.0) for item in items]

    def link_replacement(self, old_id, new_id):
        self._execute("UPDATE memory_items SET status='replaced',replaced_by_id=%s,updated_at=now() WHERE id=%s", (new_id, old_id))
        self._execute("INSERT INTO memory_relations(source_id,target_id,relation_type) VALUES(%s,%s,'REPLACES')", (new_id, old_id))

    def record_access(self, memory_id, request):
        self._execute("UPDATE memory_items SET access_count=access_count+1,last_accessed_at=now() WHERE id=%s", (memory_id,))
        self._execute("INSERT INTO memory_access_logs(memory_id,trace_id,user_id,agent_id) VALUES(%s,%s,%s,%s)",
                      (memory_id, request.trace_id, request.user_id, request.agent_id))

    def list_versions(self, memory_key, tenant_id, user_id, agent_id):
        return self._fetch_objects(
            "SELECT * FROM memory_items WHERE memory_key=%s AND tenant_id=%s AND user_id=%s AND agent_id=%s ORDER BY version",
            (memory_key, tenant_id, user_id, agent_id), "item")

    def update_processing_task(self, event_id, stage, status, error=None):
        self._execute(
            """INSERT INTO memory_processing_tasks(event_id,stage,status,error)
            VALUES(%s,%s,%s,%s)
            ON CONFLICT(event_id) DO UPDATE SET
              stage=EXCLUDED.stage,status=EXCLUDED.status,error=EXCLUDED.error,
              updated_at=now()""",
            (event_id, stage, status, error),
        )

    def _execute(self, sql, values=()):
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(sql, values)

    def _fetch_objects(self, sql, values, kind):
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(sql, values)
            columns = [description[0] for description in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return [self._hydrate(row, kind) for row in rows]

    def _fetch_object(self, sql, values, kind):
        objects = self._fetch_objects(sql, values, kind)
        return objects[0] if objects else None

    @staticmethod
    def _hydrate(row, kind):
        if kind == "event":
            from app.memory.models.event import MemoryEvent
            return MemoryEvent(**row)
        from app.memory.models.item import MemoryItem
        return MemoryItem(**row)
