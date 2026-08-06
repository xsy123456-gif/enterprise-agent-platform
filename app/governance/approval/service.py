from app.governance.approval.models import ApprovalRequest, ApprovalStatus
from app.governance.events import LifecycleEvent


class ApprovalService:
    def __init__(self, repository, lifecycle_service, event_publisher=None):
        self.repository = repository
        self.lifecycle_service = lifecycle_service
        self.event_publisher = event_publisher

    def create_request(self, agent_id, version, requester, approval_channel="manual", comment=None, role="developer"):
        self.lifecycle_service.request_review(
            agent_id, version, requester=requester,
            approval_channel=approval_channel, comment=comment, role=role,
        )
        request = ApprovalRequest(agent_id, version, requester, approval_channel, comment=comment)
        self.repository.add(request)
        self._publish("agent.review_requested", request, requester)
        return request

    def approve(self, approval_id, reviewer, comment=None, role="admin"):
        request = self._get(approval_id)
        if request.status != ApprovalStatus.PENDING.value:
            raise ValueError("Approval request is not pending")
        self.lifecycle_service.approve(request.agent_id, request.version, reviewer=reviewer, comment=comment, role=role)
        request.status = ApprovalStatus.APPROVED.value
        request.reviewer = reviewer
        request.comment = comment
        self.repository.update(request)
        self._publish("agent.approved", request, reviewer)
        return request

    def reject(self, approval_id, reviewer, comment=None, role="admin"):
        request = self._get(approval_id)
        if request.status != ApprovalStatus.PENDING.value:
            raise ValueError("Approval request is not pending")
        self.lifecycle_service._authorize(
            reviewer, role, "reject_agent", request.agent_id, request.version,
        )
        request.status = ApprovalStatus.REJECTED.value
        request.reviewer = reviewer
        request.comment = comment
        self.repository.update(request)
        self._publish("agent.rejected", request, reviewer)
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
