"""HTTP connectors (Phase 18.13.4).

Provider-specific connectors that route reads/writes through the thin
``HttpTransport`` to the simulation services.  Each connector understands only
its provider's paths, query params, DTO field names, pagination token and error
shapes; it wraps every row in a ``SourceRecordEnvelope``.  It never writes
canonical entities and never decides business semantics.

Simulation contract is representative, not vendor-certified.
"""

import uuid

from app.commerce.ingestion.envelope import SourceRecordEnvelope
from app.commerce.ingestion.ports import FetchRequest, FetchResult
from app.commerce.integration.connectors.base import BaseConnector
from app.commerce.integration.errors import (
    ConnectorError,
    ExternalAuthenticationError,
    ExternalNotFound,
    ExternalRequestError,
    ExternalUnavailable,
    InvalidExternalResponse,
    RateLimitError,
)
from app.commerce.integration.transport import HttpTransport

_RETRYABLE_STATUS = frozenset({502, 503, 504})


class HttpConnector(BaseConnector):
    connector_id = ""
    provider = ""
    resource_paths = {}
    resource_id_field = {}
    scope = {}
    campaign_path = ""

    def __init__(self, base_url, scope=None, transport=None, timeout=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.base_url = (base_url or "").rstrip("/")
        self.scope = dict(scope or {})
        self.transport = transport or HttpTransport(self.base_url, timeout=timeout)
        self._correlation_id = ""

    def set_correlation_id(self, value):
        self._correlation_id = value or ""

    def _headers(self):
        headers = self.authorize()
        headers["X-Correlation-ID"] = self._correlation_id or uuid.uuid4().hex
        return headers

    def _fetch(self, request: FetchRequest) -> FetchResult:
        path = self.resource_paths.get(request.resource)
        if path is None:
            raise ConnectorError(
                f"{self.connector_id}: no path for resource {request.resource!r}")
        params = dict(self.scope)
        params["page_size"] = request.limit or 100
        if request.cursor:
            params["next_token"] = request.cursor
        response = self.transport.get(path, params=params,
                                      headers=self._headers())
        self._check(response)
        body = response.json()
        if not isinstance(body, dict):
            raise InvalidExternalResponse(
                f"{self.connector_id}: unexpected response shape")
        items = body.get("items")
        if items is None:
            raise InvalidExternalResponse(
                f"{self.connector_id}: response missing 'items'")
        id_field = self.resource_id_field.get(request.resource, "id")
        envelopes = tuple(self._envelope(item, request.resource, id_field)
                          for item in items)
        next_cursor = body.get("next_token")
        return FetchResult(envelopes=envelopes, next_cursor=next_cursor,
                           complete=not next_cursor)

    def _envelope(self, item, resource, id_field):
        external_id = str(item.get(id_field, ""))
        return SourceRecordEnvelope(
            source_record_id=external_id or uuid.uuid4().hex,
            resource=resource,
            source=self.provider,
            payload=dict(item),
            sequence=str(item.get("sequence", "")),
            source_external_id=external_id,
            source_observed_at=(item.get("lastUpdated")
                                or item.get("updated_at")
                                or item.get("ERSDA")
                                or ""),
            connector_id=self.connector_id,
            connector_version=self.version,
        )

    def _check(self, response):
        status = response.status_code
        if 200 <= status < 300:
            return
        body = response.json()
        if status in (401, 403):
            raise ExternalAuthenticationError(
                f"{self.connector_id}: authentication failed ({status})")
        if status == 404:
            raise ExternalNotFound(
                f"{self.connector_id}: resource not found ({status})")
        if status == 429:
            retry_after = response.headers.get("Retry-After", "1")
            try:
                retry_after = float(retry_after)
            except (TypeError, ValueError):
                retry_after = 1.0
            raise RateLimitError(
                f"{self.connector_id}: rate limited", retry_after=retry_after)
        if status in _RETRYABLE_STATUS:
            raise ExternalUnavailable(
                f"{self.connector_id}: upstream unavailable ({status})")
        if status in (400, 409):
            raise ExternalRequestError(
                f"{self.connector_id}: invalid request ({status}): {body!r}")
        raise ConnectorError(f"{self.connector_id}: unexpected status {status}")

    def update_campaign(self, campaign_id, body):
        if not self.campaign_path:
            raise ConnectorError(f"{self.connector_id}: no campaign write path")
        response = self.transport.patch(
            self.campaign_path.format(campaign_id=campaign_id),
            headers=self._headers(), json_body=body)
        self._check(response)
        return response.json()


class AmazonHttpConnector(HttpConnector):
    connector_id = "amazon_sp_api"
    provider = "amazon"
    resource_paths = {
        "listing": "/amazon/v1/listings",
        "order": "/amazon/v1/orders",
        "inventory": "/amazon/v1/inventory",
        "campaign": "/amazon/v1/advertising/campaigns",
        "review": "/amazon/v1/reviews",
        "metric": "/amazon/v1/metrics",
    }
    resource_id_field = {
        "listing": "asin", "order": "orderId", "inventory": "sku",
        "campaign": "campaignId", "review": "reviewId", "metric": "metricName",
    }
    campaign_path = "/amazon/v1/advertising/campaigns/{campaign_id}"


class TikTokHttpConnector(HttpConnector):
    connector_id = "tiktok_shop"
    provider = "tiktok"
    resource_paths = {
        "product": "/tiktok/v1/products",
        "order": "/tiktok/v1/orders",
        "inventory": "/tiktok/v1/inventory",
        "campaign": "/tiktok/v1/ads/campaigns",
        "review": "/tiktok/v1/reviews",
        "metric": "/tiktok/v1/metrics",
    }
    resource_id_field = {
        "product": "product_id", "order": "order_id", "inventory": "seller_sku",
        "campaign": "campaign_id", "review": "review_id", "metric": "metric_name",
    }
    campaign_path = "/tiktok/v1/ads/campaigns/{campaign_id}"


class SapHttpConnector(HttpConnector):
    connector_id = "sap_erp"
    provider = "sap"
    resource_paths = {
        "material": "/sap/v1/materials",
        "inventory": "/sap/v1/inventory",
        "purchase_order": "/sap/v1/purchase-orders",
    }
    resource_id_field = {
        "material": "MATNR", "inventory": "MATNR",
        "purchase_order": "EBELN",
    }


class SalesforceHttpConnector(HttpConnector):
    connector_id = "salesforce_crm"
    provider = "salesforce"
    resource_paths = {
        "account": "/salesforce/v1/accounts",
        "contact": "/salesforce/v1/contacts",
        "opportunity": "/salesforce/v1/opportunities",
        "case": "/salesforce/v1/cases",
    }
    resource_id_field = {
        "account": "Id", "contact": "Id",
        "opportunity": "Id", "case": "Id",
    }


class NetSuiteHttpConnector(HttpConnector):
    connector_id = "netsuite_erp"
    provider = "netsuite"
    resource_paths = {
        "item": "/netsuite/v1/items",
        "inventory": "/netsuite/v1/inventory",
        "sales_order": "/netsuite/v1/sales-orders",
        "purchase_order": "/netsuite/v1/purchase-orders",
        "fulfillment": "/netsuite/v1/fulfillments",
    }
    resource_id_field = {
        "item": "internalId", "inventory": "internalId",
        "sales_order": "internalId", "purchase_order": "internalId",
        "fulfillment": "internalId",
    }


__all__ = [
    "HttpConnector",
    "AmazonHttpConnector",
    "TikTokHttpConnector",
    "SapHttpConnector",
    "SalesforceHttpConnector",
    "NetSuiteHttpConnector",
]
