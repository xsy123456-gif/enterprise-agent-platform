from datetime import datetime, timezone
import json

from app.memory.models.item import MemoryItemStatus
from app.memory.repository.base import MemoryRepository


class InMemoryMemoryRepository(MemoryRepository):
    def __init__(self):
        self.events = {}
        self.items = {}
        self.access_logs = []
        self.processing_tasks = {}

    def save_event(self, event):
        self.events[event.event_id] = event
        return event

    def get_event(self, event_id):
        return self.events.get(event_id)

    def update_event(self, event):
        if event.event_id not in self.events:
            raise KeyError(f"Memory event not found: {event.event_id}")
        self.events[event.event_id] = event
        return event

    def create_item(self, item):
        self.items[item.id] = item
        return item

    def get_item(self, memory_id):
        return self.items.get(memory_id)

    def find_latest(self, memory_key, tenant_id, user_id, agent_id):
        candidates = [item for item in self.items.values()
                      if item.memory_key == memory_key and item.tenant_id == tenant_id
                      and item.user_id == user_id and item.agent_id == agent_id]
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
            similarity = self._similarity(item, query, text, query_embedding)
            candidates.append((item, similarity))
        return candidates

    @staticmethod
    def _similarity(item, query, text, query_embedding):
        if query_embedding and item.embedding:
            dot = sum(left * right for left, right in zip(query_embedding, item.embedding))
            left_norm = sum(value * value for value in query_embedding) ** 0.5
            right_norm = sum(value * value for value in item.embedding) ** 0.5
            return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
        return 1.0 if not query else sum(
            token in text for token in query.split()
        ) / max(len(query.split()), 1)

    def link_replacement(self, old_id, new_id):
        old = self.items[old_id]
        old.status = MemoryItemStatus.REPLACED
        old.replaced_by_id = new_id
        old.updated_at = datetime.now(timezone.utc)

    def record_access(self, memory_id, request):
        item = self.items[memory_id]
        item.access_count += 1
        item.last_accessed_at = datetime.now(timezone.utc)
        self.access_logs.append({"memory_id": memory_id, "trace_id": request.trace_id})

    def list_versions(self, memory_key, tenant_id, user_id, agent_id):
        items = [item for item in self.items.values()
                 if item.memory_key == memory_key and item.tenant_id == tenant_id
                 and item.user_id == user_id and item.agent_id == agent_id]
        return sorted(items, key=lambda item: item.version)

    def update_processing_task(self, event_id, stage, status, error=None):
        self.processing_tasks[event_id] = {
            "event_id": event_id,
            "stage": stage,
            "status": status,
            "error": error,
            "updated_at": datetime.now(timezone.utc),
        }
        return self.processing_tasks[event_id]
