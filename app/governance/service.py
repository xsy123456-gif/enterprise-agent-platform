from app.governance.authorization import (
    LifecycleAuthorizationPort,
    SYSTEM_PRINCIPAL,
)
from app.governance.events import LifecycleEvent
from app.governance.models import AgentLifecycle, ApprovalRequest, utc_now
from app.governance.policy import LifecyclePolicy


class AgentLifecycleService:
    def __init__(self, repository, event_publisher=None, policy=None, authorization=None):
        self.repository = repository
        self.event_publisher = event_publisher
        self.policy = policy or LifecyclePolicy()
        self.authorization = authorization

    def create(self, agent_id, version, owner="", principal=None):
        self._authorize(principal, "create", agent_id, version)
        lifecycle = AgentLifecycle(
            agent_id=agent_id,
            version=version,
            owner=owner,
        )
        self.repository.add(lifecycle)
        self._publish("agent.created", lifecycle, self._operator(principal))
        return lifecycle

    def get(self, agent_id, version):
        lifecycle = self.repository.get(agent_id, version)
        if lifecycle is None:
            raise KeyError(f"Lifecycle not found: {agent_id}:{version}")
        return lifecycle

    def request_review(
        self,
        agent_id,
        version,
        principal=None,
        approval_channel="manual",
        comment=None,
    ):
        lifecycle = self.get(agent_id, version)
        self._authorize(principal, "submit_review", agent_id, version)
        operator = self._operator(principal)
        self._transition(lifecycle, "validating", operator)
        self._publish("agent.validation_passed", lifecycle, operator)
        self._transition(lifecycle, "reviewing", operator)
        request = ApprovalRequest(
            agent_id=agent_id,
            version=version,
            requester=operator,
            approval_channel=approval_channel,
            comment=comment,
        )
        self.repository.add_approval(request)
        self._publish("agent.review_requested", lifecycle, operator)
        return request

    def approve(self, agent_id, version, principal=None, comment=None):
        lifecycle = self.get(agent_id, version)
        self._authorize(principal, "approve", agent_id, version)
        operator = self._operator(principal)
        self._transition(lifecycle, "approved", operator)
        lifecycle.approved_by = operator
        lifecycle.approval_time = utc_now()
        self.repository.update(lifecycle)
        self._publish("agent.approved", lifecycle, operator)
        return lifecycle

    def activate(self, agent_id, version, principal=None):
        self._authorize(principal, "activate", agent_id, version)
        return self._change(agent_id, version, "active",
                            self._operator(principal), "agent.activated")

    def suspend(self, agent_id, version, principal=None):
        self._authorize(principal, "suspend", agent_id, version)
        return self._change(agent_id, version, "suspended",
                            self._operator(principal), "agent.suspended")

    def deprecate(self, agent_id, version, principal=None):
        self._authorize(principal, "deprecate", agent_id, version)
        return self._change(agent_id, version, "deprecated",
                            self._operator(principal), "agent.deprecated")

    def archive(self, agent_id, version, principal=None):
        self._authorize(principal, "archive", agent_id, version)
        return self._change(agent_id, version, "archived",
                            self._operator(principal), "agent.archived")

    def _change(self, agent_id, version, target, operator, event_type):
        lifecycle = self.get(agent_id, version)
        self._transition(lifecycle, target, operator)
        self._publish(event_type, lifecycle, operator)
        return lifecycle

    def _transition(self, lifecycle, target, operator):
        self.policy.validate(lifecycle.status, target)
        lifecycle.status = target
        lifecycle.updated_at = utc_now()
        self.repository.update(lifecycle)

    def _publish(self, event_type, lifecycle, operator):
        if self.event_publisher is not None:
            self.event_publisher.publish(
                LifecycleEvent(
                    event_type=event_type,
                    agent_id=lifecycle.agent_id,
                    version=lifecycle.version,
                    operator=operator,
                )
            )

    def _authorize(self, principal, action, agent_id, version):
        if principal is None:
            principal = SYSTEM_PRINCIPAL
        if self.authorization is None:
            raise PermissionError(f"Lifecycle authorization required for {action}")
        if not self.authorization.authorize(principal, action, agent_id, version):
            raise PermissionError(f"Permission denied for lifecycle {action}")

    @staticmethod
    def _operator(principal):
        if principal is None:
            return SYSTEM_PRINCIPAL.principal_id
        return getattr(principal, "principal_id", "unknown")
