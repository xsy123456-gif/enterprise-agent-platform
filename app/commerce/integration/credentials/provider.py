"""Credential providers (Phase 12.9.3).

``InMemoryCredentialProvider`` resolves a tenant x provider ``Credential``
(reference only); ``InMemorySecretProvider`` resolves a ``SecretReference`` to
the plain secret.  The secret provider is reachable only inside the Connector
Runtime — never from an Agent / Skill / Plan / Tool.
"""

from app.commerce.integration.credentials.models import (
    Credential,
    CredentialProvider,
    SecretProvider,
)
from app.commerce.integration.errors import (
    CredentialError,
    SecretResolutionError,
)


class InMemoryCredentialProvider(CredentialProvider):

    def __init__(self, credentials=None):
        self._credentials = {}
        for credential in (credentials or []):
            self._credentials[(credential.tenant_id, credential.provider)] = credential

    def resolve(self, tenant_id, provider) -> Credential:
        credential = self._credentials.get((tenant_id, provider))
        if credential is None:
            raise CredentialError(f"no credential for {tenant_id}@{provider}")
        return credential


class InMemorySecretProvider(SecretProvider):

    def __init__(self, secrets=None):
        self._secrets = dict(secrets or {})

    def get_secret(self, secret_ref) -> str:
        secret = self._secrets.get(secret_ref.reference_id)
        if secret is None:
            raise SecretResolutionError(
                f"unresolvable secret reference {secret_ref.reference_id!r}"
            )
        return secret


__all__ = ["InMemoryCredentialProvider", "InMemorySecretProvider"]
