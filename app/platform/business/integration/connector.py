"""Enterprise ERP/CRM connectors (Phase 16.5).

Extends the Phase 12.9 integration boundary (Connector -> Adapter -> Canonical)
into enterprise systems.  Each connector is tagged with a ``domain`` so ERP
data never leaks into the Commerce Domain — ERP invoices belong to the Finance
Domain, CRM data to the CRM Domain.
"""

from app.commerce.ingestion.envelope import SourceRecordEnvelope
from app.commerce.ingestion.ports import FetchRequest, FetchResult
from app.commerce.integration.connectors.base import BaseConnector

DOMAIN_COMMERCE = "commerce"
DOMAIN_CRM = "crm"
DOMAIN_ERP = "erp"
DOMAIN_FINANCE = "finance"
DOMAINS = frozenset({DOMAIN_COMMERCE, DOMAIN_CRM, DOMAIN_ERP, DOMAIN_FINANCE})


class EnterpriseConnector(BaseConnector):
    domain = ""

    def __init__(self, records=None, version="1.0", **kwargs):
        super().__init__(version=version, **kwargs)
        self.records = list(records or [])

    def _fetch(self, request: FetchRequest) -> FetchResult:
        self.authorize()
        offset = int(request.cursor) if request.cursor and str(request.cursor).isdigit() else 0
        batch = self.records[offset:offset + request.limit]
        next_offset = offset + len(batch)
        return FetchResult(
            envelopes=tuple(self._envelope(r) for r in batch),
            next_cursor=None if next_offset >= len(self.records) else str(next_offset),
            complete=next_offset >= len(self.records),
        )

    def _envelope(self, record):
        return SourceRecordEnvelope(
            source_record_id=record["id"], resource=record["resource"],
            source=self.connector_id, payload={**record, "domain": self.domain},
            source_external_id=record.get("external_id", ""),
            connector_id=self.connector_id, connector_version=self.version,
        )


class SalesforceConnector(EnterpriseConnector):
    connector_id = "salesforce"
    provider = "salesforce"
    domain = DOMAIN_CRM


class SAPConnector(EnterpriseConnector):
    connector_id = "sap_erp"
    provider = "sap"
    domain = DOMAIN_ERP


class NetSuiteConnector(EnterpriseConnector):
    connector_id = "netsuite"
    provider = "netsuite"
    domain = DOMAIN_FINANCE


__all__ = [
    "EnterpriseConnector",
    "SalesforceConnector",
    "SAPConnector",
    "NetSuiteConnector",
    "DOMAIN_COMMERCE",
    "DOMAIN_CRM",
    "DOMAIN_ERP",
    "DOMAIN_FINANCE",
    "DOMAINS",
]
