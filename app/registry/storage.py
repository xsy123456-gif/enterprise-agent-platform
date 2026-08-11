from app.registry.repository import AgentRepository


class InMemoryAgentRepository(AgentRepository):
    def __init__(self):
        self._agents = {}
        self._policies = {}
        self._tool_bindings = []

    def add_agent(self, agent):
        key = (agent.agent_id, agent.version)
        if key in self._agents:
            raise ValueError(f"Agent already registered: {agent.registry_key}")
        self._agents[key] = agent

    def get_agent(self, agent_id, version):
        return self._agents.get((agent_id, version))

    def list_agents(self, agent_id=None):
        agents = list(self._agents.values())
        if agent_id is not None:
            agents = [agent for agent in agents if agent.agent_id == agent_id]
        return agents

    def update_agent(self, agent):
        key = (agent.agent_id, agent.version)
        if key not in self._agents:
            raise KeyError(f"Agent not found: {agent.registry_key}")
        self._agents[key] = agent

    def add_policy(self, policy):
        if policy.policy_id in self._policies:
            raise ValueError(f"Policy already registered: {policy.policy_id}")
        self._policies[policy.policy_id] = policy

    def get_policy(self, policy_id):
        return self._policies.get(policy_id)

    def add_tool_binding(self, binding):
        duplicate = any(
            item.capability_id == binding.capability_id
            and item.tool_name == binding.tool_name
            for item in self._tool_bindings
        )
        if duplicate:
            raise ValueError(
                "Tool binding already registered: "
                f"{binding.capability_id}:{binding.tool_name}"
            )
        self._tool_bindings.append(binding)

    def list_tool_bindings(self, capability_id=None):
        if capability_id is None:
            return list(self._tool_bindings)
        return [
            binding
            for binding in self._tool_bindings
            if binding.capability_id == capability_id
        ]
