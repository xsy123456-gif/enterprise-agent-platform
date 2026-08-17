"""Development authentication provider (Phase 18.12).

``Bearer dev-<principal-id>`` — explicit development convenience.  Never a
production path.
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


class DevAuthenticationProvider:

    def authenticate(self, authorization_header):
        token = _bearer(authorization_header)
        if not token.startswith("dev-"):
            raise ApiError(ApiErrorCode.INVALID_CREDENTIAL,
                           "Invalid credential.", http_status=401)
        return AuthenticatedPrincipal(principal_id=token[len("dev-"):],
                                      auth_source="dev")


__all__ = ["DevAuthenticationProvider"]
