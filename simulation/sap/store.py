"""SAP simulation state (Phase 18.13)."""

from simulation.common.state import ProviderStateStore
from simulation.sap import schemas


def build_store():
    store = ProviderStateStore(provider="sap")
    store.load("material", schemas.MATERIALS)
    store.load("inventory", schemas.INVENTORY)
    store.load("purchase_order", schemas.PURCHASE_ORDERS)
    return store


__all__ = ["build_store"]
