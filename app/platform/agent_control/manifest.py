"""Enterprise agent manifest (Phase 13.1).

The manifest is an enterprise asset (not just business config): it carries
ownership, department, security policy and evaluation policy.  It only declares
capabilities; actual authorization is decided by Governance.
"""

from dataclasses import dataclass

from app.platform.agent_control.errors import ManifestError


@dataclass(frozen=True)
class AgentManifest:
    agent_id: str
    version: str
    owner: str = ""
    department: str = ""
    description: str = ""
    skills: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    security_policy: str = ""
    evaluation_policy: str = ""

    def __post_init__(self):
        object.__setattr__(self, "skills", tuple(self.skills or ()))
        object.__setattr__(self, "required_capabilities", tuple(self.required_capabilities or ()))
        if not self.agent_id:
            raise ValueError("agent_id is required")

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "owner": self.owner,
            "department": self.department,
            "description": self.description,
            "skills": list(self.skills),
            "required_capabilities": list(self.required_capabilities),
            "security_policy": self.security_policy,
            "evaluation_policy": self.evaluation_policy,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentManifest":
        if not isinstance(data, dict):
            raise ManifestError("manifest must be a mapping")
        try:
            return cls(
                agent_id=data["agent_id"],
                version=str(data.get("version", "1.0")),
                owner=data.get("owner", ""),
                department=data.get("department", ""),
                description=data.get("description", ""),
                skills=tuple(data.get("skills", ())),
                required_capabilities=tuple(data.get("required_capabilities", ())),
                security_policy=data.get("security_policy", ""),
                evaluation_policy=data.get("evaluation_policy", ""),
            )
        except (KeyError, TypeError) as error:
            raise ManifestError(f"invalid manifest: {error}")

    @classmethod
    def from_yaml(cls, text: str) -> "AgentManifest":
        import yaml
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise ManifestError(f"unable to parse manifest YAML: {error}")
        return cls.from_dict(data or {})


__all__ = ["AgentManifest"]
