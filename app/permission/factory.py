"""Permission subsystem composition."""

from dataclasses import dataclass

from app.permission.api.service import PermissionService
from app.permission.config import PermissionConfig
from app.permission.ports.evaluator import PolicyEvaluatorPort
from app.permission.ports.policy_provider import PolicyProviderPort
from app.permission.runtime import PermissionRuntime


@dataclass(frozen=True)
class PermissionSystem:
    service: PermissionService
    runtime: PermissionRuntime
    config: PermissionConfig

    def evaluate(self, request):
        return self.service.evaluate(request)


def _provider_from_config(config: PermissionConfig) -> PolicyProviderPort:
    if config.provider == "local_file":
        from app.permission.providers.local_file import LocalFilePolicyProvider

        return LocalFilePolicyProvider(config.policy_root)
    raise ValueError(f"Unsupported permission provider: {config.provider}")


def build_permission(
    provider: PolicyProviderPort | None = None,
    config: PermissionConfig | None = None,
    evaluator: PolicyEvaluatorPort | None = None,
) -> PermissionSystem:
    config = config or PermissionConfig()
    provider = provider or _provider_from_config(config)
    runtime = PermissionRuntime(provider, config)
    service = PermissionService(runtime, evaluator=evaluator, config=config)
    return PermissionSystem(service=service, runtime=runtime, config=config)
