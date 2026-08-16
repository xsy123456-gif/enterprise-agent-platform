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
    IntegrationError,
    RateLimitError,
    SecretResolutionError,
    UnknownAdapterError,
    UnknownConnectorError,
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
]
