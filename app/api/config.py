"""Product API configuration (Phase 18.12)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApiConfig:
    environment: str = "testing"
    docs_enabled: bool = True
    max_body_bytes: int = 256 * 1024
    max_message_chars: int = 16_000
    allowed_origins: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "allowed_origins", tuple(self.allowed_origins or ()))


def api_config_for(environment):
    environment = (environment or "testing").lower()
    if environment == "production":
        return ApiConfig(environment="production", docs_enabled=False)
    return ApiConfig(environment=environment, docs_enabled=True)


__all__ = ["ApiConfig", "api_config_for"]
