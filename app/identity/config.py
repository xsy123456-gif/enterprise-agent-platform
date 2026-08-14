"""Identity subsystem configuration.

Configuration is adapter/strategy internal; concrete users are never
hard-coded here.
"""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class IdentityConfig:
    provider: str = "local_file"
    data_root: str = "data/identity"
    fail_closed: bool = True

    @classmethod
    def from_environment(cls, environ=None):
        env = dict(os.environ if environ is None else environ)
        return cls(
            provider=env.get("IDENTITY_PROVIDER", "local_file"),
            data_root=env.get("IDENTITY_DATA_ROOT", "data/identity"),
            fail_closed=env.get("IDENTITY_FAIL_CLOSED", "true").lower()
            not in {"false", "0", "no"},
        )
