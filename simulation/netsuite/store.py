"""NetSuite simulation state (Phase 18.13)."""

from simulation.common.state import ProviderStateStore
from simulation.netsuite import schemas


def build_store():
    store = ProviderStateStore(provider="netsuite")
    store.load("item", schemas.ITEMS)
    store.load("inventory", schemas.INVENTORY)
    store.load("sales_order", schemas.SALES_ORDERS)
    store.load("purchase_order", schemas.PURCHASE_ORDERS)
    store.load("fulfillment", schemas.FULFILLMENTS)
    return store


__all__ = ["build_store"]
