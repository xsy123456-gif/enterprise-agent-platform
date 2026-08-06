from dataclasses import dataclass, field


@dataclass
class CapabilityDefinition:
    capability_id: str
    name: str
    description: str
    examples: list[str] = field(default_factory=list)
    risk_level: str = "low"
    required_permissions: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.capability_id:
            raise ValueError("capability_id is required")
        if not self.name:
            raise ValueError("capability name is required")
        if not self.description:
            raise ValueError("capability description is required")

    def to_dict(self):
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "examples": list(self.examples),
            "risk_level": self.risk_level,
            "required_permissions": list(self.required_permissions),
            "allowed_tools": list(self.allowed_tools),
        }
