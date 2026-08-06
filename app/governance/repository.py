from abc import ABC, abstractmethod


class LifecycleRepository(ABC):
    @abstractmethod
    def add(self, lifecycle):
        pass

    @abstractmethod
    def get(self, agent_id, version):
        pass

    @abstractmethod
    def update(self, lifecycle):
        pass

    @abstractmethod
    def add_approval(self, request):
        pass

    @abstractmethod
    def get_approval(self, request_id):
        pass


class InMemoryLifecycleRepository(LifecycleRepository):
    def __init__(self):
        self._lifecycles = {}
        self._approvals = {}

    def add(self, lifecycle):
        key = (lifecycle.agent_id, lifecycle.version)
        if key in self._lifecycles:
            raise ValueError(f"Lifecycle already exists: {key[0]}:{key[1]}")
        self._lifecycles[key] = lifecycle

    def get(self, agent_id, version):
        return self._lifecycles.get((agent_id, version))

    def update(self, lifecycle):
        key = (lifecycle.agent_id, lifecycle.version)
        if key not in self._lifecycles:
            raise KeyError(f"Lifecycle not found: {key[0]}:{key[1]}")
        self._lifecycles[key] = lifecycle

    def add_approval(self, request):
        self._approvals[request.request_id] = request

    def get_approval(self, request_id):
        return self._approvals.get(request_id)
