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
    def delete(self, artifact_id):
        pass
