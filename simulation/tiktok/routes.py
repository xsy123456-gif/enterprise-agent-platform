"""TikTok Shop simulation routes (Phase 18.13).

Read surfaces: products / orders / inventory / ads campaigns / reviews / metrics.
One write surface: campaign budget/status update.  Store-scoped by ``shop_id``.
"""

from fastapi import Depends, HTTPException, Request

from simulation.common.errors import tiktok_error
from simulation.common.pagination import paginate


def _authorize_scope(request: Request, shop_id):
    scope = getattr(request.state, "scope", {})
    if shop_id and scope.get("shop_id") != shop_id:
        raise HTTPException(status_code=404,
                            detail=tiktok_error(4040001, "shop not visible"))


def _scoped(request, resource, shop_id):
    if not shop_id:
        return request.app.state.store.list_records(resource)
    return [r for r in request.app.state.store.list_records(resource)
            if r.get("shop_id", shop_id) == shop_id]


def register_routes(app):
    auth = app.state.auth.dependency()

    @app.get("/tiktok/v1/products")
    def list_products(request: Request, shop_id: str, page_size: int = 50,
                      next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, shop_id)
        return paginate(_scoped(request, "product", shop_id), page_size,
                        next_token)

    @app.get("/tiktok/v1/orders")
    def list_orders(request: Request, shop_id: str, page_size: int = 50,
                    next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, shop_id)
        return paginate(_scoped(request, "order", shop_id), page_size,
                        next_token)

    @app.get("/tiktok/v1/inventory")
    def list_inventory(request: Request, shop_id: str, page_size: int = 50,
                       next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, shop_id)
        return paginate(_scoped(request, "inventory", shop_id), page_size,
                        next_token)

    @app.get("/tiktok/v1/ads/campaigns")
    def list_campaigns(request: Request, shop_id: str, page_size: int = 50,
                       next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, shop_id)
        return paginate(_scoped(request, "campaign", shop_id), page_size,
                        next_token)

    @app.get("/tiktok/v1/reviews")
    def list_reviews(request: Request, shop_id: str, page_size: int = 50,
                     next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, shop_id)
        return paginate(_scoped(request, "review", shop_id), page_size,
                        next_token)

    @app.get("/tiktok/v1/metrics")
    def list_metrics(request: Request, shop_id: str, page_size: int = 50,
                     next_token: str | None = None, _=Depends(auth)):
        _authorize_scope(request, shop_id)
        return paginate(_scoped(request, "metric", shop_id), page_size,
                        next_token)

    @app.patch("/tiktok/v1/ads/campaigns/{campaign_id}")
    async def update_campaign(request: Request, campaign_id: str, _=Depends(auth)):
        body = await request.json()
        _authorize_scope(request, body.get("shop_id", ""))
        existing = request.app.state.store.get("campaign", "campaign_id", campaign_id)
        if existing is None:
            raise HTTPException(status_code=404,
                                detail=tiktok_error(4040002, "campaign not found"))
        if "budget" in body:
            existing["budget"] = body["budget"]
        if "status" in body:
            existing["status"] = body["status"]
        updated = request.app.state.store.upsert("campaign", "campaign_id", existing)
        return {"campaign_id": updated["campaign_id"],
                "budget": updated["budget"], "status": updated["status"]}


__all__ = ["register_routes"]
