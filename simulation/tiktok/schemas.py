"""TikTok Shop simulation DTOs (Phase 18.13).

TikTok-like field naming (snake_case ``seller_sku`` / ``product_id`` / ``title``)
differs from Amazon's camelCase DTOs, so the connector/adapter mapping is
genuinely exercised — these are NOT canonical entities.
"""

SHOP_ID = "shop-001"

PRODUCTS = [
    {"seller_sku": "SKU-001", "product_id": "7230001", "title": "Wireless Mouse",
     "status": "ACTIVE"},
    {"seller_sku": "SKU-002", "product_id": "7230002", "title": "Mechanical Keyboard",
     "status": "ACTIVE"},
    {"seller_sku": "SKU-003", "product_id": "7230003", "title": "USB-C Hub",
     "status": "SUSPENDED"},
]

ORDERS = [
    {"order_id": "TT-9001", "product_id": "7230001", "seller_sku": "SKU-001",
     "quantity": 1, "status": "SHIPPED", "price": 1290.0, "currency": "JPY",
     "created_at": "2026-08-01T00:00:00Z"},
    {"order_id": "TT-9002", "product_id": "7230002", "seller_sku": "SKU-002",
     "quantity": 1, "status": "PENDING", "price": 12900.0, "currency": "JPY",
     "created_at": "2026-08-02T00:00:00Z"},
]

INVENTORY = [
    {"seller_sku": "SKU-001", "available_stock": 120, "reserved_stock": 5,
     "updated_at": "2026-08-10T00:00:00Z"},
    {"seller_sku": "SKU-002", "available_stock": 3, "reserved_stock": 0,
     "updated_at": "2026-08-10T00:00:00Z"},
]

CAMPAIGNS = [
    {"campaign_id": "TT-CMP-1", "name": "TikTok Launch", "budget": 200.0,
     "status": "ACTIVE"},
    {"campaign_id": "TT-CMP-2", "name": "Lookalike", "budget": 80.0,
     "status": "PAUSED"},
]

REVIEWS = [
    {"review_id": "R-TT-1", "product_id": "7230001", "rating": 3,
     "comment": "Decent but small."},
    {"review_id": "R-TT-2", "product_id": "7230001", "rating": 5,
     "comment": "Great value."},
]

METRICS = [
    {"metric_name": "GMV", "value": 180000.0, "period": "DAILY",
     "period_start": "2026-08-01", "period_end": "2026-08-02"},
    {"metric_name": "SESSIONS", "value": 15000.0, "period": "DAILY",
     "period_start": "2026-08-01", "period_end": "2026-08-02"},
]
