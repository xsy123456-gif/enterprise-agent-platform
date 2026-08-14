"""Identity subsystem composition.

``build_identity`` assembles a provider (the only place external identity
sources may appear) behind ``IdentityProviderPort`` and returns an
``IdentitySystem``.
"""

from dataclasses import dataclass

from app.identity.api.service import IdentityService
from app.identity.config import IdentityConfig
from app.identity.context.builder import AccessContextBuilder
from app.identity.ports.provider import IdentityProviderPort
from app.identity.runtime import IdentityRuntime
from app.identity.validation.validator import IdentityValidator


@dataclass(frozen=True)
class IdentitySystem:
    service: IdentityService
    runtime: IdentityRuntime
    config: IdentityConfig

    def build_access_context(self, user_id):
        return self.service.build_access_context(user_id)


def _provider_from_config(config: IdentityConfig) -> IdentityProviderPort:
    if config.provider == "local_file":
        from app.identity.providers.local_file import LocalFileIdentityProvider

        return LocalFileIdentityProvider(config.data_root)
    raise ValueError(f"Unsupported identity provider: {config.provider}")


def build_identity(
    provider: IdentityProviderPort | None = None,
    config: IdentityConfig | None = None,
    validator: IdentityValidator | None = None,
    builder: AccessContextBuilder | None = None,
) -> IdentitySystem:
    """Assemble the Identity subsystem."""
    config = config or IdentityConfig()
    provider = provider or _provider_from_config(config)
    service = IdentityService(
        provider=provider,
        validator=validator or IdentityValidator(fail_closed=config.fail_closed),
        builder=builder or AccessContextBuilder(),
    )
    runtime = IdentityRuntime(service=service, provider=provider)
    return IdentitySystem(service=service, runtime=runtime, config=config)
