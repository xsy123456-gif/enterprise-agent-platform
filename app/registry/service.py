import re

from app.registry.models import AgentStatus


class AgentRegistry:
    def __init__(self, repository, capability_catalog=None):
        self.repository = repository
        self.capability_catalog = capability_catalog

    def register(self, agent):
        self._validate_agent(agent)
        self.repository.add_agent(agent)
        return agent

    def get(self, agent_id, version=None, require_active=True):
        agent = self._find(agent_id, version)
        if agent is None:
            key = agent_id if version is None else f"{agent_id}:{version}"
            raise KeyError(f"Agent not found: {key}")
        if require_active and agent.status != AgentStatus.ACTIVE:
            raise RuntimeError(
                f"Agent is not active: {agent.registry_key} ({agent.status})"
            )
        return agent

    def get_agent(self, agent_id, version=None):
        return self.get(agent_id, version).instance

    def list_agents(self, agent_id=None, capability_id=None, status=None):
        agents = self.repository.list_agents(agent_id)
        if capability_id is not None:
            agents = [
                agent
                for agent in agents
                if capability_id in agent.capabilities
            ]
        if status is not None:
            agents = [agent for agent in agents if agent.status == status]
        return agents

    def list_versions(self, agent_id):
        agents = self.repository.list_agents(agent_id)
        agents.sort(key=lambda agent: self._version_key(agent.version))
        return [agent.version for agent in agents]

    def resolve_by_capability(self, capability_id):
        candidates = self.list_agents(
            capability_id=capability_id,
            status=AgentStatus.ACTIVE,
        )
        if not candidates:
            raise KeyError(
                f"No active Agent provides capability: {capability_id}"
            )

        # Registration order is the initial cross-Agent priority policy.
        # Within that Agent identity, always select its latest active version.
        selected_agent_id = candidates[0].agent_id
        versions = [
            agent for agent in candidates if agent.agent_id == selected_agent_id
        ]
        return max(versions, key=lambda agent: self._version_key(agent.version))

    def set_status(self, agent_id, version, status):
        if status not in AgentStatus.ALL:
            raise ValueError(f"Unsupported agent status: {status}")
        agent = self.get(agent_id, version, require_active=False)
        agent.status = status
        self.repository.update_agent(agent)
        return agent

    def register_capability(self, capability):
        self.repository.add_capability(capability)
        return capability

    def get_capability(self, capability_id):
        capability = self.repository.get_capability(capability_id)
        if capability is None:
            raise KeyError(f"Capability not found: {capability_id}")
        return capability

    def list_capabilities(self):
        return self.repository.list_capabilities()

    def register_policy(self, policy):
        self.repository.add_policy(policy)
        return policy

    def get_policy(self, policy_id):
        policy = self.repository.get_policy(policy_id)
        if policy is None:
            raise KeyError(f"Policy not found: {policy_id}")
        return policy

    def bind_tool(self, binding):
        if self.capability_catalog is not None:
            capability = self.capability_catalog.get(binding.capability_id)
            if (
                capability.allowed_tools
                and binding.tool_name not in capability.allowed_tools
            ):
                raise ValueError(
                    f"Tool is not allowed for capability: {binding.tool_name}"
                )
            if (
                binding.required_permission
                not in capability.required_permissions
            ):
                raise ValueError(
                    "Tool binding permission is not declared by capability: "
                    f"{binding.required_permission}"
                )
        self.repository.add_tool_binding(binding)
        return binding

    def get_tool_bindings(self, capability_id=None):
        return self.repository.list_tool_bindings(capability_id)

    def _find(self, agent_id, version):
        if version is not None:
            return self.repository.get_agent(agent_id, version)

        candidates = [
            agent
            for agent in self.repository.list_agents(agent_id)
            if agent.status == AgentStatus.ACTIVE
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda agent: self._version_key(agent.version))

    @staticmethod
    def _version_key(version):
        return tuple(
            (0, int(part)) if part.isdigit() else (1, part.lower())
            for part in re.findall(r"\d+|[A-Za-z]+", version)
        )

    def _validate_agent(self, agent):
        if not agent.agent_id or not agent.version:
            raise ValueError("agent_id and version are required")
        if agent.status not in AgentStatus.ALL:
            raise ValueError(f"Unsupported agent status: {agent.status}")
        if agent.instance is None:
            raise ValueError("Agent instance is required")
        if len(agent.capabilities) != len(set(agent.capabilities)):
            raise ValueError("Agent capabilities must be unique")
        if self.capability_catalog is not None:
            for capability_id in agent.capabilities:
                try:
                    self.capability_catalog.get(capability_id)
                except KeyError as error:
                    raise ValueError(
                        f"Agent references unknown capability: {capability_id}"
                    ) from error
