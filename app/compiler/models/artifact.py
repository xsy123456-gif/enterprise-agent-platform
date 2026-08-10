from dataclasses import dataclass


@dataclass(frozen=True)
class GraphArtifactMetadata:
    """Metadata carried in IR without importing the Artifact repository."""

    compiler_version: str
