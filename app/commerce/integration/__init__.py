"""External commerce integration boundary (Phase 12.9).

Standard access layer between the Enterprise Agent Platform and external
commerce systems (Amazon / TikTok / Shopify / ERP / CRM).  Connectors handle
transport only; Adapters map External DTO -> Canonical; Credentials are secret
references only; the Canonical Commerce Model remains the sole business
language.
"""

from app.commerce.integration.errors import (
    AdapterError,
    ConnectorError,
    CredentialError,
    ExternalAuthenticationError,
    ExternalNotFound,
    ExternalRequestError,
    ExternalUnavailable,
    IntegrationError,
    InvalidExternalResponse,
    RateLimitError,
    SecretResolutionError,
    UnknownAdapterError,
    UnknownConnectorError,
)
from app.commerce.integration.credentials import (
    Credential,
    CredentialProvider,
    SecretProvider,
    SecretReference,
)
from app.commerce.integration.credentials.provider import (
    InMemoryCredentialProvider,
    InMemorySecretProvider,
)
from app.commerce.integration.connectors import (
    AmazonConnector,
    BaseConnector,
    RetryPolicy,
    TikTokConnector,
)
from app.commerce.integration.adapters import (
    AmazonAdapter,
    BaseAdapter,
    TikTokAdapter,
)
from app.commerce.integration.registry import (
    AdapterRegistry,
    ConnectorRegistry,
)
from app.commerce.integration.sync import (
    ConnectorBinding,
    IntegrationSyncRuntime,
    SyncScheduler,
)

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
    "SecretReference",
    "Credential",
    "CredentialProvider",
    "SecretProvider",
    "InMemoryCredentialProvider",
    "InMemorySecretProvider",
    "BaseConnector",
    "RetryPolicy",
    "AmazonConnector",
    "TikTokConnector",
    "BaseAdapter",
    "AmazonAdapter",
    "TikTokAdapter",
    "ConnectorRegistry",
    "AdapterRegistry",
    "ConnectorBinding",
    "IntegrationSyncRuntime",
    "SyncScheduler",
]
