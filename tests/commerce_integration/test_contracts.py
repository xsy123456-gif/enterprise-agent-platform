"""Phase 12.9.1 Integration Contract tests."""

import pytest

from app.commerce.ingestion.envelope import MUTATION_UPSERT, SourceRecordEnvelope
from app.commerce.ingestion.ports import FetchRequest, FetchResult
from app.commerce.integration.adapters.base import BaseAdapter
from app.commerce.integration.connectors.base import BaseConnector, RetryPolicy
from app.commerce.integration.credentials.models import (
    Credential,
    SecretReference,
)
from app.commerce.integration.errors import ConnectorError, RateLimitError


class _FailingConnector(BaseConnector):
    connector_id = "flaky"

    def __init__(self, fail_times=2, rate_limit=False, **kwargs):
        kwargs.setdefault("sleep", lambda s: None)
        super().__init__(**kwargs)
        self.fail_times = fail_times
        self.rate_limit = rate_limit
        self.calls = 0

    def _fetch(self, request):
        self.calls += 1
        if self.calls <= self.fail_times:
            if self.rate_limit:
                raise RateLimitError("limited", retry_after=0.01)
            raise ConnectorError("upstream down")
        return FetchResult(envelopes=(), next_cursor=None, complete=True)


def test_connector_retries_with_backoff():
    connector = _FailingConnector(fail_times=2)
    result = connector.fetch(FetchRequest(resource="LISTING", mode="FULL_SNAPSHOT"))
    assert result.complete is True
    assert connector.calls == 3
    assert connector.audit_log[-1]["kind"] == "error"


def test_connector_rate_limit_uses_retry_after():
    connector = _FailingConnector(fail_times=1, rate_limit=True)
    connector.fetch(FetchRequest(resource="LISTING", mode="FULL_SNAPSHOT"))
    assert connector.calls == 2
    assert connector.audit_log[0]["kind"] == "rate_limit"
    assert connector.audit_log[0]["retry_after"] == 0.01


def test_connector_gives_up_after_max_retries():
    connector = _FailingConnector(fail_times=99)
    with pytest.raises(ConnectorError):
        connector.fetch(FetchRequest(resource="LISTING", mode="FULL_SNAPSHOT"))
    assert connector.calls == 4  # 1 + 3 retries


# ── Adapter contract ────────────────────────────────────────

class _DemoAdapter(BaseAdapter):
    adapter_id = "demo"

    def adapt(self, envelope):
        entity = {"listing_id": "listing_B001", "tenant_id": self.tenant_id,
                  "store_id": self.store_id, "platform": "amazon",
                  "external_listing_id": envelope.payload["asin"]}
        return [self._mutation(MUTATION_UPSERT, "listing", entity, envelope,
                               external_id=envelope.payload["asin"],
                               resource_type="listing",
                               canonical_id="listing_B001")]


def _envelope():
    return SourceRecordEnvelope(
        source_record_id="r1", resource="listing", source="amazon",
        payload={"asin": "B001"}, source_external_id="B001",
        connector_id="amazon_sp_api", connector_version="1.0",
    )


def test_adapter_maps_dto_to_canonical_mutation():
    adapter = _DemoAdapter(tenant_id="company_A", store_id="JP01")
    mutations = adapter.adapt(_envelope())
    assert len(mutations) == 1
    mutation = mutations[0]
    assert mutation.mutation_type == MUTATION_UPSERT
    assert mutation.resource == "listing"
    assert mutation.entity["external_listing_id"] == "B001"
    assert mutation.external_identity["platform"] == "amazon"
    assert mutation.external_identity["external_id"] == "B001"
    assert mutation.external_identity["canonical_id"] == "listing_B001"
    # adapter never fabricates business analysis
    assert "cause" not in mutation.entity
    assert "impact" not in mutation.entity
    assert "priority" not in mutation.entity


# ── Credential contract ─────────────────────────────────────

def test_credential_never_holds_plain_token():
    credential = Credential(
        credential_id="c1", tenant_id="company_A", provider="amazon",
        secret_ref=SecretReference(reference_id="ref-123", provider="vault"),
    )
    assert not hasattr(credential, "token")
    assert not hasattr(credential, "access_token")
    assert not hasattr(credential, "refresh_token")
    assert not hasattr(credential, "secret")
    assert "token" not in credential.to_dict()
    assert credential.to_dict()["secret_ref"] == {
        "reference_id": "ref-123", "provider": "vault"}


def test_secret_reference_is_opaque():
    ref = SecretReference(reference_id="vault/amazon/token", provider="vault")
    assert ref.reference_id == "vault/amazon/token"
