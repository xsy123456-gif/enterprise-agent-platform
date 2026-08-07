from datetime import datetime, timezone
import json
from threading import Lock

from app.memory.embedding.models import EmbeddingResult
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

    def save_event(self, event):
        self.events[event.event_id] = event
        return event

    def get_event(self, event_id):
        return self.events.get(event_id)

    def update_event(self, event):
        self.events[event.event_id] = event
        return event

    def create_item(self, item, relations=None):
        self.items[item.id] = item
        for target_id, relation_type in relations or []:
            self.create_relation(item.id, target_id, relation_type)
            if relation_type == "REPLACES":
                old = self.items[target_id]
                old.status = MemoryItemStatus.REPLACED
                old.replaced_by_id = item.id
                old.updated_at = datetime.now(timezone.utc)
        return item

    def get_item(self, memory_id):
        return self.items.get(memory_id)

    def find_latest(self, scope, identity):
        candidates = [
            item for item in self.items.values()
            if item.scope == scope and item.identity == identity
        ]
        return max(candidates, key=lambda item: item.version) if candidates else None

    def search(self, request, query_embedding=None):
        if query_embedding is not None:
            return self.search_vector(request, query_embedding)
        return self.search_sql(request, request.query.lower().split())

    def _scoped_items(self, request):
        items = []
        for item in self.items.values():
            if item.status != MemoryItemStatus.ACTIVE or item.tenant_id != request.tenant_id:
                continue
            if item.user_id != request.user_id or item.agent_id != request.agent_id:
                continue
            if item.department_id != request.department_id:
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

    def search_vector(self, request, query_embedding):
        candidates = []
        for item in self._scoped_items(request):
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
            "user_id": request.user_id, "agent_id": request.agent_id,
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

    def __init__(self, mapping=None, dimension=3):
        self.mapping = dict(mapping or {})
        self.dimension = dimension
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
            vector=list(vector), model="test-embedding",
            version="test", dimension=len(vector),
        )
