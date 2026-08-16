"""NetSuite ERP simulation routes (Phase 18.13).

ERP read surfaces: items / inventory / sales orders / purchase orders /
fulfillments.  Scoped by ``subsidiary``.
"""

from fastapi import Depends, HTTPException, Request

from simulation.common.errors import netsuite_error
from simulation.common.pagination import paginate


def _authorize_scope(request: Request, subsidiary):
    scope = getattr(request.state, "scope", {})
    if subsidiary and scope.get("subsidiary") != subsidiary:
        raise HTTPException(status_code=404,
                            detail=netsuite_error("SUBSIDIARY_NOT_FOUND",
                                                  "subsidiary not visible"))


def register_routes(app):
    auth = app.state.auth.dependency()

    @app.get("/netsuite/v1/items")
    def list_items(request: Request, subsidiary: str, page_size: int = 50,
                   next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, subsidiary)
        return paginate(request.app.state.store.list_records("item"),
                        page_size, next_token)

    @app.get("/netsuite/v1/inventory")
    def list_inventory(request: Request, subsidiary: str, page_size: int = 50,
                       next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, subsidiary)
        return paginate(request.app.state.store.list_records("inventory"),
                        page_size, next_token)

    @app.get("/netsuite/v1/sales-orders")
    def list_sales_orders(request: Request, subsidiary: str, page_size: int = 50,
                          next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, subsidiary)
        return paginate(request.app.state.store.list_records("sales_order"),
                        page_size, next_token)

    @app.get("/netsuite/v1/purchase-orders")
    def list_purchase_orders(request: Request, subsidiary: str, page_size: int = 50,
                             next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, subsidiary)
        return paginate(request.app.state.store.list_records("purchase_order"),
                        page_size, next_token)

    @app.get("/netsuite/v1/fulfillments")
    def list_fulfillments(request: Request, subsidiary: str, page_size: int = 50,
                          next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, subsidiary)
        return paginate(request.app.state.store.list_records("fulfillment"),
                        page_size, next_token)


__all__ = ["register_routes"]
