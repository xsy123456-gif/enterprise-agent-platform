from abc import ABC, abstractmethod


class CapabilityRepository(ABC):
    @abstractmethod
    def add(self, capability):
        pass

    @abstractmethod
    def get(self, capability_id):
        pass

    @abstractmethod
    def list(self):
        pass


class InMemoryCapabilityRepository(CapabilityRepository):
    def __init__(self):
        self._capabilities = {}

    def add(self, capability):
        if capability.capability_id in self._capabilities:
            raise ValueError(
                f"Capability already registered: {capability.capability_id}"
            )
        self._capabilities[capability.capability_id] = capability

    def get(self, capability_id):
        return self._capabilities.get(capability_id)

    def list(self):
        return list(self._capabilities.values())
