"""Amazon simulation app (Phase 18.13)."""

from simulation.amazon import schemas
from simulation.amazon.routes import register_routes
from simulation.amazon.store import build_store
from simulation.common.app import build_simulation_app
from simulation.common.auth import SimulationAuth
from simulation.common.config import SimulationConfig
from simulation.common.control import FailureInjector


def config():
    return SimulationConfig(
        provider="amazon",
        port=9101,
        api_key="sim-amazon-key",
    )


def build_app(seed_path=None):
    cfg = config()
    auth = SimulationAuth(_auth_scopes(seed_path))
    store = build_store()
    from simulation.common.loader import load_seed_into
    store, dataset_id, dataset_version = load_seed_into("amazon", store, seed_path)
    injector = FailureInjector()
    return build_simulation_app(cfg, auth, store, injector, register_routes,
                                dataset_id=dataset_id,
                                dataset_version=dataset_version)


def _auth_scopes(seed_path):
    default = {
        "sim-amazon-store-001-token": {
            "seller_id": schemas.SELLER_ID,
            "marketplace_id": schemas.MARKETPLACE_ID,
        },
        "sim-amazon-store-002-token": {
            "seller_id": "store-002",
            "marketplace_id": schemas.MARKETPLACE_ID,
        },
        "sim-amazon-key": {
            "seller_id": schemas.SELLER_ID,
            "marketplace_id": schemas.MARKETPLACE_ID,
        },
    }
    from simulation.common.loader import build_provider_auth

    def scope_fn(store):
        return {"seller_id": store["external_store_id"],
                "marketplace_id": store["marketplace"]}

    return build_provider_auth("amazon", seed_path, default, scope_fn)


__all__ = ["build_app", "config"]
