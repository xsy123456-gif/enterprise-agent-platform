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


def build_app():
    cfg = config()
    auth = SimulationAuth({
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
    })
    store = build_store()
    injector = FailureInjector()
    return build_simulation_app(cfg, auth, store, injector, register_routes)


__all__ = ["build_app", "config"]
