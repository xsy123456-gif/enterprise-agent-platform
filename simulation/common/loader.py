"""Simulation state loader (Phase 18.14).

Loads a ``data/seed/...`` dataset into a provider's ``ProviderStateStore``.
This is the only runtime consumer of the seed data; the platform and connectors
never read seed files directly.  The loader does data -> provider state only; it
never computes diagnostics, insights, causes or anomalies.
"""

import json
import os


class SimulationStateLoader:
    def __init__(self, seed_root):
        self.seed_root = seed_root
        manifest_path = os.path.join(seed_root, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as fh:
            self.manifest = json.load(fh)
        self.dataset_id = self.manifest.get("dataset_id", "")
        self.dataset_version = self.manifest.get("dataset_version", "")

    def _read_jsonl(self, provider, filename):
        path = os.path.join(self.seed_root, "providers", provider, filename)
        if not os.path.exists(path):
            return []
        rows = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def load_into(self, provider, store, resource_files):
        """``resource_files`` maps resource -> provider filename."""
        for resource, filename in resource_files.items():
            records = self._read_jsonl(provider, filename)
            if records:
                store.load(resource, records)
        return store


# resource -> provider file mapping for each provider
RESOURCE_FILES = {
    "amazon": {
        "listing": "listings.jsonl",
        "order": "orders.jsonl",
        "inventory": "inventory.jsonl",
        "campaign": "campaigns.jsonl",
        "review": "reviews.jsonl",
        "metric": "metrics.jsonl",
    },
    "tiktok": {
        "product": "products.jsonl",
        "order": "orders.jsonl",
        "inventory": "inventory.jsonl",
        "campaign": "campaigns.jsonl",
        "review": "reviews.jsonl",
        "metric": "metrics.jsonl",
    },
    "sap": {
        "material": "materials.jsonl",
        "inventory": "inventory.jsonl",
        "purchase_order": "purchase_orders.jsonl",
    },
    "salesforce": {
        "account": "accounts.jsonl",
        "contact": "contacts.jsonl",
        "opportunity": "opportunities.jsonl",
        "case": "cases.jsonl",
    },
    "netsuite": {
        "item": "items.jsonl",
        "inventory": "inventory.jsonl",
        "sales_order": "sales_orders.jsonl",
        "purchase_order": "purchase_orders.jsonl",
        "fulfillment": "fulfillments.jsonl",
    },
}


def load_provider(provider, store, seed_root):
    loader = SimulationStateLoader(seed_root)
    return loader.load_into(provider, store, RESOURCE_FILES[provider]), loader


def load_seed_into(provider, store, seed_path):
    """Load a seed dataset if given; returns (store, dataset_id, version)."""
    if not seed_path:
        return store, "", ""
    store, loader = load_provider(provider, store, seed_path)
    return store, loader.dataset_id, loader.dataset_version


def provider_stores(seed_root, provider):
    """Return the seed's stores for a provider (world/stores.json)."""
    if not seed_root:
        return []
    path = os.path.join(seed_root, "world", "stores.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        stores = json.load(fh)
    return [s for s in stores if s.get("provider") == provider]


def build_provider_auth(provider, seed_path, default_scopes, scope_fn):
    """Build a token->scope map; when a seed is loaded, bind tokens to the seed's
    real provider account/store identifiers."""
    if not seed_path:
        return default_scopes
    stores = provider_stores(seed_path, provider)
    if not stores:
        return default_scopes
    scopes = {f"sim-{provider}-key": scope_fn(stores[0])}
    for i, store in enumerate(stores):
        scopes[f"sim-{provider}-store-{i + 1:03d}-token"] = scope_fn(store)
    return scopes


__all__ = ["SimulationStateLoader", "RESOURCE_FILES", "load_provider",
           "load_seed_into", "provider_stores", "build_provider_auth"]
