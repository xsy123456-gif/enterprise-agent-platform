"""Adapters package (Phase 12.9)."""

from app.commerce.integration.adapters.base import BaseAdapter
from app.commerce.integration.adapters.amazon import AmazonAdapter
from app.commerce.integration.adapters.tiktok import TikTokAdapter

__all__ = ["BaseAdapter", "AmazonAdapter", "TikTokAdapter"]
