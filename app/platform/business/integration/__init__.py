"""Integration subpackage (Phase 16.5)."""

from app.platform.business.integration.connector import (
    DOMAIN_COMMERCE,
    DOMAIN_CRM,
    DOMAIN_ERP,
    DOMAIN_FINANCE,
    EnterpriseConnector,
    NetSuiteConnector,
    SAPConnector,
    SalesforceConnector,
)
from app.platform.business.integration.registry import EnterpriseIntegrationRegistry

__all__ = [
    "EnterpriseConnector",
    "SalesforceConnector",
    "SAPConnector",
    "NetSuiteConnector",
    "EnterpriseIntegrationRegistry",
    "DOMAIN_COMMERCE",
    "DOMAIN_CRM",
    "DOMAIN_ERP",
    "DOMAIN_FINANCE",
]
