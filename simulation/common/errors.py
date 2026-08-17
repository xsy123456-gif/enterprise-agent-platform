"""Provider error DTOs (Phase 18.13.1).

Each provider returns its own error shape (Amazon-like, TikTok-like, SAP-like);
the connectors/adapters map them into the platform integration error taxonomy.
We intentionally do NOT unify these into one platform error shape.
"""


def amazon_error(code, message):
    return {"errors": [{"code": code, "message": message}]}


def tiktok_error(code, message):
    return {"code": code, "message": message}


def sap_error(code, message):
    return {"error": {"code": code, "message": message}}


def salesforce_error(code, message):
    return [{"errorCode": code, "message": message}]


def netsuite_error(code, message):
    return {"error": {"code": code, "message": message}}


__all__ = [
    "amazon_error",
    "tiktok_error",
    "sap_error",
    "salesforce_error",
    "netsuite_error",
]
