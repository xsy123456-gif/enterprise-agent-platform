from abc import ABC, abstractmethod


class ApprovalRepository(ABC):
    @abstractmethod
    def add(self, request):
        pass

    @abstractmethod
    def get(self, approval_id):
        pass

    @abstractmethod
    def update(self, request):
        pass

    @abstractmethod
    def list(self, agent_id=None, version=None):
        pass


class InMemoryApprovalRepository(ApprovalRepository):
    def __init__(self):
        self._requests = {}

    def add(self, request):
        self._requests[request.approval_id] = request

    def get(self, approval_id):
        return self._requests.get(approval_id)

    def update(self, request):
        if request.approval_id not in self._requests:
            raise KeyError(f"Approval not found: {request.approval_id}")
        self._requests[request.approval_id] = request

    def list(self, agent_id=None, version=None):
        return [r for r in self._requests.values()
                if (agent_id is None or r.agent_id == agent_id)
                and (version is None or r.version == version)]
