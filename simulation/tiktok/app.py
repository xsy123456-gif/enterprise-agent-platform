"""TikTok simulation app (Phase 18.13)."""

from simulation.common.app import build_simulation_app
from simulation.common.auth import SimulationAuth
from simulation.common.config import SimulationConfig
from simulation.common.control import FailureInjector
from simulation.tiktok import schemas
from simulation.tiktok.routes import register_routes
from simulation.tiktok.store import build_store


def config():
    return SimulationConfig(provider="tiktok", port=9102, api_key="sim-tiktok-key")


def build_app(seed_path=None):
    cfg = config()
    auth = SimulationAuth(_auth_scopes(seed_path))
    store = build_store()
    from simulation.common.loader import load_seed_into
    store, dataset_id, dataset_version = load_seed_into("tiktok", store, seed_path)
    return build_simulation_app(cfg, auth, store, FailureInjector(),
                                register_routes, dataset_id=dataset_id,
                                dataset_version=dataset_version)


def _auth_scopes(seed_path):
    default = {
        "sim-tiktok-shop-001-token": {"shop_id": schemas.SHOP_ID},
        "sim-tiktok-key": {"shop_id": schemas.SHOP_ID},
    }
    from simulation.common.loader import build_provider_auth

    def scope_fn(store):
        return {"shop_id": store["external_store_id"]}

    return build_provider_auth("tiktok", seed_path, default, scope_fn)


__all__ = ["build_app", "config"]
