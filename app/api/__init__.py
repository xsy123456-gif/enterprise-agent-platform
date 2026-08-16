"""Product API inbound adapter (Phase 18.12)."""

from app.api.config import ApiConfig, api_config_for
from app.api.context import ApiRequestContext
from app.api.errors import ApiError, ApiErrorCode
from app.api.factory import create_http_app
from app.api.gateway import EnterpriseProductGateway
from app.api.server import build_http_application

__all__ = [
    "ApiConfig",
    "api_config_for",
    "ApiRequestContext",
    "ApiError",
    "ApiErrorCode",
    "create_http_app",
    "EnterpriseProductGateway",
    "build_http_application",
]
