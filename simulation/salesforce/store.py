"""Salesforce simulation state (Phase 18.13)."""

from simulation.common.state import ProviderStateStore
from simulation.salesforce import schemas


def build_store():
    store = ProviderStateStore(provider="salesforce")
    store.load("account", schemas.ACCOUNTS)
    store.load("contact", schemas.CONTACTS)
    store.load("opportunity", schemas.OPPORTUNITIES)
    store.load("case", schemas.CASES)
    return store


__all__ = ["build_store"]
