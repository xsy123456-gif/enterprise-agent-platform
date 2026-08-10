from app.artifacts.repository import ArtifactRepository
from app.storage.exceptions import ConflictError


class InMemoryArtifactRepository(ArtifactRepository):
    """Development storage; artifact contracts do not depend on this backend."""

    def __init__(self):
        self._artifacts = {}

    def save(self, artifact):
        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None and existing != artifact:
            raise ConflictError(f"Artifact identity conflict: {artifact.artifact_id}")
        by_hash = self.get_by_hash(getattr(artifact, "artifact_hash", None))
        if by_hash is not None:
            return by_hash
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def get(self, artifact_id):
        return self._artifacts.get(artifact_id)

    def list_versions(self, agent_id):
        return self.list_for_agent(agent_id)

    def get_by_hash(self, artifact_hash):
        if not artifact_hash:
            return None
        return next(
            (item for item in self._artifacts.values()
             if getattr(item, "artifact_hash", None) == artifact_hash),
            None,
        )

    def list_for_agent(self, agent_id, version=None):
        return sorted(
            [item for item in self._artifacts.values()
             if item.agent_id == agent_id
             and (version is None or item.agent_version == version)],
            key=lambda item: item.agent_version,
        )

    def exists(self, artifact_hash):
        return self.get_by_hash(artifact_hash) is not None

    def delete(self, artifact_id):
        return self._artifacts.pop(artifact_id, None)
