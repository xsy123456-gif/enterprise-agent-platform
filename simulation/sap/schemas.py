"""SAP ERP simulation DTOs (Phase 18.13).

SAP-like field naming (``MATNR`` material, ``MAKTX`` description, ``LABST``
unrestricted stock, ``WERKS`` plant, ``BUKRS`` company code).  ERP-only data —
no advertising / reviews / marketplace traffic.
"""

PLANT = "PL01"
COMPANY_CODE = "CC01"

MATERIALS = [
    {"MATNR": "SKU-001", "MAKTX": "Wireless Mouse", "MTART": "FERT",
     "WERKS": "PL01", "BUKRS": "CC01"},
    {"MATNR": "SKU-002", "MAKTX": "Mechanical Keyboard", "MTART": "FERT",
     "WERKS": "PL01", "BUKRS": "CC01"},
    {"MATNR": "SKU-003", "MAKTX": "USB-C Hub", "MTART": "HAWA",
     "WERKS": "PL01", "BUKRS": "CC01"},
]

INVENTORY = [
    {"MATNR": "SKU-001", "WERKS": "PL01", "LABST": 120, "UMLMC": 5,
     "MEINS": "PC", "ERSDA": "2026-08-10"},
    {"MATNR": "SKU-002", "WERKS": "PL01", "LABST": 3, "UMLMC": 0,
     "MEINS": "PC", "ERSDA": "2026-08-10"},
]

PURCHASE_ORDERS = [
    {"EBELN": "PO-5001", "MATNR": "SKU-001", "MENGE": 50, "WERKS": "PL01",
     "STATUS": "OPEN"},
    {"EBELN": "PO-5002", "MATNR": "SKU-002", "MENGE": 100, "WERKS": "PL01",
     "STATUS": "RECEIVED"},
]
