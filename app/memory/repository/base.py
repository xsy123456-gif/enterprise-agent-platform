from abc import ABC, abstractmethod


class MemoryRepository(ABC):
    @abstractmethod
    def save_event(self, event): pass

    @abstractmethod
    def get_event(self, event_id): pass

    @abstractmethod
    def update_event(self, event): pass

    @abstractmethod
    def create_item(self, item, relations=None): pass

    @abstractmethod
    def get_item(self, memory_id): pass

    @abstractmethod
    def find_latest(self, memory_key, tenant_id, user_id, agent_id): pass

    @abstractmethod
    def search(self, request, query_embedding=None): pass

    @abstractmethod
    def link_replacement(self, old_id, new_id): pass

    @abstractmethod
    def create_relation(self, source_id, target_id, relation_type): pass

    @abstractmethod
    def list_relations(self, source_id=None, target_id=None, relation_type=None): pass

    @abstractmethod
    def record_access(self, memory_id, request): pass

    @abstractmethod
    def list_versions(self, memory_key, tenant_id, user_id, agent_id): pass

    @abstractmethod
    def update_processing_task(self, event_id, stage, status, error=None): pass
