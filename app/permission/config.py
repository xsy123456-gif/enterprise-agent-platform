"""Permission subsystem configuration."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class PermissionConfig:
    provider: str = "local_file"
    policy_root: str = "data/permission/policies"
    fail_closed: bool = True
    max_condition_depth: int = 16
    max_condition_nodes: int = 256

    @classmethod
    def from_environment(cls, environ=None):
        env = dict(os.environ if environ is None else environ)

        def _int(key, default):
            try:
                return int(env[key])
            except (KeyError, ValueError):
                return default

        return cls(
            provider=env.get("PERMISSION_PROVIDER", "local_file"),
            policy_root=env.get("PERMISSION_POLICY_ROOT", "data/permission/policies"),
            fail_closed=env.get("PERMISSION_FAIL_CLOSED", "true").lower()
            not in {"false", "0", "no"},
            max_condition_depth=_int("PERMISSION_MAX_CONDITION_DEPTH", 16),
            max_condition_nodes=_int("PERMISSION_MAX_CONDITION_NODES", 256),
        )
