from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryScope:
    tenant_id: str
    user_id: str
    agent_id: str
    department_id: str | None = None

    def __post_init__(self):
        for field_name in ("tenant_id", "user_id", "agent_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
            object.__setattr__(self, field_name, value.strip())
        department_id = self.department_id
        if department_id is not None:
            if not isinstance(department_id, str) or not department_id.strip():
                raise ValueError("department_id must be None or a non-empty string")
            object.__setattr__(self, "department_id", department_id.strip())
