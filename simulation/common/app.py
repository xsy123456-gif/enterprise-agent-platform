"""Simulation FastAPI app builder (Phase 18.13.1).

Builds a per-provider FastAPI app with the shared cross-cutting concerns:
failure-injection middleware, request logging, ``/health``, ``/__simulation__/*
`` reset + control endpoints (admin-token protected).  Provider-specific routes
are registered by each provider module.
"""

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from simulation.common.auth import require_admin
from simulation.common.config import SimulationConfig


class SimulationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, injector):
        super().__init__(app)
        self.injector = injector

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path == "/health" or path.startswith("/__simulation__"):
            return await call_next(request)
        action = self.injector.take()
        if action is None:
            response = await call_next(request)
            _log(request, response)
            return response
        kind, value = action
        if kind == "fail":
            response = JSONResponse(
                status_code=503,
                content={"errors": [{"code": "TemporarilyUnavailable",
                                     "message": "upstream temporarily unavailable"}]},
                headers={"Retry-After": "0"},
            )
        elif kind == "rate_limit":
            response = JSONResponse(
                status_code=429,
                content={"errors": [{"code": "Throttling",
                                     "message": "rate limited"}]},
                headers={"Retry-After": str(value)},
            )
        elif kind == "delay":
            await asyncio.sleep(value)
            response = await call_next(request)
        elif kind == "malformed":
            response = JSONResponse(
                status_code=200,
                content={"unexpected": "shape"},
            )
        else:
            response = await call_next(request)
        _log(request, response)
        return response


def _log(request, response):
    store = getattr(request.app.state, "store", None)
    if store is None:
        return
    correlation_id = request.headers.get("X-Correlation-ID", "")
    store.request_log.record(
        provider=getattr(request.app.state, "provider", ""),
        method=request.method,
        path=request.url.path,
        correlation_id=correlation_id,
        status=response.status_code,
    )


def build_simulation_app(config: SimulationConfig, auth, store, injector,
                         register_routes):
    config = config.resolve_defaults()
    app = FastAPI(
        title=f"{config.provider} Simulation",
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    app.add_middleware(SimulationMiddleware, injector=injector)
    app.state.provider = config.provider
    app.state.store = store
    app.state.injector = injector
    app.state.auth = auth

    @app.get("/health")
    def health():
        return {"status": "ok", "provider": config.provider}

    @app.post("/__simulation__/reset")
    def reset(request: Request):
        require_admin(request, config.admin_key)
        store.reset()
        injector.reset()
        return {"status": "reset"}

    @app.post("/__simulation__/control/fail-next")
    def control_fail(request: Request):
        require_admin(request, config.admin_key)
        injector.fail_next_request()
        return {"status": "ok"}

    @app.post("/__simulation__/control/rate-limit-next")
    def control_rate_limit(request: Request):
        require_admin(request, config.admin_key)
        injector.rate_limit_next_request()
        return {"status": "ok"}

    @app.post("/__simulation__/control/delay-next")
    def control_delay(request: Request):
        require_admin(request, config.admin_key)
        body = request.json() if request.headers.get("content-length") else {}
        injector.delay_next_request(float(body.get("seconds", 1.0)))
        return {"status": "ok"}

    @app.post("/__simulation__/control/malformed-next")
    def control_malformed(request: Request):
        require_admin(request, config.admin_key)
        injector.malformed_next_request()
        return {"status": "ok"}

    register_routes(app)
    return app


__all__ = ["build_simulation_app", "SimulationMiddleware"]
