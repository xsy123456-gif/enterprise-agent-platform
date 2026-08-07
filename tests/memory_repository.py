from datetime import datetime, timezone
import json
from threading import Lock, RLock
from contextlib import contextmanager
import copy

from app.memory.embedding.models import EmbeddingResult, EmbeddingSpace
from app.memory.errors import ConcurrentMemoryWrite, MemoryInvariantViolation
from app.memory.models.item import MemoryItemStatus
from app.memory.repository.base import MemoryRepository


class TestMemoryRepository(MemoryRepository):
    """Test-only repository; production code has no dictionary storage fallback."""

    __test__ = False

    def __init__(self):
        self.embedding_dimension = 3
        self.events = {}
        self.items = {}
        self.relations = []
        self.access_logs = []
        self.processing_tasks = {}
        self.outbox = {}
        self._commit_lock = RLock()

    def save_event(self, event):
        for stored in self.events.values():
            if (stored.tenant_id, stored.source_kind, stored.idempotency_key) == (
                event.tenant_id, event.source_kind, event.idempotency_key
            ):
                return stored
        self.events[event.event_id] = event
        return event

    @contextmanager
    def atomic_write(self):
        snapshot = (copy.deepcopy(self.items), copy.deepcopy(self.relations))
        try:
            yield
        except Exception:
            self.items, self.relations = snapshot
            raise

    def get_event(self, event_id):
        return self.events.get(event_id)

    def update_event(self, event):
        self.events[event.event_id] = event
        return event

    def claim_events(self, worker_id, limit, lease_seconds):
        now = datetime.now(timezone.utc)
        claimed = []
        for event in self.events.values():
            claimable = event.status in {"received", "retry_wait"} and (
                event.next_attempt_at is None or event.next_attempt_at <= now
            )
            expired = event.status == "processing" and event.lease_until and event.lease_until <= now
            if (claimable or expired) and len(claimed) < limit:
                event.status = "processing"
                event.locked_by = worker_id
                event.lease_until = now
                event.attempt_count += 1
                claimed.append(event)
        return claimed

    def add_outbox(self, event):
        self.outbox.setdefault(event.event_id, {
            "id": event.event_id, "event_type": event.event_type,
            "aggregate_id": event.aggregate_id, "payload": event.payload,
            "status": "pending", "attempt_count": 0,
        })

    def claim_outbox(self, limit):
        return [item for item in self.outbox.values() if item["status"] == "pending"][:limit]

    def mark_outbox_published(self, outbox_id):
        self.outbox[outbox_id]["status"] = "published"

    def retry_outbox(self, outbox_id, error, next_attempt_at):
        item = self.outbox[outbox_id]
        item["attempt_count"] += 1
        item["last_error"] = error
        item["available_at"] = next_attempt_at

    def finalize_event(self, event, domain_events):
        self.update_event(event)
        for domain_event in domain_events:
            self.add_outbox(domain_event)

    def create_item(self, item, relations=None):
        replacing_ids = {
            target_id for target_id, relation_type in relations or []
            if relation_type == "REPLACES"
        }
        active = [
            current for current in self.items.values()
            if current.scope == item.scope and current.identity == item.identity
            and current.status == MemoryItemStatus.ACTIVE
            and current.id not in replacing_ids
        ]
        if item.status == MemoryItemStatus.ACTIVE and active:
            raise MemoryInvariantViolation(
                "Memory scope and identity already have an ACTIVE head"
            )
        self.items[item.id] = item
        for target_id, relation_type in relations or []:
            self.create_relation(item.id, target_id, relation_type)
            if relation_type == "REPLACES":
                old = self.items[target_id]
                old.status = MemoryItemStatus.REPLACED
                old.replaced_by_id = item.id
                old.updated_at = datetime.now(timezone.utc)
        return item

    def commit_resolution(self, item, expected_active_head_id, relations=None):
        with self._commit_lock:
            current = self.find_active_head(item.scope, item.identity)
            current_id = current.id if current else None
            if current_id != expected_active_head_id:
                raise ConcurrentMemoryWrite(
                    "ACTIVE head changed while committing Memory"
                )
            item.version = self.get_latest_version(item.scope, item.identity) + 1
            return self.create_item(item, relations=relations)

    def get_item(self, memory_id):
        return self.items.get(memory_id)

    def find_active_head(self, scope, identity):
        candidates = [
            item for item in self.items.values()
            if item.scope == scope and item.identity == identity
            and item.status == MemoryItemStatus.ACTIVE
        ]
        if len(candidates) > 1:
            raise MemoryInvariantViolation(
                "Memory scope and identity have multiple ACTIVE heads"
            )
        return candidates[0] if candidates else None

    def get_latest_version(self, scope, identity):
        versions = self.list_versions(scope, identity)
        return max((item.version for item in versions), default=0)

    def search(self, request, query_embedding=None, embedding_space_id=None):
        if query_embedding is not None:
            return self.search_vector(request, query_embedding, embedding_space_id)
        return self.search_sql(request, request.query.lower().split())

    def _scoped_items(self, request):
        items = []
        for item in self.items.values():
            if item.status != MemoryItemStatus.ACTIVE or item.tenant_id != request.scope.tenant_id:
                continue
            if item.user_id != request.scope.user_id or item.agent_id != request.scope.agent_id:
                continue
            if item.department_id != request.scope.department_id:
                continue
            if request.types and item.type not in request.types:
                continue
            items.append(item)
        return items

    def search_sql(self, request, keywords):
        normalized = [keyword.lower() for keyword in keywords]
        query = request.query.lower().strip()
        candidates = []
        for item in self._scoped_items(request):
            text = f"{item.memory_key} {json.dumps(item.content, ensure_ascii=False)}".lower()
            score = 1.0 if not normalized else sum(
                keyword in text for keyword in normalized
            ) / len(normalized)
            if score > 0 or not query:
                candidates.append((item, score))
        return candidates

    def search_vector(self, request, query_embedding, embedding_space_id=None):
        if not embedding_space_id:
            return []
        candidates = []
        for item in self._scoped_items(request):
            if item.embedding_space_id != embedding_space_id:
                continue
            if not item.embedding or len(item.embedding) != len(query_embedding):
                continue
            dot = sum(a * b for a, b in zip(item.embedding, query_embedding))
            left = sum(value * value for value in item.embedding) ** 0.5
            right = sum(value * value for value in query_embedding) ** 0.5
            score = dot / (left * right) if left and right else 0.0
            candidates.append((item, score))
        return sorted(candidates, key=lambda value: value[1], reverse=True)

    def link_replacement(self, old_id, new_id):
        old = self.items[old_id]
        old.status = MemoryItemStatus.REPLACED
        old.replaced_by_id = new_id
        self.create_relation(new_id, old_id, "REPLACES")

    def create_relation(self, source_id, target_id, relation_type):
        relation = {
            "source_id": source_id, "target_id": target_id,
            "relation_type": relation_type, "created_at": datetime.now(timezone.utc),
        }
        self.relations.append(relation)
        return relation

    def list_relations(self, source_id=None, target_id=None, relation_type=None):
        return [
            relation for relation in self.relations
            if (source_id is None or relation["source_id"] == source_id)
            and (target_id is None or relation["target_id"] == target_id)
            and (relation_type is None or relation["relation_type"] == relation_type)
        ]

    def record_access(self, memory_id, request):
        self.access_logs.append({
            "memory_id": memory_id, "trace_id": request.trace_id,
            "user_id": request.scope.user_id, "agent_id": request.scope.agent_id,
            "query": request.query, "created_at": datetime.now(timezone.utc),
        })

    def list_versions(self, scope, identity):
        return sorted([
            item for item in self.items.values()
            if item.scope == scope and item.identity == identity
        ], key=lambda item: item.version)

    def update_processing_task(self, event_id, stage, status, error=None):
        self.processing_tasks[event_id] = {
            "event_id": event_id, "stage": stage, "status": status,
            "error": error, "updated_at": datetime.now(timezone.utc),
        }


class TestEmbeddingService:
    __test__ = False

    def __init__(self, mapping=None, dimension=3, provider="test", model="test-embedding", version="test"):
        self.mapping = dict(mapping or {})
        self.dimension = dimension
        self.space = EmbeddingSpace(provider, model, version, dimension)
        self.vectors = {}
        self.lock = Lock()

    def embed(self, text):
        with self.lock:
            vector = self.mapping.get(text)
            if vector is None:
                vector = self.vectors.get(text)
            if vector is None:
                index = len(self.vectors) % self.dimension
                vector = [0.0] * self.dimension
                vector[index] = 1.0
                self.vectors[text] = vector
        return EmbeddingResult(
            vector=list(vector), space=self.space,
        )
