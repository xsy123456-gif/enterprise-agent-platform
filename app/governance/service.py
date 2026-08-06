from app.governance.events import LifecycleEvent
from app.governance.models import AgentLifecycle, ApprovalRequest, utc_now
from app.governance.policy import LifecyclePolicy


class AgentLifecycleService:
    def __init__(self, repository, event_publisher=None, policy=None, governance_engine=None):
        self.repository = repository
        self.event_publisher = event_publisher
        self.policy = policy or LifecyclePolicy()
        self.governance_engine = governance_engine

    def create(self, agent_id, version, owner="", user_id="system", role="system"):
        self._authorize(user_id, role, "create_agent", agent_id, version)
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
        role="developer",
    ):
        lifecycle = self.get(agent_id, version)
        self._authorize(requester, role, "submit_review", agent_id, version)
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

    def approve(self, agent_id, version, reviewer="admin", comment=None, role="admin"):
        lifecycle = self.get(agent_id, version)
        self._authorize(reviewer, role, "approve_agent", agent_id, version)
        self._transition(lifecycle, "approved", reviewer)
        lifecycle.approved_by = reviewer
        lifecycle.approval_time = utc_now()
        self.repository.update(lifecycle)
        self._publish("agent.approved", lifecycle, reviewer)
        return lifecycle

    def activate(self, agent_id, version, operator="admin", role="admin"):
        self._authorize(operator, role, "activate_agent", agent_id, version)
        return self._change(agent_id, version, "active", operator, "agent.activated")

    def suspend(self, agent_id, version, operator="admin", role="admin"):
        self._authorize(operator, role, "suspend_agent", agent_id, version)
        return self._change(agent_id, version, "suspended", operator, "agent.suspended")

    def deprecate(self, agent_id, version, operator="admin", role="admin"):
        self._authorize(operator, role, "deprecate_agent", agent_id, version)
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

    def _authorize(self, user_id, role, action, agent_id, version):
        if self.governance_engine is None:
            return
        decision = self.governance_engine.check({
            "user_id": user_id,
            "role": role,
            "action": action,
            "agent_id": agent_id,
            "version": version,
        })
        if not decision.allowed:
            raise PermissionError(f"Governance policy denied {action}: {decision.reason}")
