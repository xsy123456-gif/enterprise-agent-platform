from app.agents.definition import AgentDefinition
from app.agents.manifest import ManifestAgent
from app.registry.models import Agent, AgentStatus
from app.prompts.loader import PromptLoader


class ManifestLoader:
    def __init__(self, parser, validator, registry, llm, prompt_loader=None):
        self.parser = parser
        self.validator = validator
        self.registry = registry
        self.llm = llm
        self.prompt_loader = prompt_loader or PromptLoader()

    def load(self, path):
        manifest = self.parser.parse(path)
        return self.load_manifest(manifest)

    def load_manifest(self, manifest, validate=True):
        if validate:
            self.validator.validate(manifest)
        definition = self._to_definition(
            manifest, self.prompt_loader.load(manifest)
        )
        instance = ManifestAgent(self.llm, definition)
        registered = Agent(
            agent_id=manifest.agent_id,
            name=manifest.name,
            version=manifest.version,
            description=manifest.description,
            owner=manifest.owner,
            status=AgentStatus.ACTIVE,
            capabilities=list(manifest.capabilities),
            policy_id=manifest.policy_ref,
            instance=instance,
            definition=definition,
        )
        self.registry.register(registered)
        return registered

    @staticmethod
    def _to_definition(manifest, system_prompt):
        memory_read = list(manifest.memory_policy.get("read") or [])
        memory_write = list(manifest.memory_policy.get("write") or [])
        return AgentDefinition(
            agent_id=manifest.agent_id,
            version=manifest.version,
            system_prompt=system_prompt,
            capabilities=list(manifest.capabilities),
            allowed_tools=list(manifest.tools),
            memory_policy=(
                "customer_memory" if "customer" in memory_write else None
            ),
            memory_read=memory_read,
            memory_write=memory_write,
            policy_ref=manifest.policy_ref,
            runtime=dict(manifest.runtime),
        )
