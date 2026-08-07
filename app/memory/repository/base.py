from abc import ABC, abstractmethod


class MemoryRepository(ABC):
    @abstractmethod
    def save_event(self, event): pass

    @abstractmethod
    def get_event(self, event_id): pass

    @abstractmethod
    def update_event(self, event): pass

    @abstractmethod
    def claim_events(self, worker_id, limit, lease_seconds): pass

    @abstractmethod
    def renew_lease(self, event_id, lock_token, lease_seconds): pass

    @abstractmethod
    def commit_event_result(self, event, domain_events, lock_token): pass

    @abstractmethod
    def add_outbox(self, event): pass

    @abstractmethod
    def claim_outbox(self, limit, worker_id, lease_seconds): pass

    @abstractmethod
    def mark_outbox_published(self, outbox_id): pass

    @abstractmethod
    def retry_outbox(self, outbox_id, error, next_attempt_at): pass

    @abstractmethod
    def dead_letter_outbox(self, outbox_id, error): pass

    @abstractmethod
    def finalize_event(self, event, domain_events): pass

    @abstractmethod
    def create_item(self, item, relations=None): pass

    @abstractmethod
    def commit_resolution(
        self, item, expected_active_head_id, relations=None
    ): pass

    @abstractmethod
    def merge_observation(self, item, evaluation): pass

    @abstractmethod
    def get_item(self, memory_id): pass

    @abstractmethod
    def find_active_head(self, scope, identity): pass

    @abstractmethod
    def get_latest_version(self, scope, identity): pass

    @abstractmethod
    def search(self, request, query_embedding=None, embedding_space_id=None): pass

    @abstractmethod
    def search_sql(self, request, keywords): pass

    @abstractmethod
    def search_vector(self, request, query_embedding, embedding_space_id=None): pass

    @abstractmethod
    def link_replacement(self, old_id, new_id): pass

    @abstractmethod
    def create_relation(self, source_id, target_id, relation_type): pass

    @abstractmethod
    def list_relations(self, source_id=None, target_id=None, relation_type=None): pass

    @abstractmethod
    def record_access(self, memory_id, request): pass

    @abstractmethod
    def list_versions(self, scope, identity): pass

    @abstractmethod
    def update_processing_task(self, event_id, stage, status, error=None): pass
