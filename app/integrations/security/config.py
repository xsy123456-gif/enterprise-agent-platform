"""Execution security integration configuration."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class SecurityIntegrationConfig:
    principal_source: str = "local"  # "local" | "external_required"
    fail_closed: bool = True

    @classmethod
    def from_environment(cls, environ=None):
        env = dict(os.environ if environ is None else environ)
        return cls(
            principal_source=env.get("PRINCIPAL_SOURCE", "local"),
            fail_closed=env.get("SECURITY_FAIL_CLOSED", "true").lower()
            not in {"false", "0", "no"},
        )
