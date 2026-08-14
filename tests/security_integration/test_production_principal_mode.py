"""Production principal-source mode: external_required fails closed."""

from types import SimpleNamespace

import pytest

from app.integrations.security.config import SecurityIntegrationConfig
from app.integrations.security.errors import TrustedPrincipalResolutionError
from app.integrations.security.tools.security_gate import LocalTrustedPrincipalProvider


def test_local_principal_mode_derives_principal():
    provider = LocalTrustedPrincipalProvider(allow_local=True)
    principal = provider.from_request(SimpleNamespace(user_id="U001"))
    assert principal.principal_id == "U001"


def test_external_required_principal_mode_fails_closed():
    config = SecurityIntegrationConfig(principal_source="external_required")
    assert config.principal_source == "external_required"
    provider = LocalTrustedPrincipalProvider(
        allow_local=(config.principal_source != "external_required")
    )
    with pytest.raises(TrustedPrincipalResolutionError):
        provider.from_request(SimpleNamespace(user_id="U001"))
