"""In-memory policy lookup boundary for Agent invocation governance."""


class AgentInvocationPolicyStore:
    def __init__(self, policies=()):
        self._policies = {}
        for policy in policies:
            self.register(policy)

    def register(self, policy):
        key = (policy.source_agent_id, policy.target_agent_id)
        if key in self._policies:
            raise ValueError(f"Agent invocation policy already exists: {key}")
        self._policies[key] = policy
        return policy

    def get(self, source_agent_id, target_agent_id):
        return self._policies.get((source_agent_id, target_agent_id))
