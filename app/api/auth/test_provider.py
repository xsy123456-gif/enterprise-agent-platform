"""Test authentication provider (Phase 18.12).

``Bearer test-user-<principal-id>`` — deterministic test principal resolution.
"""

from app.api.auth.models import AuthenticatedPrincipal
from app.api.errors import ApiError, ApiErrorCode


def _bearer(header):
    if not header:
        raise ApiError(ApiErrorCode.AUTHENTICATION_REQUIRED,
                       "Authentication is required.", http_status=401)
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(ApiErrorCode.INVALID_CREDENTIAL,
                       "Invalid credential.", http_status=401)
    return token.strip()


class TestAuthenticationProvider:

    def __init__(self, prefix="test-user-"):
        self.prefix = prefix

    def authenticate(self, authorization_header):
        token = _bearer(authorization_header)
        if not token.startswith(self.prefix):
            raise ApiError(ApiErrorCode.INVALID_CREDENTIAL,
                           "Invalid credential.", http_status=401)
        principal_id = token[len(self.prefix):]
        if not principal_id:
            raise ApiError(ApiErrorCode.INVALID_CREDENTIAL,
                           "Invalid credential.", http_status=401)
        return AuthenticatedPrincipal(principal_id=principal_id,
                                      auth_source="test")


__all__ = ["TestAuthenticationProvider"]
