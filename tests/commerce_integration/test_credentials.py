"""Phase 12.9.3 Credential Boundary tests."""

import pytest

from app.commerce.integration.connectors.base import BaseConnector
from app.commerce.integration.credentials.models import Credential, SecretReference
from app.commerce.integration.credentials.provider import (
    InMemoryCredentialProvider,
    InMemorySecretProvider,
)
from app.commerce.integration.errors import CredentialError, SecretResolutionError


class _DemoConnector(BaseConnector):
    connector_id = "demo"

    def _fetch(self, request):
        return None


def _credential():
    return Credential(
        credential_id="c1", tenant_id="company_A", provider="amazon",
        secret_ref=SecretReference(reference_id="vault/amazon/token", provider="vault"),
    )


def test_credential_provider_returns_reference_only():
    provider = InMemoryCredentialProvider([_credential()])
    credential = provider.resolve("company_A", "amazon")
    assert credential.credential_id == "c1"
    assert credential.secret_ref.reference_id == "vault/amazon/token"
    assert not hasattr(credential, "token")


def test_credential_provider_unknown_raises():
    provider = InMemoryCredentialProvider([_credential()])
    with pytest.raises(CredentialError):
        provider.resolve("company_A", "shopify")


def test_secret_provider_resolves_inside_connector_runtime():
    secrets = InMemorySecretProvider({"vault/amazon/token": "amz-secret-123"})
    connector = _DemoConnector(credential=_credential(),
                               secret_provider=secrets)
    header = connector.authorize()
    assert header == {"Authorization": "Bearer amz-secret-123"}


def test_secret_provider_unresolvable_raises():
    secrets = InMemorySecretProvider({})
    with pytest.raises(SecretResolutionError):
        secrets.get_secret(SecretReference(reference_id="missing"))


def test_agent_layer_never_sees_secret():
    # The employee agent / skill / plan / tool layers import none of the
    # credential/secret surface; credentials are Connector-Runtime-only.
    import app.commerce.agents as agents
    for name in dir(agents):
        assert "Secret" not in name and "Credential" not in name
