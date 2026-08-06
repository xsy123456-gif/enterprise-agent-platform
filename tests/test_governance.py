import unittest
from contextlib import redirect_stdout
from io import StringIO

from app.events.bus import EventBus
from app.governance.events import EventBusPublisher
from app.governance.events import LifecycleEvent
from app.governance.lifecycle import LifecycleStatus
from app.governance.policy import LifecycleTransitionError
from app.governance.policy import (
    GovernancePolicy, InMemoryPolicyRepository, PolicyDecisionEngine, PolicyRule,
)
from app.governance.approval import ApprovalService, InMemoryApprovalRepository
from app.audit.governance import GovernanceAuditSubscriber
from app.governance.repository import InMemoryLifecycleRepository
from app.governance.service import AgentLifecycleService
from app.registry.models import Agent
from app.registry.service import AgentRegistry
from app.registry.storage import InMemoryAgentRepository


class StubAgent:
    pass


class GovernanceTest(unittest.TestCase):
    def setUp(self):
        self.event_bus = EventBus()
        self.lifecycle = AgentLifecycleService(
            InMemoryLifecycleRepository(),
            EventBusPublisher(self.event_bus),
        )

    def test_full_lifecycle_requires_ordered_transitions(self):
        with redirect_stdout(StringIO()):
            lifecycle = self.lifecycle.create("sales_agent", "0.2", "sales")
        self.assertEqual(LifecycleStatus.DRAFT, lifecycle.status)

        with self.assertRaises(LifecycleTransitionError):
            self.lifecycle.activate("sales_agent", "0.2")

        request = self.lifecycle.request_review(
            "sales_agent",
            "0.2",
            requester="alice",
            approval_channel="git_pr",
        )
        self.assertEqual("git_pr", request.approval_channel)
        self.lifecycle.approve("sales_agent", "0.2", reviewer="bob")
        self.lifecycle.activate("sales_agent", "0.2", operator="bob")
        self.assertEqual(
            LifecycleStatus.ACTIVE,
            self.lifecycle.get("sales_agent", "0.2").status,
        )

        event_types = [event.event_type for event in self.event_bus.events]
        self.assertIn("agent.created", event_types)
        self.assertIn("agent.validation_passed", event_types)
        self.assertIn("agent.review_requested", event_types)
        self.assertIn("agent.approved", event_types)
        self.assertIn("agent.activated", event_types)

    def test_suspend_deprecate_and_archive(self):
        self.lifecycle.create("sales_agent", "0.2")
        self.lifecycle.request_review("sales_agent", "0.2")
        self.lifecycle.approve("sales_agent", "0.2")
        self.lifecycle.activate("sales_agent", "0.2")
        self.lifecycle.suspend("sales_agent", "0.2")
        self.assertEqual(
            LifecycleStatus.SUSPENDED,
            self.lifecycle.get("sales_agent", "0.2").status,
        )

        with self.assertRaises(LifecycleTransitionError):
            self.lifecycle.deprecate("sales_agent", "0.2")

        self.lifecycle = AgentLifecycleService(InMemoryLifecycleRepository())
        self.lifecycle.create("sales_agent", "0.2")
        self.lifecycle.request_review("sales_agent", "0.2")
        self.lifecycle.approve("sales_agent", "0.2")
        self.lifecycle.activate("sales_agent", "0.2")
        self.lifecycle.deprecate("sales_agent", "0.2")
        self.lifecycle.archive("sales_agent", "0.2")
        self.assertEqual(
            LifecycleStatus.ARCHIVED,
            self.lifecycle.get("sales_agent", "0.2").status,
        )

    def test_registry_only_exposes_active_lifecycle_agents(self):
        registry = AgentRegistry(InMemoryAgentRepository())
        registry.attach_lifecycle_service(self.lifecycle)
        agent = Agent(
            agent_id="sales_agent",
            name="Sales",
            version="0.2",
            description="Sales",
            owner="sales",
            status="active",
            capabilities=[],
            instance=StubAgent(),
        )
        with redirect_stdout(StringIO()):
            registry.register(agent)

        self.assertEqual([], registry.get_active_agents())
        self.assertEqual(
            LifecycleStatus.DRAFT,
            self.lifecycle.get("sales_agent", "0.2").status,
        )
        self.lifecycle.request_review("sales_agent", "0.2")
        self.lifecycle.approve("sales_agent", "0.2")
        self.lifecycle.activate("sales_agent", "0.2")
        self.assertEqual([agent], registry.get_active_agents())

    def test_policy_denies_developer_activation(self):
        engine = PolicyDecisionEngine(InMemoryPolicyRepository())
        engine.register(GovernancePolicy(
            "p", "governance", [
                PolicyRule("system", "create_agent", "*", "allow"),
                PolicyRule("developer", "submit_review", "*", "allow"),
                PolicyRule("admin", "approve_agent", "*", "allow"),
                PolicyRule("admin", "activate_agent", "*", "allow"),
            ]
        ))
        lifecycle = AgentLifecycleService(InMemoryLifecycleRepository(), governance_engine=engine)
        lifecycle.create("sales_agent", "0.2")
        lifecycle.request_review("sales_agent", "0.2", requester="dev", role="developer")
        lifecycle.approve("sales_agent", "0.2", reviewer="admin")
        with self.assertRaisesRegex(PermissionError, "activate_agent"):
            lifecycle.activate("sales_agent", "0.2", operator="dev", role="developer")

    def test_approval_rejection_is_recorded_and_not_activatable(self):
        lifecycle = AgentLifecycleService(InMemoryLifecycleRepository())
        lifecycle.create("sales_agent", "0.2")
        approvals = ApprovalService(InMemoryApprovalRepository(), lifecycle)
        request = approvals.create_request("sales_agent", "0.2", "dev")
        approvals.reject(request.approval_id, "admin", "needs changes")
        self.assertEqual("rejected", approvals.get(request.approval_id).status)
        with self.assertRaises(LifecycleTransitionError):
            lifecycle.activate("sales_agent", "0.2")

    def test_governance_audit_subscriber_queries_events(self):
        subscriber = GovernanceAuditSubscriber()
        subscriber.handle(LifecycleEvent("agent.activated", "sales_agent", "0.2", "admin"))
        self.assertEqual(1, len(subscriber.query("sales_agent", event_type="agent.activated")))


if __name__ == "__main__":
    unittest.main()
