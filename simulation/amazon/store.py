"""Amazon simulation state (Phase 18.13)."""

from simulation.amazon import schemas
from simulation.common.state import ProviderStateStore


def build_store():
    store = ProviderStateStore(provider="amazon")
    store.load("listing", schemas.LISTINGS)
    store.load("order", schemas.ORDERS)
    store.load("inventory", schemas.INVENTORY)
    store.load("campaign", schemas.CAMPAIGNS)
    store.load("review", schemas.REVIEWS)
    store.load("metric", schemas.METRICS)
    return store


__all__ = ["build_store"]
