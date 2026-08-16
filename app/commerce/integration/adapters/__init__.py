"""Adapters package (Phase 12.9 / 18.13.4)."""

from app.commerce.integration.adapters.base import BaseAdapter
from app.commerce.integration.adapters.amazon import AmazonAdapter
from app.commerce.integration.adapters.tiktok import TikTokAdapter
from app.commerce.integration.adapters.sap import SapAdapter
from app.commerce.integration.adapters.netsuite import NetSuiteAdapter

__all__ = [
    "BaseAdapter",
    "AmazonAdapter",
    "TikTokAdapter",
    "SapAdapter",
    "NetSuiteAdapter",
]
