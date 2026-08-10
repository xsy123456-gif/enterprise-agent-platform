import unittest

from app.agents.definition import AgentDefinition
from app.capabilities.catalog import CapabilityCatalog
from app.capabilities.models import CapabilityDefinition
from app.capabilities.repository import InMemoryCapabilityRepository
from app.compiler import GraphCompiler
from app.compiler.models import NodeType
from app.compiler.validator import CompilerValidationError
from app.registry.models import Policy
from app.registry.service import AgentRegistry
from app.registry.storage import InMemoryAgentRepository
from app.tools.registry import ToolRegistry


class _Tool:
    pass


class GraphCompilerTest(unittest.TestCase):
    def setUp(self):
        self.catalog = CapabilityCatalog(InMemoryCapabilityRepository())
        self.catalog.register(CapabilityDefinition(
            capability_id="customer_analysis", name="Customer analysis",
            description="Read customer data", allowed_tools=["crm_query"],
        ))
        self.tools = ToolRegistry()
        self.tools.register("crm_query", _Tool())
        self.policies = AgentRegistry(InMemoryAgentRepository())
        self.policies.register_policy(Policy(policy_id="sales_policy"))
        self.definition = AgentDefinition(
            agent_id="sales_agent", version="0.2", system_prompt="You are sales.",
            capabilities=["customer_analysis"], allowed_tools=["crm_query"],
            memory_read=["customer"], policy_ref="sales_policy",
            runtime={"model": "deepseek-chat"},
        )

    def compile(self, definition=None):
        return GraphCompiler().compile(
            definition or self.definition, self.catalog, self.tools, self.policies,
        )

    def test_manifest_definition_to_ir(self):
        graph = self.compile()

        self.assertEqual("sales_agent", graph.agent_id)
        self.assertEqual("0.2", graph.version)
        self.assertEqual("v0.8.0", graph.bindings["compiler_version"])
        self.assertEqual(
            ["start", "governance", "memory", "agent", "tool:crm_query", "end"],
            [node.id for node in graph.nodes],
        )
        self.assertEqual(NodeType.AGENT, next(
            node.type for node in graph.nodes if node.id == "agent"
        ))
        self.assertIn(
            ("agent", "tool:crm_query", "conditional"),
            [(edge.source, edge.target, edge.edge_type) for edge in graph.edges],
        )

    def test_invalid_capability_is_rejected(self):
        definition = AgentDefinition(
            agent_id="sales_agent", version="0.2", system_prompt="prompt",
            capabilities=["does_not_exist"], policy_ref="sales_policy",
        )
        with self.assertRaisesRegex(CompilerValidationError, "Unknown capability"):
            self.compile(definition)

    def test_invalid_tool_binding_is_rejected(self):
        definition = AgentDefinition(
            agent_id="sales_agent", version="0.2", system_prompt="prompt",
            capabilities=["customer_analysis"], allowed_tools=["unknown_tool"],
            policy_ref="sales_policy",
        )
        with self.assertRaisesRegex(CompilerValidationError, "Unknown tool"):
            self.compile(definition)


if __name__ == "__main__":
    unittest.main()
