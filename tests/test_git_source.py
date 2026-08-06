import tempfile
import unittest
from pathlib import Path

from app.capabilities.catalog import CapabilityCatalog
from app.capabilities.models import CapabilityDefinition
from app.capabilities.repository import InMemoryCapabilityRepository
from app.manifest.loader import ManifestLoader
from app.manifest.parser import ManifestParser
from app.manifest.validator import ManifestValidator
from app.registry.models import Policy
from app.registry.service import AgentRegistry
from app.registry.storage import InMemoryAgentRepository
from app.sources.builtin import BuiltinAgentSource
from app.sources.factory import AgentSourceFactory
from app.sources.git import GitAgentSource, GitSourceError
from app.tools.crm import CRMTool
from app.tools.registry import ToolRegistry


def manifest_text(agent_id, capability="customer_analysis"):
    return f"""
agent:
  id: {agent_id}
  version: "0.2"
  name: {agent_id}
  description: Test Agent
  owner:
    team: test_team
capabilities:
  - {capability}
tools:
  allowed:
    - crm_query
memory:
  read: [customer]
  write: []
policy:
  ref: test_policy
runtime:
  model: deepseek-chat
"""


class StubLLM:
    def chat(self, messages, **kwargs):
        return '{"action":"finish","output":"done"}'


class GitAgentSourceTest(unittest.TestCase):
    def setUp(self):
        self.catalog = CapabilityCatalog(InMemoryCapabilityRepository())
        self.catalog.register(
            CapabilityDefinition(
                capability_id="customer_analysis",
                name="Customer analysis",
                description="Analyze customers",
                allowed_tools=["crm_query"],
            )
        )
        self.tools = ToolRegistry()
        self.tools.register("crm_query", CRMTool())
        self.registry = AgentRegistry(
            InMemoryAgentRepository(),
            capability_catalog=self.catalog,
        )
        self.registry.register_policy(Policy(policy_id="test_policy"))
        self.parser = ManifestParser()
        self.validator = ManifestValidator(
            self.catalog,
            self.tools,
            self.registry,
        )
        self.loader = ManifestLoader(
            self.parser,
            self.validator,
            self.registry,
            StubLLM(),
        )

    def write_manifest(self, root, agent_id, capability="customer_analysis"):
        path = Path(root) / "agents" / agent_id / "agent.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            manifest_text(agent_id, capability),
            encoding="utf-8",
        )
        return path

    def source(self, path):
        return GitAgentSource(
            repo_path=path,
            parser=self.parser,
            validator=self.validator,
            loader=self.loader,
        )

    def test_loads_agent_from_local_repository(self):
        with tempfile.TemporaryDirectory() as repository:
            self.write_manifest(repository, "sales_agent")
            loaded = self.source(repository).load(self.registry)

        self.assertEqual(1, len(loaded))
        self.assertIs(
            loaded[0],
            self.registry.get("sales_agent", "0.2"),
        )

    def test_loads_multiple_agents(self):
        with tempfile.TemporaryDirectory() as repository:
            self.write_manifest(repository, "sales_agent")
            self.write_manifest(repository, "finance_agent")
            loaded = self.source(repository).load(self.registry)

        self.assertEqual(
            ["finance_agent", "sales_agent"],
            sorted(agent.agent_id for agent in loaded),
        )

    def test_invalid_manifest_does_not_block_valid_agents(self):
        with tempfile.TemporaryDirectory() as repository:
            self.write_manifest(repository, "sales_agent")
            self.write_manifest(
                repository,
                "finance_agent",
                capability="unknown_capability",
            )
            source = self.source(repository)
            loaded = source.load(self.registry)

        self.assertEqual(["sales_agent"], [agent.agent_id for agent in loaded])
        self.assertEqual(1, len(source.failures))
        self.assertIn("Unknown capability", source.failures[0].error)
        with self.assertRaises(KeyError):
            self.registry.get("finance_agent", "0.2")

    def test_missing_repository_fails_the_source(self):
        source = self.source("/tmp/nonexistent-agent-repository-v051")
        with self.assertRaisesRegex(GitSourceError, "does not exist"):
            source.load(self.registry)

    def test_source_factory_supports_builtin_and_git_config(self):
        factory = AgentSourceFactory(
            llm=StubLLM(),
            catalog=self.catalog,
            tool_registry=self.tools,
            agent_registry=self.registry,
        )
        self.assertIsInstance(
            factory.create({"agent_source": {"type": "builtin"}}),
            BuiltinAgentSource,
        )

        with tempfile.TemporaryDirectory() as repository:
            source = factory.create(
                {
                    "agent_source": {
                        "type": "git",
                        "path": repository,
                    }
                }
            )
            self.assertIsInstance(source, GitAgentSource)


if __name__ == "__main__":
    unittest.main()
