from abc import ABC, abstractmethod


class PolicyRepository(ABC):
    @abstractmethod
    def add(self, policy):
        pass

    @abstractmethod
    def get(self, policy_id):
        pass


class InMemoryPolicyRepository(PolicyRepository):
    def __init__(self):
        self._policies = {}

    def add(self, policy):
        if policy.policy_id in self._policies:
            raise ValueError(f"Policy already exists: {policy.policy_id}")
        self._policies[policy.policy_id] = policy

    def get(self, policy_id):
        return self._policies.get(policy_id)
