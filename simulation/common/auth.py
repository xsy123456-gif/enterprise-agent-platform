"""Simulation auth (Phase 18.13.1).

Each simulation service accepts a simple Bearer token.  A token binds to a
provider account/store scope, so the service can deny a request that asks for a
scope the token does not own.  This proves connectors do not merely self-report
a store id — the server enforces it.
"""

from fastapi import HTTPException, Request


class SimulationAuth:
    def __init__(self, token_scopes):
        """``token_scopes`` maps ``token -> scope`` (a dict of provider account
        identifiers, e.g. ``{"seller_id": "store-001"}``)."""
        self._token_scopes = dict(token_scopes or {})

    def resolve_scope(self, token):
        if not token:
            return None
        return self._token_scopes.get(token)

    def dependency(self):
        def _dep(request: Request):
            authorization = request.headers.get("Authorization", "")
            token = ""
            if authorization.lower().startswith("bearer "):
                token = authorization[7:]
            scope = self.resolve_scope(token)
            if scope is None:
                raise HTTPException(
                    status_code=401,
                    detail={"code": "Unauthorized", "message": "invalid credential"},
                )
            request.state.scope = scope
            return scope

        return _dep


def require_admin(request: Request, admin_key: str):
    token = request.headers.get("X-Simulation-Admin-Token", "")
    if not admin_key or token != admin_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "Unauthorized", "message": "simulation control denied"},
        )


__all__ = ["SimulationAuth", "require_admin"]
