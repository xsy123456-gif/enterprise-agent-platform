"""Connector base (Phase 12.9.1).

Reuses the frozen Phase 7 transport contract (``ConnectorPort`` / ``FetchRequest``
/ ``FetchResult``) — the integration layer does NOT redefine transport.  A
``BaseConnector`` adds the integration concerns on top: credential-authorized
requests, retry with exponential backoff, and rate-limit retry-after handling.
"""

import time
from abc import abstractmethod
from dataclasses import dataclass

from app.commerce.ingestion.ports import ConnectorPort, FetchRequest, FetchResult
from app.commerce.integration.errors import (
    ConnectorError,
    CredentialError,
    RateLimitError,
)


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    base_seconds: float = 1.0
    factor: float = 2.0


class BaseConnector(ConnectorPort):
    connector_id = ""

    def __init__(self, version="1.0", credential=None, secret_provider=None,
                 retry_policy=None, clock=None, sleep=None):
        self.version = version
        self.credential = credential
        self.secret_provider = secret_provider
        self.retry_policy = retry_policy or RetryPolicy()
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self.audit_log = []

    def fetch(self, request: FetchRequest) -> FetchResult:
        retries = self.retry_policy.max_retries
        delay = self.retry_policy.base_seconds
        last_error = None
        for attempt in range(retries + 1):
            try:
                return self._fetch(request)
            except RateLimitError as error:
                last_error = error
                self.audit_log.append({
                    "attempt": attempt, "kind": "rate_limit",
                    "retry_after": getattr(error, "retry_after", delay),
                })
                if attempt >= retries:
                    break
                self._sleep(getattr(error, "retry_after", delay))
            except ConnectorError as error:
                last_error = error
                self.audit_log.append({"attempt": attempt, "kind": "error"})
                if attempt >= retries:
                    break
                self._sleep(delay)
                delay *= self.retry_policy.factor
        if last_error is not None:
            raise last_error
        raise ConnectorError(f"{self.connector_id}: fetch failed")

    def authorize(self) -> dict:
        """Build an auth header from the credential + secret provider.

        Fail-closed: a connector without a credential cannot call the platform.
        The plain token is fetched here (inside the Connector Runtime) and never
        escapes the connector.
        """
        if self.credential is None:
            raise CredentialError(f"connector {self.connector_id!r} has no credential")
        if self.credential.secret_ref is None or self.secret_provider is None:
            raise CredentialError(
                f"connector {self.connector_id!r} has no resolvable secret"
            )
        token = self.secret_provider.get_secret(self.credential.secret_ref)
        return {"Authorization": f"Bearer {token}"}

    @abstractmethod
    def _fetch(self, request: FetchRequest) -> FetchResult:
        pass


__all__ = ["BaseConnector", "RetryPolicy"]
