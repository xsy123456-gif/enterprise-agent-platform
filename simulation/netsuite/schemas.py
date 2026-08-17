"""NetSuite ERP simulation DTOs (Phase 18.13).

NetSuite-like field naming (``internalId``, ``itemId``, ``displayName``,
``onHand``).  ERP item/order/inventory semantics — a second ERP mapping surface
distinct from SAP.
"""

SUBSIDIARY = "SUB-001"

ITEMS = [
    {"internalId": "1001", "itemId": "SKU-001", "displayName": "Wireless Mouse",
     "type": "InventoryItem", "onHand": 120},
    {"internalId": "1002", "itemId": "SKU-002", "displayName": "Mechanical Keyboard",
     "type": "InventoryItem", "onHand": 3},
    {"internalId": "1003", "itemId": "SKU-003", "displayName": "USB-C Hub",
     "type": "NonInventoryItem", "onHand": 0},
]

INVENTORY = [
    {"internalId": "1001", "itemId": "SKU-001", "location": "MAIN",
     "onHand": 120, "committed": 5, "available": 115},
    {"internalId": "1002", "itemId": "SKU-002", "location": "MAIN",
     "onHand": 3, "committed": 0, "available": 3},
]

SALES_ORDERS = [
    {"internalId": "SO-2001", "itemId": "SKU-001", "quantity": 2,
     "status": "PendingFulfillment", "amount": 2580.0},
    {"internalId": "SO-2002", "itemId": "SKU-002", "quantity": 1,
     "status": "PendingFulfillment", "amount": 12900.0},
]

PURCHASE_ORDERS = [
    {"internalId": "PO-3001", "itemId": "SKU-001", "quantity": 50,
     "status": "PendingReceipt"},
]

FULFILLMENTS = [
    {"internalId": "IF-4001", "salesOrderId": "SO-2001", "itemId": "SKU-001",
     "quantity": 2, "status": "Shipped"},
]
