from datetime import datetime, timedelta, timezone
import json
from threading import Lock, RLock
from contextlib import contextmanager
import copy

from app.memory.embedding.models import EmbeddingResult, EmbeddingSpace
from app.memory.errors import ConcurrentMemoryWrite, MemoryError, MemoryInvariantViolation
from app.memory.models.item import MemoryItemStatus
from app.memory.repository.base import MemoryRepository


class TestMemoryRepository(MemoryRepository):
    """Test-only repository; production code has no dictionary storage fallback.

    Row state (_event_state) is tracked independently of Python event objects
    so that pre-setting event.status before commit_event_result does not
    contaminate the ownership check.
    """

    __test__ = False

    def __init__(self):
        self.embedding_dimension = 3
        self.events = {}
        self._event_state = {}
        self.items = {}
        self.relations = []
        self.access_logs = []
        self.processing_tasks = {}
        self.outbox = {}
        self._commit_lock = RLock()
        self._tx_active = False
        self._tx_snapshot = None

    def _es(self, event_id):
        return self._event_state.setdefault(event_id, {})

    def save_event(self, event):
        for stored in self.events.values():
            if (stored.tenant_id, stored.source_kind, stored.idempotency_key) == (
                event.tenant_id, event.source_kind, event.idempotency_key
            ):
                return stored
        self.events[event.event_id] = event
        st = self._es(event.event_id)
        st["status"] = event.status
        return event

    @contextmanager
    def atomic_write(self):
        if self._tx_active:
            yield
            return
        self._tx_active = True
        self._tx_snapshot = (copy.deepcopy(self.items), copy.deepcopy(self.relations))
        try:
            yield
        except Exception as exc:
            self.items, self.relations = self._tx_snapshot
            if isinstance(exc, MemoryError):
                raise
            from app.memory.errors import MemoryStorageError
            raise MemoryStorageError(
                f"Repository atomic write failed: {exc}"
            ) from exc
        finally:
            self._tx_active = False
            self._tx_snapshot = None

    def get_event(self, event_id):
        return self.events.get(event_id)

    def update_event(self, event):
        self.events[event.event_id] = event
        st = self._es(event.event_id)
        st["status"] = event.status
        return event

    def claim_events(self, worker_id, limit, lease_seconds):
        import uuid
        now = datetime.now(timezone.utc)
        claimed = []
        for event in list(self.events.values()):
            st = self._es(event.event_id)
            status = st.get("status", event.status)
            claimable = status in {"received", "retry_wait"} and (
                event.next_attempt_at is None or event.next_attempt_at <= now
            )
            expired = (
                status == "processing"
                and st.get("lease_until")
                and st["lease_until"] <= now
            )
            if (claimable or expired) and len(claimed) < limit:
                st["status"] = "processing"
                st["locked_by"] = worker_id
                st["lock_token"] = str(uuid.uuid4())
                st["lease_until"] = now + timedelta(seconds=lease_seconds)
                event.status = "processing"
                event.locked_by = worker_id
                event.lock_token = st["lock_token"]
                event.lease_until = st["lease_until"]
                event.attempt_count += 1
                event.error = None
                event.error_code = None
                claimed.append(event)
        return claimed

    def renew_lease(self, event_id, worker_id, lock_token, lease_seconds):
        st = self._es(event_id)
        if (
            st.get("status") == "processing"
            and st.get("locked_by") == worker_id
            and st.get("lock_token") == lock_token
            and st.get("lease_until")
            and st["lease_until"] > datetime.now(timezone.utc)
        ):
            st["lease_until"] = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
            event = self.events.get(event_id)
            if event:
                event.lease_until = st["lease_until"]
            return True
        return False

    def commit_event_result(self, event, worker_id, domain_events, lock_token):
        st = self._es(event.event_id)
        if not self.events.get(event.event_id):
            raise ConcurrentMemoryWrite("Event result rejected: event not found")
        if (st.get("status") != "processing"
                or st.get("locked_by") != worker_id
                or st.get("lock_token") != lock_token
                or not st.get("lease_until")
                or st["lease_until"] <= datetime.now(timezone.utc)):
            raise ConcurrentMemoryWrite("Event result rejected: ownership lost")
        status = event.status
        if status == "processed":
            event.error = None
            event.error_code = None
            event.next_attempt_at = None
        st["status"] = status
        st.pop("locked_by", None)
        st.pop("lock_token", None)
        st.pop("lease_until", None)
        event.locked_by = None
        event.lease_until = None
        event.lock_token = None
        return self.finalize_event(event, domain_events)

    def finalize_event(self, event, domain_events):
        self.update_event(event)
        for domain_event in domain_events:
            self.add_outbox(domain_event)

    def add_outbox(self, event):
        self.outbox.setdefault(event.event_id, {
            "id": event.event_id, "event_type": event.event_type,
            "aggregate_id": event.aggregate_id, "payload": event.payload,
            "status": "pending", "attempt_count": 0, "lock_token": None,
            "locked_by": None, "lease_until": None,
        })

    def claim_outbox(self, limit, worker_id=None, lease_seconds=30):
        import uuid
        now = datetime.now(timezone.utc)
        claimed = []
        for item in list(self.outbox.values()):
            claimable = item["status"] == "pending"
            expired = (
                item["status"] == "processing"
                and item.get("lease_until")
                and item["lease_until"] <= now
            )
            if (claimable or expired) and len(claimed) < limit:
                item["status"] = "processing"
                item["locked_by"] = worker_id
                item["lock_token"] = str(uuid.uuid4())
                item["lease_until"] = now + timedelta(seconds=lease_seconds)
                item["attempt_count"] += 1
                claimed.append(item)
        return claimed

    def mark_outbox_published(self, outbox_id, worker_id, lock_token):
        item = self.outbox.get(outbox_id)
        if not item:
            raise ConcurrentMemoryWrite("Outbox CAS mark_published: record not found")
        if (item["status"] != "processing"
                or item.get("locked_by") != worker_id
                or item.get("lock_token") != lock_token
                or not item.get("lease_until")
                or item["lease_until"] <= datetime.now(timezone.utc)):
            raise ConcurrentMemoryWrite("Outbox CAS mark_published: ownership lost")
        item["status"] = "published"
        return True

    def retry_outbox(self, outbox_id, error, next_attempt_at, worker_id, lock_token):
        item = self.outbox.get(outbox_id)
        if not item:
            raise ConcurrentMemoryWrite("Outbox CAS retry: record not found")
        if (item["status"] != "processing"
                or item.get("locked_by") != worker_id
                or item.get("lock_token") != lock_token
                or not item.get("lease_until")
                or item["lease_until"] <= datetime.now(timezone.utc)):
            raise ConcurrentMemoryWrite("Outbox CAS retry: ownership lost")
        item["status"] = "pending"
        item["last_error"] = error
        item["available_at"] = next_attempt_at
        return True

    def dead_letter_outbox(self, outbox_id, error, worker_id, lock_token):
        item = self.outbox.get(outbox_id)
        if not item:
            raise ConcurrentMemoryWrite("Outbox CAS dead_letter: record not found")
        if (item["status"] != "processing"
                or item.get("locked_by") != worker_id
                or item.get("lock_token") != lock_token
                or not item.get("lease_until")
                or item["lease_until"] <= datetime.now(timezone.utc)):
            raise ConcurrentMemoryWrite("Outbox CAS dead_letter: ownership lost")
        item["status"] = "dead_letter"
        item["last_error"] = error
        return True

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

    def merge_observation(self, item, evaluation):
        stored = self.items.get(item.id)
        if not stored or stored.status != MemoryItemStatus.ACTIVE:
            raise ConcurrentMemoryWrite(
                "Could not merge observation: item is no longer ACTIVE"
            )
        stored.observation_count += 1
        stored.last_observed_at = datetime.now(timezone.utc)
        stored.updated_at = datetime.now(timezone.utc)
        stored.confidence = max(stored.confidence, evaluation.confidence)
        stored.importance = max(stored.importance, evaluation.importance)
        return stored

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
        item = self.items.get(memory_id)
        if item:
            item.access_count += 1
            item.last_accessed_at = datetime.now(timezone.utc)

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
