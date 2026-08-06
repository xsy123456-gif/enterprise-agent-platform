from abc import ABC, abstractmethod


class AgentRepository(ABC):
    @abstractmethod
    def add_agent(self, agent):
        pass

    @abstractmethod
    def get_agent(self, agent_id, version):
        pass

    @abstractmethod
    def list_agents(self, agent_id=None):
        pass

    @abstractmethod
    def update_agent(self, agent):
        pass

    @abstractmethod
    def add_capability(self, capability):
        pass

    @abstractmethod
    def get_capability(self, capability_id):
        pass

    @abstractmethod
    def list_capabilities(self):
        pass

    @abstractmethod
    def add_policy(self, policy):
        pass

    @abstractmethod
    def get_policy(self, policy_id):
        pass

    @abstractmethod
    def add_tool_binding(self, binding):
        pass

    @abstractmethod
    def list_tool_bindings(self, capability_id=None):
        pass
