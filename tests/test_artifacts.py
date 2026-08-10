import unittest

from app.agents.definition import AgentDefinition
from app.artifacts import (
    AgentLifecycleStatus, CompiledAgentArtifact, InMemoryArtifactRepository,
)
from app.compiler.models import AgentGraphIR, NodeIR, NodeType
from app.registry.models import Agent, AgentStatus
from app.registry.service import AgentRegistry
from app.registry.storage import InMemoryAgentRepository


class ArtifactFoundationTest(unittest.TestCase):
    def graph(self, version="0.1"):
        return AgentGraphIR(
            agent_id="sales_agent", version=version,
            nodes=(NodeIR("start", NodeType.START), NodeIR("end", NodeType.END)),
            edges=(), state_schema={}, bindings={},
        )

    def test_artifact_create_get_and_list_versions(self):
        repository = InMemoryArtifactRepository()
        first = CompiledAgentArtifact.from_ir(self.graph("0.1"), "v0.8.0")
        second = CompiledAgentArtifact.from_ir(self.graph("0.2"), "v0.8.0")
        repository.save(first)
        repository.save(second)

        self.assertIs(first, repository.get(first.artifact_id))
        self.assertEqual(["0.1", "0.2"], [
            item.agent_version for item in repository.list_versions("sales_agent")
        ])
        self.assertIs(second, repository.delete(second.artifact_id))
        self.assertIsNone(repository.get(second.artifact_id))

    def test_registry_stores_artifact_reference(self):
        registry = AgentRegistry(InMemoryAgentRepository())
        definition = AgentDefinition("sales_agent", "0.1", "prompt")
        agent = Agent(
            agent_id="sales_agent", name="Sales", version="0.1", description="",
            owner="sales", status=AgentStatus.DRAFT, capabilities=[],
            instance=object(), definition=definition,
        )
        registry.register(agent)

        stored = registry.attach_artifact("sales_agent", "0.1", "sales_agent:0.1:abc")
        self.assertEqual("sales_agent:0.1:abc", stored.artifact_ref)

    def test_lifecycle_transition_contract(self):
        self.assertEqual(
            AgentLifecycleStatus.COMPILING,
            AgentLifecycleStatus.transition(
                AgentLifecycleStatus.VALIDATING, AgentLifecycleStatus.COMPILING,
            ),
        )
        with self.assertRaisesRegex(ValueError, "Invalid Agent lifecycle transition"):
            AgentLifecycleStatus.transition(
                AgentLifecycleStatus.DRAFT, AgentLifecycleStatus.ACTIVE,
            )


if __name__ == "__main__":
    unittest.main()
