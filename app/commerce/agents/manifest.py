"""Agent capability manifest (Phase 12.1).

``AgentManifest`` declares an agent's capability surface: the skills it may
route to and the platform capabilities it requires.  ``required_capabilities``
is a *declaration* only — actual authorization flows through
Identity -> Permission -> Governance, never through the manifest.
"""

from dataclasses import dataclass

from app.commerce.agents.errors import AgentManifestError


@dataclass(frozen=True)
class AgentManifest:
    agent_id: str
    version: str
    description: str
    skills: tuple[str, ...] = ()
    default_skill: str = ""
    required_capabilities: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "skills", tuple(self.skills or ()))
        object.__setattr__(
            self, "required_capabilities", tuple(self.required_capabilities or ())
        )
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not self.description:
            raise ValueError("agent description is required")

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "description": self.description,
            "skills": list(self.skills),
            "default_skill": self.default_skill,
            "required_capabilities": list(self.required_capabilities),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentManifest":
        if not isinstance(data, dict):
            raise AgentManifestError("manifest must be a mapping")
        try:
            return cls(
                agent_id=data["agent_id"],
                version=str(data.get("version", "1.0")),
                description=data.get("description", ""),
                skills=tuple(data.get("skills", ())),
                default_skill=data.get("default_skill", ""),
                required_capabilities=tuple(data.get("required_capabilities", ())),
            )
        except (KeyError, TypeError) as error:
            raise AgentManifestError(f"invalid manifest: {error}")

    @classmethod
    def from_yaml(cls, text: str) -> "AgentManifest":
        import yaml
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise AgentManifestError(f"unable to parse manifest YAML: {error}")
        return cls.from_dict(data or {})


__all__ = ["AgentManifest"]
