"""API request context dependency (Phase 18.12)."""

from fastapi import Depends, Request

from app.api.context import ApiRequestContext
from app.api.dependencies.auth import (
    get_authenticated_principal,
    get_trusted_context,
)


def get_api_request_context(
    request: Request,
    principal=Depends(get_authenticated_principal),
    trusted_context=Depends(get_trusted_context),
) -> ApiRequestContext:
    return ApiRequestContext(
        request_id=getattr(request.state, "request_id", ""),
        authenticated_principal=principal,
        trusted_context=trusted_context,
        client_metadata={
            "user_agent": request.headers.get("User-Agent", ""),
        },
    )


__all__ = ["get_api_request_context"]
