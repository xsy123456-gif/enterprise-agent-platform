import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from app.main import build_runtime
from app.sources.base import AgentSource
from app.sources.builtin import BuiltinAgentSource
from app.registry.models import Agent, AgentStatus, Capability, Policy, ToolBinding
from app.registry.service import AgentRegistry
from app.registry.storage import InMemoryAgentRepository
from app.runtime.action import AgentAction
from app.runtime.context import AgentContext
from app.runtime.engine import RuntimeEngine


class StubAgent:
    def __init__(self, output):
        self.output = output

    def think(self, state):
        return AgentAction.finish_action(self.output)


class StubLLM:
    def chat(self, messages, **kwargs):
        return '{"type":"finish","output":"done"}'


class ToolCallingStubLLM:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return (
                '{"type":"tool","tool":"crm_query",'
                '"input":"customer_A"}'
            )
        return '{"type":"finish","output":"visit prepared"}'


class AgentRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry(InMemoryAgentRepository())

    def make_agent(self, version, status=AgentStatus.ACTIVE):
        return Agent(
            agent_id="sales_agent",
            name="Sales",
            version=version,
            description="Sales agent",
            owner="sales",
            status=status,
            capabilities=["customer_analysis"],
            instance=StubAgent(version),
        )

    def test_same_agent_id_supports_multiple_versions(self):
        self.registry.register(self.make_agent("1.0"))
        self.registry.register(self.make_agent("1.10"))
        self.registry.register(self.make_agent("1.2"))

        self.assertEqual(
            ["1.0", "1.2", "1.10"],
            self.registry.list_versions("sales_agent"),
        )
        self.assertEqual(
            "1.10",
            self.registry.get("sales_agent").version,
        )

    def test_agent_id_and_version_pair_is_unique(self):
        self.registry.register(self.make_agent("1.0"))

        with self.assertRaisesRegex(ValueError, "already registered"):
            self.registry.register(self.make_agent("1.0"))

    def test_inactive_agent_cannot_be_resolved_for_runtime(self):
        self.registry.register(self.make_agent("1.0"))
        self.registry.set_status("sales_agent", "1.0", AgentStatus.INACTIVE)

        with self.assertRaisesRegex(RuntimeError, "not active"):
            self.registry.get_agent("sales_agent", "1.0")

    def test_capability_policy_and_tool_binding_are_managed(self):
        capability = Capability("customer_analysis", "Analyze customers")
        policy = Policy(
            policy_id="sales_policy",
            permission_rules=["crm.customer.read"],
            data_scope=["sales_department"],
            audit_level="full",
        )
        binding = ToolBinding(
            capability_id=capability.capability_id,
            tool_name="crm_query",
            required_permission="crm.customer.read",
            risk_level="low",
        )

        self.registry.register_capability(capability)
        self.registry.register_policy(policy)
        self.registry.bind_tool(binding)

        self.assertIs(capability, self.registry.get_capability("customer_analysis"))
        self.assertIs(policy, self.registry.get_policy("sales_policy"))
        self.assertEqual(
            [binding],
            self.registry.get_tool_bindings("customer_analysis"),
        )

    def test_runtime_resolves_agent_from_registry(self):
        self.registry.register(self.make_agent("1.0"))
        runtime = RuntimeEngine(
            agent_registry=self.registry,
            tool_runner=object(),
        )
        state = AgentContext(
            task="test",
            user_id="user_1",
            role="sales",
            agent_name="sales_agent",
        )

        self.assertEqual("1.0", runtime.run(state))

    def test_builtin_sales_agent_registration(self):
        definitions = BuiltinAgentSource(StubLLM()).load(self.registry)

        registered = self.registry.get("sales_agent", "0.1")
        self.assertEqual([registered], definitions)
        self.assertEqual("销售运营助手", registered.name)
        self.assertEqual(
            ["customer_analysis", "visit_prepare"],
            registered.capabilities,
        )
        self.assertEqual("sales_agent", registered.instance.agent_id)
        self.assertEqual("0.1", registered.instance.version)

    def test_builtin_source_implements_source_contract(self):
        self.assertIsInstance(BuiltinAgentSource(StubLLM()), AgentSource)

    def test_application_flow_keeps_existing_platform_services(self):
        llm = ToolCallingStubLLM()
        with patch("app.main.create_llm", return_value=llm):
            runtime, audit, event_bus = build_runtime()

        state = AgentContext(
            task="prepare customer visit",
            user_id="sales_001",
            role="sales",
            agent_name="sales_agent",
        )
        with redirect_stdout(StringIO()):
            result = runtime.run(state)

        self.assertEqual("visit prepared", result)
        self.assertEqual("crm_query", audit.logs[0]["tool"])
        self.assertEqual("allow", audit.logs[0]["action"])
        self.assertIn(
            "tool_completed",
            [event.event_type for event in event_bus.events],
        )
        self.assertEqual("Tesla", state.tool_results[0]["name"])
        self.assertEqual("completed", state.loop_status)
        self.assertEqual("sales_agent", state.runtime_trace.agent_id)
        self.assertGreaterEqual(state.runtime_trace.llm_calls, 2)
        self.assertEqual(
            "Tesla",
            runtime.memory_service.recall("customer", "Tesla")[0]["key"],
        )


if __name__ == "__main__":
    unittest.main()
