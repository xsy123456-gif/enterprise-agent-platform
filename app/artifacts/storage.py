from app.artifacts.repository import ArtifactRepository


class InMemoryArtifactRepository(ArtifactRepository):
    """Development storage; artifact contracts do not depend on this backend."""

    def __init__(self):
        self._artifacts = {}

    def save(self, artifact):
        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None and existing != artifact:
            raise ValueError(f"Artifact already exists: {artifact.artifact_id}")
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def get(self, artifact_id):
        return self._artifacts.get(artifact_id)

    def list_versions(self, agent_id):
        return sorted(
            [item for item in self._artifacts.values() if item.agent_id == agent_id],
            key=lambda item: item.agent_version,
        )

    def delete(self, artifact_id):
        return self._artifacts.pop(artifact_id, None)
