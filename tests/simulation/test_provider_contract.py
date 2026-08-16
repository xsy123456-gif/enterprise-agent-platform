"""Phase 18.13.2 provider contract tests (Amazon + TikTok).

Pagination (multi-page, opaque token), write (PATCH mutates state), and provider
error shapes.
"""

from fastapi.testclient import TestClient

from simulation.amazon.app import build_app as amazon_app
from simulation.tiktok.app import build_app as tiktok_app


def _collect(client, url, params, headers):
    items = []
    requests = 0
    token = None
    while True:
        q = dict(params)
        if token:
            q["next_token"] = token
        response = client.get(url, params=q, headers=headers)
        assert response.status_code == 200
        requests += 1
        body = response.json()
        items.extend(body["items"])
        token = body.get("next_token")
        if token is None:
            break
    return items, requests


def test_amazon_listings_paginate_across_multiple_requests():
    client = TestClient(amazon_app())
    headers = {"Authorization": "Bearer sim-amazon-key"}
    items, requests = _collect(client, "/amazon/v1/listings",
                               {"seller_id": "store-001", "page_size": 2}, headers)
    assert len(items) == 4
    assert requests == 2
    asins = {item["asin"] for item in items}
    assert len(asins) == 4  # no duplicate, no missing


def test_tiktok_products_paginate_across_multiple_requests():
    client = TestClient(tiktok_app())
    headers = {"Authorization": "Bearer sim-tiktok-key"}
    items, requests = _collect(client, "/tiktok/v1/products",
                               {"shop_id": "shop-001", "page_size": 2}, headers)
    assert len(items) == 3
    assert requests == 2
    ids = {item["product_id"] for item in items}
    assert len(ids) == 3


def test_pagination_token_is_opaque():
    client = TestClient(amazon_app())
    headers = {"Authorization": "Bearer sim-amazon-key"}
    response = client.get("/amazon/v1/listings",
                          params={"seller_id": "store-001", "page_size": 2},
                          headers=headers)
    token = response.json()["next_token"]
    assert token is not None
    assert token != "2"
    assert "offset" not in token  # not a raw JSON offset in plaintext


def test_amazon_write_updates_campaign_state():
    client = TestClient(amazon_app())
    headers = {"Authorization": "Bearer sim-amazon-key"}
    response = client.patch(
        "/amazon/v1/advertising/campaigns/CMP-AMZ-1", headers=headers,
        json={"sellerId": "store-001", "dailyBudget": 120.0, "state": "ENABLED"})
    assert response.status_code == 200
    assert response.json()["dailyBudget"] == 120.0

    campaigns = client.get("/amazon/v1/advertising/campaigns",
                           params={"seller_id": "store-001"}, headers=headers)
    updated = next(c for c in campaigns.json()["items"]
                   if c["campaignId"] == "CMP-AMZ-1")
    assert updated["dailyBudget"] == 120.0


def test_tiktok_write_updates_campaign_state():
    client = TestClient(tiktok_app())
    headers = {"Authorization": "Bearer sim-tiktok-key"}
    response = client.patch(
        "/tiktok/v1/ads/campaigns/TT-CMP-1", headers=headers,
        json={"shop_id": "shop-001", "budget": 250.0, "status": "ACTIVE"})
    assert response.status_code == 200
    assert response.json()["budget"] == 250.0


def test_provider_error_shapes_differ():
    # Amazon-like vs TikTok-like error bodies (both 404 for a missing campaign).
    amazon = TestClient(amazon_app())
    amz = amazon.patch("/amazon/v1/advertising/campaigns/MISSING",
                       headers={"Authorization": "Bearer sim-amazon-key"},
                       json={"sellerId": "store-001", "dailyBudget": 1.0})
    assert amz.status_code == 404
    assert "errors" in amz.json()

    tiktok = TestClient(tiktok_app())
    tt = tiktok.patch("/tiktok/v1/ads/campaigns/MISSING",
                      headers={"Authorization": "Bearer sim-tiktok-key"},
                      json={"shop_id": "shop-001", "budget": 1.0})
    assert tt.status_code == 404
    assert "code" in tt.json()
