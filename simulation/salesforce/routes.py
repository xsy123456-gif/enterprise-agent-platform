"""Salesforce CRM simulation routes (Phase 18.13).

CRM read surfaces: accounts / contacts / opportunities / cases.  Scoped by the
token's org (the token binds to ``org_id``).
"""

from fastapi import Depends, HTTPException, Request

from simulation.common.errors import salesforce_error
from simulation.common.pagination import paginate


def _authorize_scope(request: Request):
    scope = getattr(request.state, "scope", {})
    if not scope.get("org_id"):
        raise HTTPException(status_code=404, detail=salesforce_error(
            "NOT_FOUND", "org not visible"))


def register_routes(app):
    auth = app.state.auth.dependency()

    @app.get("/salesforce/v1/accounts")
    def list_accounts(request: Request, page_size: int = 50,
                      next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request)
        return paginate(request.app.state.store.list_records("account"),
                        page_size, next_token)

    @app.get("/salesforce/v1/contacts")
    def list_contacts(request: Request, page_size: int = 50,
                      next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request)
        return paginate(request.app.state.store.list_records("contact"),
                        page_size, next_token)

    @app.get("/salesforce/v1/opportunities")
    def list_opportunities(request: Request, page_size: int = 50,
                           next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request)
        return paginate(request.app.state.store.list_records("opportunity"),
                        page_size, next_token)

    @app.get("/salesforce/v1/cases")
    def list_cases(request: Request, page_size: int = 50,
                   next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request)
        return paginate(request.app.state.store.list_records("case"),
                        page_size, next_token)


__all__ = ["register_routes"]
