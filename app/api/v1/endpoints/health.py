"""Health endpoints (Phase 18.12)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.v1.schemas.health import LiveResponse, ReadyResponse

router = APIRouter(tags=["Health"])


@router.get("/health/live", response_model=LiveResponse)
def live():
    return LiveResponse(status="alive")


@router.get("/health/ready", response_model=ReadyResponse)
def ready(request: Request):
    application = request.app.state.application
    components = {"runtime": "ready", "identity": "ready",
                  "commerce": "ready", "knowledge": "ready"}
    ready_ok = application.started
    if not ready_ok:
        return JSONResponse(status_code=503, content=ReadyResponse(
            status="not_ready", components=components).model_dump())
    return ReadyResponse(status="ready", components=components)


__all__ = ["router"]
