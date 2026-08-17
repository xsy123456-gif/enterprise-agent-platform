"""Amazon simulation routes (Phase 18.13).

Read surfaces: listings / orders / inventory / advertising campaigns / reviews /
metrics.  One write surface: campaign budget/status update.  All routes are
store-scoped: the ``seller_id``/``marketplaceId`` must match the token's scope.
"""

from fastapi import Depends, HTTPException, Request

from simulation.amazon import schemas
from simulation.common.errors import amazon_error
from simulation.common.pagination import paginate


def _scope(request: Request):
    return getattr(request.state, "scope", {})


def _authorize_scope(request: Request, seller_id, marketplace_id=None):
    scope = _scope(request)
    if seller_id and scope.get("seller_id") != seller_id:
        raise HTTPException(status_code=404, detail=amazon_error(
            "NotFound", f"seller {seller_id!r} not visible"))
    if marketplace_id and scope.get("marketplace_id") != marketplace_id:
        raise HTTPException(status_code=404, detail=amazon_error(
            "NotFound", f"marketplace {marketplace_id!r} not visible"))
    return scope


def _records(request, resource):
    return request.app.state.store.list_records(resource)


def _scoped(request, resource, seller_id):
    """Filter records by the store scope.  Contract fixtures without a
    ``seller_id`` field are returned unmodified (compatibility); seed records
    are scoped to the requesting seller."""
    if not seller_id:
        return _records(request, resource)
    return [r for r in _records(request, resource)
            if r.get("seller_id", seller_id) == seller_id]


def register_routes(app):
    auth = app.state.auth.dependency()

    @app.get("/amazon/v1/listings")
    def list_listings(request: Request, seller_id: str, page_size: int = 50,
                      next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, seller_id)
        return paginate(_scoped(request, "listing", seller_id), page_size,
                        next_token)

    @app.get("/amazon/v1/orders")
    def list_orders(request: Request, seller_id: str, page_size: int = 50,
                    next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, seller_id)
        return paginate(_scoped(request, "order", seller_id), page_size,
                        next_token)

    @app.get("/amazon/v1/inventory")
    def list_inventory(request: Request, seller_id: str, page_size: int = 50,
                       next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, seller_id)
        return paginate(_scoped(request, "inventory", seller_id), page_size,
                        next_token)

    @app.get("/amazon/v1/advertising/campaigns")
    def list_campaigns(request: Request, seller_id: str, page_size: int = 50,
                       next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, seller_id)
        return paginate(_scoped(request, "campaign", seller_id), page_size,
                        next_token)

    @app.get("/amazon/v1/reviews")
    def list_reviews(request: Request, seller_id: str, page_size: int = 50,
                     next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, seller_id)
        return paginate(_scoped(request, "review", seller_id), page_size,
                        next_token)

    @app.get("/amazon/v1/metrics")
    def list_metrics(request: Request, seller_id: str, page_size: int = 50,
                     next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, seller_id)
        return paginate(_scoped(request, "metric", seller_id), page_size,
                        next_token)

    @app.patch("/amazon/v1/advertising/campaigns/{campaign_id}")
    async def update_campaign(request: Request, campaign_id: str, _=Depends(auth)):
        body = await request.json()
        _authorize_scope(request, body.get("sellerId", ""),
                         body.get("marketplaceId"))
        existing = request.app.state.store.get("campaign", "campaignId", campaign_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=amazon_error(
                "NotFound", f"campaign {campaign_id!r} not found"))
        if "dailyBudget" in body:
            existing["dailyBudget"] = body["dailyBudget"]
        if "state" in body:
            existing["state"] = body["state"]
        updated = request.app.state.store.upsert(
            "campaign", "campaignId", existing)
        return {"campaignId": updated["campaignId"],
                "dailyBudget": updated["dailyBudget"],
                "state": updated["state"]}


__all__ = ["register_routes"]
