from app.governance.approval.models import ApprovalRequest, ApprovalStatus
from app.governance.events import LifecycleEvent


class ApprovalService:
    def __init__(self, repository, lifecycle_service, event_publisher=None):
        self.repository = repository
        self.lifecycle_service = lifecycle_service
        self.event_publisher = event_publisher

    def create_request(self, agent_id, version, principal=None,
                       approval_channel="manual", comment=None):
        self.lifecycle_service.request_review(
            agent_id, version, principal=principal,
            approval_channel=approval_channel, comment=comment,
        )
        operator = getattr(principal, "principal_id", "unknown") if principal else "system"
        request = ApprovalRequest(agent_id, version, operator, approval_channel, comment=comment)
        self.repository.add(request)
        self._publish("agent.review_requested", request, operator)
        return request

    def approve(self, approval_id, principal=None, comment=None):
        request = self._get(approval_id)
        if request.status != ApprovalStatus.PENDING.value:
            raise ValueError("Approval request is not pending")
        self.lifecycle_service.approve(
            request.agent_id, request.version, principal=principal, comment=comment
        )
        operator = getattr(principal, "principal_id", "unknown") if principal else "system"
        request.status = ApprovalStatus.APPROVED.value
        request.reviewer = operator
        request.comment = comment
        self.repository.update(request)
        self._publish("agent.approved", request, operator)
        return request

    def reject(self, approval_id, principal=None, comment=None):
        request = self._get(approval_id)
        if request.status != ApprovalStatus.PENDING.value:
            raise ValueError("Approval request is not pending")
        operator = getattr(principal, "principal_id", "unknown") if principal else "system"
        request.status = ApprovalStatus.REJECTED.value
        request.reviewer = operator
        request.comment = comment
        self.repository.update(request)
        self._publish("agent.rejected", request, operator)
        return request

    def get(self, approval_id):
        return self._get(approval_id)

    def list(self, agent_id=None, version=None):
        return self.repository.list(agent_id, version)

    def _get(self, approval_id):
        request = self.repository.get(approval_id)
        if request is None:
            raise KeyError(f"Approval not found: {approval_id}")
        return request

    def _publish(self, event_type, request, operator):
        if self.event_publisher is not None:
            self.event_publisher.publish(LifecycleEvent(
                event_type, request.agent_id, request.version, operator,
            ))
