"""Commerce integration errors (Phase 12.9)."""

from app.commerce.contracts.errors import CommerceError


class IntegrationError(CommerceError):
    """Base error for the external commerce integration boundary."""


class ConnectorError(IntegrationError):
    """A connector transport / upstream failure."""


class RateLimitError(ConnectorError):
    """The upstream platform rate-limited the connector."""

    def __init__(self, message="", retry_after=1.0):
        super().__init__(message)
        self.retry_after = retry_after


class AdapterError(IntegrationError):
    """An adapter could not map an external record."""


class CredentialError(IntegrationError):
    """A credential could not be resolved / is missing."""


class SecretResolutionError(CredentialError):
    """The secret provider could not resolve a SecretReference."""


class UnknownConnectorError(IntegrationError):
    """A connector id/version is not registered."""


class UnknownAdapterError(IntegrationError):
    """An adapter id/version is not registered."""


class ExternalAuthenticationError(CredentialError):
    """The upstream rejected the credential (401/403).  Not retryable."""


class ExternalNotFound(IntegrationError):
    """The upstream resource does not exist (404).  Not retryable."""


class ExternalRequestError(IntegrationError):
    """The upstream rejected the request as invalid (400/409).  Not retryable."""


class ExternalUnavailable(ConnectorError):
    """The upstream is temporarily unavailable (502/503/504/timeout/network).
    Retryable."""


class InvalidExternalResponse(IntegrationError):
    """The upstream returned a malformed / unparseable payload."""


__all__ = [
    "IntegrationError",
    "ConnectorError",
    "RateLimitError",
    "AdapterError",
    "CredentialError",
    "SecretResolutionError",
    "UnknownConnectorError",
    "UnknownAdapterError",
    "ExternalAuthenticationError",
    "ExternalNotFound",
    "ExternalRequestError",
    "ExternalUnavailable",
    "InvalidExternalResponse",
]
