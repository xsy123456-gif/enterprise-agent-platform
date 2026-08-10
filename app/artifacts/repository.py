from abc import ABC, abstractmethod


class ArtifactRepository(ABC):
    @abstractmethod
    def save(self, artifact):
        pass

    @abstractmethod
    def get(self, artifact_id):
        pass

    @abstractmethod
    def list_versions(self, agent_id):
        pass

    @abstractmethod
    def get_by_hash(self, artifact_hash):
        pass

    @abstractmethod
    def list_for_agent(self, agent_id, version=None):
        pass

    @abstractmethod
    def exists(self, artifact_hash):
        pass

    @abstractmethod
    def delete(self, artifact_id):
        pass
