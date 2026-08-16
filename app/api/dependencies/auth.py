"""HTTP authentication + trusted-context dependencies (Phase 18.12).

Authorization header -> AuthenticationProvider -> AuthenticatedPrincipal ->
IdentityService -> TrustedExecutionContext.  Client-supplied tenant / role /
permission fields are never trusted (they are not even read).
"""

from fastapi import Depends, Request

from app.api.auth.models import AuthenticatedPrincipal
from app.api.errors import ApiError, ApiErrorCode
from app.commerce.trusted_context import project_trusted_context
from app.integrations.security.models.trusted_principal import TrustedPrincipal


def get_authenticated_principal(request: Request) -> AuthenticatedPrincipal:
    auth_provider = request.app.state.auth_provider
    return auth_provider.authenticate(request.headers.get("Authorization"))


def get_trusted_context(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
):
    resolver = request.app.state.resolver
    try:
        subject = resolver.resolve(TrustedPrincipal(
            principal_id=principal.principal_id, source=principal.auth_source))
    except Exception:
        raise ApiError(
            ApiErrorCode.INVALID_CREDENTIAL, "Invalid credential.",
            http_status=401,
        )
    return project_trusted_context(
        subject, {"trace_id": getattr(request.state, "request_id", "")},
    )


__all__ = ["get_authenticated_principal", "get_trusted_context"]
