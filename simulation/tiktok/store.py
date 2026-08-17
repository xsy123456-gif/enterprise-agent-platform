"""TikTok simulation state (Phase 18.13)."""

from simulation.common.state import ProviderStateStore
from simulation.tiktok import schemas


def build_store():
    store = ProviderStateStore(provider="tiktok")
    store.load("product", schemas.PRODUCTS)
    store.load("order", schemas.ORDERS)
    store.load("inventory", schemas.INVENTORY)
    store.load("campaign", schemas.CAMPAIGNS)
    store.load("review", schemas.REVIEWS)
    store.load("metric", schemas.METRICS)
    return store


__all__ = ["build_store"]
