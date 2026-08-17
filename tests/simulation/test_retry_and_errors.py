"""Phase 18.13.5 retry / error mapping tests.

Retryable (429/503/timeout/network) vs non-retryable (400/401/404) behaviour,
rate-limit Retry-After handling, timeout mapping, and malformed-response
mapping.
"""

import pytest

from app.commerce.ingestion.ports import FetchRequest
from app.commerce.integration.connectors import AmazonHttpConnector
from app.commerce.integration.connectors.base import RetryPolicy
from app.commerce.integration.credentials.models import Credential, SecretReference
from app.commerce.integration.credentials.provider import InMemorySecretProvider
from app.commerce.integration.errors import (
    ExternalAuthenticationError,
    ExternalNotFound,
    ExternalRequestError,
    ExternalUnavailable,
    InvalidExternalResponse,
)
from app.commerce.integration.transport import HttpResponse
from tests.simulation.conftest import run_simulation

from simulation.amazon.app import build_app as amazon_app


class _StubTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, path, params=None, headers=None):
        self.calls += 1
        entry = self.responses.pop(0)
        if len(entry) == 2:
            status, body, response_headers = entry[0], entry[1], {}
        else:
            status, body, response_headers = entry
        return HttpResponse(status, body, response_headers)


def _connector(transport=None, **kwargs):
    kwargs.setdefault("base_url", "http://127.0.0.1:1")
    kwargs.setdefault("scope", {"seller_id": "store-001"})
    kwargs.setdefault("credential", Credential(
        credential_id="c1", tenant_id="company_A", provider="amazon",
        secret_ref=SecretReference(reference_id="ref")))
    kwargs.setdefault("secret_provider", InMemorySecretProvider({"ref": "tok"}))
    kwargs.setdefault("sleep", lambda s: None)
    kwargs.setdefault("retry_policy", RetryPolicy(max_retries=3,
                                                  base_seconds=0.0))
    if transport is not None:
        kwargs["transport"] = transport
    return AmazonHttpConnector(**kwargs)


def _ok(body):
    return (200, body)


def test_503_is_retried_then_succeeds():
    transport = _StubTransport([
        (503, {"errors": [{"code": "TemporarilyUnavailable"}]}),
        _ok({"items": [], "next_token": None}),
    ])
    connector = _connector(transport)
    result = connector.fetch(FetchRequest(resource="listing",
                                          mode="FULL_SNAPSHOT"))
    assert result.complete is True
    assert transport.calls == 2


def test_429_uses_retry_after_then_succeeds():
    transport = _StubTransport([
        (429, {"errors": [{"code": "Throttling"}]}, {"Retry-After": "0"}),
        _ok({"items": [], "next_token": None}),
    ])
    connector = _connector(transport)
    result = connector.fetch(FetchRequest(resource="listing",
                                          mode="FULL_SNAPSHOT"))
    assert result.complete is True
    assert transport.calls == 2
    assert connector.audit_log[0]["kind"] == "rate_limit"


def test_400_is_not_retried():
    transport = _StubTransport([(400, {"errors": [{"code": "InvalidInput"}]})])
    connector = _connector(transport)
    with pytest.raises(ExternalRequestError):
        connector.fetch(FetchRequest(resource="listing", mode="FULL_SNAPSHOT"))
    assert transport.calls == 1


def test_404_is_not_retried():
    transport = _StubTransport([(404, {"errors": [{"code": "NotFound"}]})])
    connector = _connector(transport)
    with pytest.raises(ExternalNotFound):
        connector.fetch(FetchRequest(resource="listing", mode="FULL_SNAPSHOT"))
    assert transport.calls == 1


def test_401_is_not_retried():
    transport = _StubTransport([(401, {"errors": [{"code": "Unauthorized"}]})])
    connector = _connector(transport)
    with pytest.raises(ExternalAuthenticationError):
        connector.fetch(FetchRequest(resource="listing", mode="FULL_SNAPSHOT"))
    assert transport.calls == 1


def test_timeout_maps_to_retryable_external_unavailable():
    with run_simulation(amazon_app()) as server:
        server.app.state.injector.delay_next_request(2.0)
        connector = _connector(
            transport=None, base_url=server.base_url, timeout=(0.2, 0.2),
            retry_policy=RetryPolicy(max_retries=0))
        with pytest.raises(ExternalUnavailable):
            connector.fetch(FetchRequest(resource="listing",
                                         mode="FULL_SNAPSHOT"))


def test_malformed_response_maps_to_invalid_external_response():
    with run_simulation(amazon_app()) as server:
        server.app.state.injector.malformed_next_request()
        connector = _connector(
            transport=None, base_url=server.base_url,
            retry_policy=RetryPolicy(max_retries=0))
        with pytest.raises(InvalidExternalResponse):
            connector.fetch(FetchRequest(resource="listing",
                                         mode="FULL_SNAPSHOT"))
