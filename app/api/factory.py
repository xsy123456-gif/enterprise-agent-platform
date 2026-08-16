"""HTTP application factory (Phase 18.12).

``create_http_app`` builds the FastAPI inbound adapter over an already-composed
``EnterpriseApplication``.  It never builds a second platform, never imports
business logic, and never executes tools / plans / agents directly.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.config import ApiConfig
from app.api.errors import ApiError, ApiErrorCode
from app.api.gateway import EnterpriseProductGateway
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.middleware.security_headers import SecurityHeadersMiddleware
from app.api.v1.endpoints import health
from app.api.v1.router import router as v1_router


def _request_id(request):
    return getattr(request.state, "request_id", "")


def _build_gateway(application, access_control=None):
    agents = application.agents
    agent_directory = {agents.definition.agent_id: agents.runtime}
    agent_definitions = {agents.definition.agent_id: agents.definition}
    return EnterpriseProductGateway(
        agent_directory=agent_directory,
        agent_definitions=agent_definitions,
        execution_store=application.commerce.execution_manager.store,
        trace_collector=application.production.trace,
        approval_repository=application.business.approval.repository,
        approval_engine=application.business.approval,
        workflow_repository=application.business.workflow_engine.run_repository,
        workflow_engine=application.business.workflow_engine,
        fact_executor=application.commerce.tool_surface.fact_executor,
        access_control=access_control,
        control_plane_registry=application.control_plane.registry,
    )


def create_http_app(application, authentication_provider, config: ApiConfig,
                    access_control=None):
    app = FastAPI(
        title="Enterprise Agent Platform API",
        version="1.0.0",
        docs_url="/docs" if config.docs_enabled else None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
        redoc_url=None,
    )
    app.state.application = application
    app.state.gateway = _build_gateway(application, access_control=access_control)
    app.state.auth_provider = authentication_provider
    app.state.resolver = application.foundation.security.resolver
    app.state.api_config = config
    from app.api.idempotency import InMemoryIdempotencyStore
    from app.api.idempotency.guard import IdempotencyGuard
    app.state.idempotency_store = InMemoryIdempotencyStore()
    app.state.idempotency_guard = IdempotencyGuard(app.state.idempotency_store)

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.http_status,
                            content=exc.envelope(_request_id(request)))

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={
            "error": {
                "code": ApiErrorCode.INVALID_REQUEST,
                "message": "Invalid request.",
                "request_id": _request_id(request),
                "trace_id": None,
                "details": {},
            }
        })

    @app.exception_handler(Exception)
    async def _internal_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={
            "error": {
                "code": ApiErrorCode.INTERNAL_ERROR,
                "message": "An internal error occurred.",
                "request_id": _request_id(request),
                "trace_id": None,
                "details": {},
            }
        })

    app.include_router(health.router)
    app.include_router(v1_router)
    return app


__all__ = ["create_http_app"]
