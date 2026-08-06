from app.governance.events import LifecycleEvent
from app.governance.models import AgentLifecycle, ApprovalRequest, utc_now
from app.governance.policy import LifecyclePolicy


class AgentLifecycleService:
    def __init__(self, repository, event_publisher=None, policy=None):
        self.repository = repository
        self.event_publisher = event_publisher
        self.policy = policy or LifecyclePolicy()

    def create(self, agent_id, version, owner=""):
        lifecycle = AgentLifecycle(
            agent_id=agent_id,
            version=version,
            owner=owner,
        )
        self.repository.add(lifecycle)
        self._publish("agent.created", lifecycle, "system")
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
        requester="system",
        approval_channel="manual",
        comment=None,
    ):
        lifecycle = self.get(agent_id, version)
        self._transition(lifecycle, "validating", requester)
        self._publish("agent.validation_passed", lifecycle, requester)
        self._transition(lifecycle, "reviewing", requester)
        request = ApprovalRequest(
            agent_id=agent_id,
            version=version,
            requester=requester,
            approval_channel=approval_channel,
            comment=comment,
        )
        self.repository.add_approval(request)
        self._publish("agent.review_requested", lifecycle, requester)
        return request

    def approve(self, agent_id, version, reviewer="admin", comment=None):
        lifecycle = self.get(agent_id, version)
        self._transition(lifecycle, "approved", reviewer)
        lifecycle.approved_by = reviewer
        lifecycle.approval_time = utc_now()
        self.repository.update(lifecycle)
        self._publish("agent.approved", lifecycle, reviewer)
        return lifecycle

    def activate(self, agent_id, version, operator="admin"):
        return self._change(agent_id, version, "active", operator, "agent.activated")

    def suspend(self, agent_id, version, operator="admin"):
        return self._change(agent_id, version, "suspended", operator, "agent.suspended")

    def deprecate(self, agent_id, version, operator="admin"):
        return self._change(agent_id, version, "deprecated", operator, "agent.deprecated")

    def archive(self, agent_id, version, operator="admin"):
        return self._change(agent_id, version, "archived", operator, "agent.archived")

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
