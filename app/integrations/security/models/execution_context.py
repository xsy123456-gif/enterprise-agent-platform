"""Execution security context + principal binding models."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionPrincipalBinding:
    principal_id: str
    tenant_id: str
    identity_version_at_admission: str = ""
    security_context_id: str = ""


@dataclass(frozen=True)
class ExecutionSecurityContext:
    security_context_id: str
    principal_binding: ExecutionPrincipalBinding
    request_id: str
    trace_id: str = ""
    admission_metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "admission_metadata", dict(self.admission_metadata or {}))
