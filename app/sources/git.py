from dataclasses import dataclass
from pathlib import Path

from app.sources.base import AgentSource


class GitSourceError(RuntimeError):
    pass


@dataclass
class ManifestLoadFailure:
    path: str
    error: str
    error_type: str

    def to_dict(self):
        return {
            "path": self.path,
            "error": self.error,
            "error_type": self.error_type,
        }


class GitAgentSource(AgentSource):
    """Loads Agent manifests from an existing local Git working tree."""

    def __init__(self, repo_path, parser, validator, loader):
        self.repo_path = Path(repo_path).expanduser()
        self.parser = parser
        self.validator = validator
        self.loader = loader
        self.failures = []

    def load(self, registry):
        if not self.repo_path.exists() or not self.repo_path.is_dir():
            raise GitSourceError(
                f"Git Agent repository does not exist: {self.repo_path}"
            )
        if self.loader.registry is not registry:
            raise GitSourceError("ManifestLoader is configured for another Registry")

        self.failures = []
        loaded = []
        for manifest_path in self._manifest_paths():
            try:
                manifest = self.parser.parse(manifest_path)
                self.validator.validate(manifest)
                loaded.append(
                    self.loader.load_manifest(manifest, validate=False)
                )
            except Exception as error:
                self.failures.append(
                    ManifestLoadFailure(
                        path=str(manifest_path),
                        error=str(error),
                        error_type=type(error).__name__,
                    )
                )
        return loaded

    def _manifest_paths(self):
        agents_root = self.repo_path / "agents"
        scan_root = agents_root if agents_root.is_dir() else self.repo_path
        return sorted(
            path
            for path in scan_root.rglob("agent.yaml")
            if ".git" not in path.parts
        )
