from app.agents.definition import AgentDefinition
from app.agents.manifest import ManifestAgent
from app.registry.models import Agent, AgentStatus


class ManifestLoader:
    def __init__(self, parser, validator, registry, llm):
        self.parser = parser
        self.validator = validator
        self.registry = registry
        self.llm = llm

    def load(self, path):
        manifest = self.parser.parse(path)
        return self.load_manifest(manifest)

    def load_manifest(self, manifest):
        self.validator.validate(manifest)
        definition = self._to_definition(manifest)
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
    def _to_definition(manifest):
        memory_read = list(manifest.memory_policy.get("read") or [])
        memory_write = list(manifest.memory_policy.get("write") or [])
        return AgentDefinition(
            agent_id=manifest.agent_id,
            version=manifest.version,
            system_prompt=ManifestLoader._build_system_prompt(manifest),
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

    @staticmethod
    def _build_system_prompt(manifest):
        capabilities = ", ".join(manifest.capabilities)
        tools = ", ".join(manifest.tools) or "none"
        return f"""
你是{manifest.name}。

职责：{manifest.description}
业务能力：{capabilities}
允许工具：{tools}

需要工具时只能输出：
{{"action":"tool_call","tool":"工具名称","arguments":{{}}}}

完成当前任务步骤时只能输出：
{{"action":"finish","output":"结果"}}

不得直接执行工具、修改权限或改变运行状态，只能输出上述JSON。
"""
