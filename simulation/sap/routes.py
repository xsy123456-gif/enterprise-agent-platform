"""SAP ERP simulation routes (Phase 18.13).

ERP-only read surfaces: material master, inventory, purchase orders.  Scoped by
``plant`` / ``companyCode``.
"""

from fastapi import Depends, HTTPException, Request

from simulation.common.errors import sap_error
from simulation.common.pagination import paginate


def _authorize_scope(request: Request, plant=None, company_code=None):
    scope = getattr(request.state, "scope", {})
    if plant and scope.get("plant") != plant:
        raise HTTPException(status_code=404,
                            detail=sap_error("PLANT_NOT_FOUND", "plant not visible"))
    if company_code and scope.get("company_code") != company_code:
        raise HTTPException(status_code=404,
                            detail=sap_error("COMPANY_NOT_FOUND", "company not visible"))


def register_routes(app):
    auth = app.state.auth.dependency()

    @app.get("/sap/v1/materials")
    def list_materials(request: Request, plant: str, companyCode: str = "",
                       page_size: int = 50, next_token: str | None = None,
                       _=Depends(auth)):
        _authorize_scope(request, plant=plant, company_code=companyCode)
        return paginate(request.app.state.store.list_records("material"),
                        page_size, next_token)

    @app.get("/sap/v1/inventory")
    def list_inventory(request: Request, plant: str, page_size: int = 50,
                       next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, plant=plant)
        return paginate(request.app.state.store.list_records("inventory"),
                        page_size, next_token)

    @app.get("/sap/v1/purchase-orders")
    def list_purchase_orders(request: Request, plant: str, page_size: int = 50,
                             next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, plant=plant)
        return paginate(request.app.state.store.list_records("purchase_order"),
                        page_size, next_token)


__all__ = ["register_routes"]
