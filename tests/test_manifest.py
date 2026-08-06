import tempfile
import unittest
from pathlib import Path

from app.capabilities.catalog import CapabilityCatalog
from app.capabilities.models import CapabilityDefinition
from app.capabilities.repository import InMemoryCapabilityRepository
from app.manifest.loader import ManifestLoader
from app.manifest.parser import ManifestParser
from app.manifest.validator import ManifestValidationError, ManifestValidator
from app.registry.models import Policy
from app.registry.service import AgentRegistry
from app.registry.storage import InMemoryAgentRepository
from app.tools.crm import CRMTool
from app.tools.registry import ToolRegistry
from app.prompts.loader import PromptLoadError, PromptLoader


VALID_MANIFEST = """
agent:
  id: sales_agent
  version: "0.2"
  name: Sales Agent
  description: Analyze customers
  owner:
    team: sales_operations
prompt:
  system: prompts/system.md
capabilities:
  - customer_analysis
tools:
  allowed:
    - crm_query
memory:
  read: [customer]
  write: [customer]
policy:
  ref: sales_agent_policy
runtime:
  model: deepseek-chat
"""


class StubLLM:
    def chat(self, messages, **kwargs):
        return '{"action":"finish","output":"done"}'


class ManifestTest(unittest.TestCase):
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
        self.registry.register_policy(
            Policy(policy_id="sales_agent_policy")
        )
        self.validator = ManifestValidator(
            self.catalog,
            self.tools,
            self.registry,
        )

    def parse(self, content):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "agent.yaml"
        path.write_text(content, encoding="utf-8")
        prompt = Path(directory.name) / "prompts" / "system.md"
        prompt.parent.mkdir()
        prompt.write_text("You are a sales analyst.", encoding="utf-8")
        return ManifestParser().parse(path)

    def test_parser_converts_yaml_to_manifest(self):
        manifest = self.parse(VALID_MANIFEST)
        self.assertEqual("sales_agent", manifest.agent_id)
        self.assertEqual("0.2", manifest.version)
        self.assertEqual(["customer_analysis"], manifest.capabilities)
        self.assertEqual(["crm_query"], manifest.tools)
        self.assertEqual("sales_operations", manifest.owner)
        self.assertEqual("prompts/system.md", manifest.system_prompt_ref)

    def test_loader_registers_manifest_agent(self):
        manifest = self.parse(VALID_MANIFEST)
        loader = ManifestLoader(
            ManifestParser(),
            self.validator,
            self.registry,
            StubLLM(),
        )
        registered = loader.load_manifest(manifest)

        self.assertIs(registered, self.registry.get("sales_agent", "0.2"))
        self.assertEqual("sales_agent", registered.definition.agent_id)
        self.assertEqual(["crm_query"], registered.definition.allowed_tools)
        self.assertEqual("deepseek-chat", registered.definition.runtime["model"])
        self.assertEqual("You are a sales analyst.", registered.definition.system_prompt)

    def test_prompt_must_stay_inside_agent_directory(self):
        manifest = self.parse(
            VALID_MANIFEST.replace("prompts/system.md", "../system.md")
        )
        with self.assertRaisesRegex(PromptLoadError, "inside"):
            PromptLoader().load(manifest)

    def test_unknown_capability_is_rejected(self):
        manifest = self.parse(
            VALID_MANIFEST.replace("customer_analysis", "unknown_capability")
        )
        with self.assertRaisesRegex(
            ManifestValidationError, "Unknown capability"
        ):
            self.validator.validate(manifest)

    def test_unknown_tool_is_rejected(self):
        manifest = self.parse(
            VALID_MANIFEST.replace("crm_query", "unknown_tool")
        )
        with self.assertRaisesRegex(ManifestValidationError, "Unknown tool"):
            self.validator.validate(manifest)

    def test_unknown_policy_and_runtime_model_are_rejected(self):
        manifest = self.parse(
            VALID_MANIFEST.replace("sales_agent_policy", "unknown_policy")
        )
        with self.assertRaisesRegex(ManifestValidationError, "Unknown policy"):
            self.validator.validate(manifest)

        manifest = self.parse(
            VALID_MANIFEST.replace("deepseek-chat", "unsupported-model")
        )
        with self.assertRaisesRegex(
            ManifestValidationError, "Unsupported runtime model"
        ):
            self.validator.validate(manifest)

    def test_runtime_status_and_direct_permissions_are_prohibited(self):
        manifest = self.parse(
            VALID_MANIFEST.replace(
                "version: \"0.2\"",
                'version: "0.2"\n  status: active',
            )
        )
        with self.assertRaisesRegex(ValueError, "Prohibited manifest fields"):
            self.validator.validate(manifest)


if __name__ == "__main__":
    unittest.main()
