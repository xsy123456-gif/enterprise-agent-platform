from datetime import datetime, timezone
import json

from app.memory.models.item import MemoryItemStatus
from app.memory.repository.base import MemoryRepository


class TestMemoryRepository(MemoryRepository):
    """Test-only repository; production code has no dictionary storage fallback."""

    __test__ = False

    def __init__(self):
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

    def find_latest(self, memory_key, tenant_id, user_id, agent_id):
        candidates = [
            item for item in self.items.values()
            if item.memory_key == memory_key and item.tenant_id == tenant_id
            and item.user_id == user_id and item.agent_id == agent_id
        ]
        return max(candidates, key=lambda item: item.version) if candidates else None

    def search(self, request, query_embedding=None):
        query = request.query.lower().strip()
        candidates = []
        for item in self.items.values():
            if item.status != MemoryItemStatus.ACTIVE or item.tenant_id != request.tenant_id:
                continue
            if item.user_id != request.user_id or item.agent_id != request.agent_id:
                continue
            if request.department_id is not None and item.department_id != request.department_id:
                continue
            if request.types and item.type not in request.types:
                continue
            text = f"{item.memory_key} {json.dumps(item.content, ensure_ascii=False)}".lower()
            score = 1.0 if not query else sum(
                token in text for token in query.split()
            ) / max(len(query.split()), 1)
            candidates.append((item, score))
        return candidates

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

    def list_versions(self, memory_key, tenant_id, user_id, agent_id):
        return sorted([
            item for item in self.items.values()
            if item.memory_key == memory_key and item.tenant_id == tenant_id
            and item.user_id == user_id and item.agent_id == agent_id
        ], key=lambda item: item.version)

    def update_processing_task(self, event_id, stage, status, error=None):
        self.processing_tasks[event_id] = {
            "event_id": event_id, "stage": stage, "status": status,
            "error": error, "updated_at": datetime.now(timezone.utc),
        }
