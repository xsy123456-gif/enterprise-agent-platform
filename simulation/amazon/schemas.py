"""Amazon simulation provider DTOs (Phase 18.13).

Amazon-like field naming is preserved (``sellerSku``, ``asin``, ``itemName``,
``dailyBudget``, ``state``) so the connector/adapter semantic mapping is actually
exercised — these are NOT canonical entities.
"""

# Contract fixtures: minimal, provider-focused, protocol-focused (not 18.14 seed).

SELLER_ID = "store-001"
MARKETPLACE_ID = "JP"

LISTINGS = [
    {"sellerSku": "SKU-001", "asin": "B0ABC001", "itemName": "Wireless Mouse",
     "status": "Active"},
    {"sellerSku": "SKU-002", "asin": "B0ABC002", "itemName": "Mechanical Keyboard",
     "status": "Active"},
    {"sellerSku": "SKU-003", "asin": "B0ABC003", "itemName": "USB-C Hub",
     "status": "Inactive"},
    {"sellerSku": "SKU-004", "asin": "B0ABC004", "itemName": "Monitor Stand",
     "status": "Active"},
]

ORDERS = [
    {"orderId": "ORD-1001", "asin": "B0ABC001", "sellerSku": "SKU-001",
     "quantity": 2, "orderStatus": "Shipped", "amount": 2580.0,
     "currency": "JPY", "purchaseDate": "2026-08-01T00:00:00Z"},
    {"orderId": "ORD-1002", "asin": "B0ABC002", "sellerSku": "SKU-002",
     "quantity": 1, "orderStatus": "Pending", "amount": 12900.0,
     "currency": "JPY", "purchaseDate": "2026-08-02T00:00:00Z"},
]

INVENTORY = [
    {"sku": "SKU-001", "fnSku": "X0001", "fulfillable": 120,
     "reserved": 5, "lastUpdated": "2026-08-10T00:00:00Z"},
    {"sku": "SKU-002", "fnSku": "X0002", "fulfillable": 3,
     "reserved": 0, "lastUpdated": "2026-08-10T00:00:00Z"},
]

CAMPAIGNS = [
    {"campaignId": "CMP-AMZ-1", "name": "JP Launch", "dailyBudget": 100.0,
     "state": "ENABLED", "targetingType": "AUTO"},
    {"campaignId": "CMP-AMZ-2", "name": "Retargeting", "dailyBudget": 50.0,
     "state": "PAUSED", "targetingType": "MANUAL"},
]

REVIEWS = [
    {"reviewId": "R-AMZ-1", "asin": "B0ABC001", "rating": 2, "title": "Too small",
     "content": "Mouse broke after two days.", "reviewDate": "2026-08-05T00:00:00Z"},
    {"reviewId": "R-AMZ-2", "asin": "B0ABC001", "rating": 4, "title": "Good",
     "content": "Works well for the price.", "reviewDate": "2026-08-06T00:00:00Z"},
]

METRICS = [
    {"metricName": "GMV", "value": 250000.0, "period": "DAILY",
     "periodStart": "2026-08-01", "periodEnd": "2026-08-02"},
    {"metricName": "SESSIONS", "value": 18000.0, "period": "DAILY",
     "periodStart": "2026-08-01", "periodEnd": "2026-08-02"},
]
