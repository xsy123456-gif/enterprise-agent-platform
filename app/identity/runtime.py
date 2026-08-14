"""Identity runtime lifecycle (start / stop / health)."""

from app.identity.api.service import IdentityService


class IdentityRuntime:
    def __init__(self, service: IdentityService | None = None, provider=None):
        self.service = service
        self.provider = provider
        self._started = False

    def start(self):
        self._started = True
        return True

    def stop(self, timeout=None):
        self._started = False
        return True

    def health(self) -> dict:
        return {
            "name": "identity",
            "healthy": self._started,
            "provider": self._provider_health(),
        }

    def _provider_health(self):
        if self.provider is None:
            return {"healthy": False, "error": "not wired"}
        checker = getattr(self.provider, "health", None)
        if callable(checker):
            try:
                return checker()
            except Exception as error:
                return {"healthy": False, "error": str(error)}
        return {"healthy": True}
