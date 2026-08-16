"""Approval repository port (Phase 18.10).

ApprovalRequest is durable business state: a pending approval must survive a
restart.  The ``ApprovalEngine`` keeps the policy + transition semantics; the
repository only stores/retrieves requests.
"""

from abc import ABC, abstractmethod


class ApprovalRepository(ABC):
    @abstractmethod
    def put(self, request):
        pass

    @abstractmethod
    def get(self, approval_id):
        pass

    @abstractmethod
    def list_pending(self):
        pass


class InMemoryApprovalRepository(ApprovalRepository):

    def __init__(self):
        self._requests = {}

    def put(self, request):
        self._requests[request.approval_id] = request
        return request

    def get(self, approval_id):
        return self._requests.get(approval_id)

    def list_pending(self):
        return [
            r for r in self._requests.values() if r.status == "PENDING"
        ]


__all__ = ["ApprovalRepository", "InMemoryApprovalRepository"]
