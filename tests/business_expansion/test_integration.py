"""Phase 16.5 ERP/CRM Integration tests."""

from app.commerce.integration.credentials.models import Credential, SecretReference
from app.commerce.integration.credentials.provider import InMemorySecretProvider
from app.commerce.ingestion.ports import FetchRequest
from app.platform.business.integration import (
    EnterpriseIntegrationRegistry,
    NetSuiteConnector,
    SAPConnector,
    SalesforceConnector,
)


def _credential(provider):
    return Credential(
        credential_id="c1", tenant_id="company_A", provider=provider,
        secret_ref=SecretReference(reference_id=f"vault/{provider}/token"))


def _secrets(provider):
    return InMemorySecretProvider({f"vault/{provider}/token": "tok"})


def test_salesforce_crm_connector_tagged_crm():
    connector = SalesforceConnector(
        records=[{"id": "r1", "resource": "contact", "external_id": "C1"}],
        credential=_credential("salesforce"), secret_provider=_secrets("salesforce"))
    page = connector.fetch(FetchRequest(resource="CONTACT", mode="FULL_SNAPSHOT"))
    assert page.envelopes[0].payload["domain"] == "crm"


def test_sap_erp_connector_tagged_erp():
    connector = SAPConnector(
        records=[{"id": "r1", "resource": "invoice", "external_id": "I1"}],
        credential=_credential("sap"), secret_provider=_secrets("sap"))
    page = connector.fetch(FetchRequest(resource="INVOICE", mode="FULL_SNAPSHOT"))
    assert page.envelopes[0].payload["domain"] == "erp"


def test_netsuite_finance_connector_tagged_finance():
    connector = NetSuiteConnector(
        records=[{"id": "r1", "resource": "invoice", "external_id": "I1"}],
        credential=_credential("netsuite"), secret_provider=_secrets("netsuite"))
    page = connector.fetch(FetchRequest(resource="INVOICE", mode="FULL_SNAPSHOT"))
    assert page.envelopes[0].payload["domain"] == "finance"


def test_domain_isolation_erp_not_commerce():
    # ERP invoice data carries a finance/erp domain tag — it never enters the
    # Commerce domain directly.
    connector = NetSuiteConnector(
        records=[{"id": "r1", "resource": "invoice", "external_id": "I1"}],
        credential=_credential("netsuite"), secret_provider=_secrets("netsuite"))
    page = connector.fetch(FetchRequest(resource="INVOICE", mode="FULL_SNAPSHOT"))
    assert page.envelopes[0].payload["domain"] != "commerce"


def test_integration_registry_versioned():
    registry = EnterpriseIntegrationRegistry()
    registry.register_class("salesforce", "1.0", SalesforceConnector)
    connector = registry.build("salesforce", credential=_credential("salesforce"),
                               secret_provider=_secrets("salesforce"))
    assert isinstance(connector, SalesforceConnector)
    assert connector.version == "1.0"
