"""Permission runtime — policy snapshot lifecycle (start / reload / health)."""

from app.permission.config import PermissionConfig
from app.permission.errors import PermissionUnavailableError
from app.permission.models.snapshot import PolicySnapshot
from app.permission.policy.snapshot import build_snapshot
from app.permission.ports.policy_provider import PolicyProviderPort
from app.permission.validation.policy_validator import validate_policy_set


class PermissionRuntime:
    def __init__(self, provider: PolicyProviderPort, config: PermissionConfig):
        if provider is None:
            raise ValueError("PermissionRuntime requires a PolicyProviderPort")
        self.provider = provider
        self.config = config
        self._snapshot: PolicySnapshot | None = None
        self._error: str | None = None

    def start(self) -> bool:
        return self.reload()

    def reload(self) -> bool:
        try:
            policies = self.provider.load_policies()
            validate_policy_set(policies, self.config)
            self._snapshot = build_snapshot(policies)
            self._error = None
            return True
        except Exception as error:
            # Keep the previous valid snapshot; fail-closed for evaluation.
            self._error = str(error)
            return False

    def get_snapshot(self) -> PolicySnapshot:
        if self._snapshot is None:
            raise PermissionUnavailableError(
                f"no policy snapshot available: {self._error or 'not started'}"
            )
        return self._snapshot

    def health(self) -> dict:
        if self._snapshot is None:
            status = "unhealthy"
        elif self._error:
            status = "degraded"
        else:
            status = "healthy"
        return {
            "name": "permission",
            "status": status,
            "snapshot_loaded": self._snapshot is not None,
            "policy_set_version": (
                self._snapshot.policy_set_version if self._snapshot else None
            ),
            "error": self._error,
        }
