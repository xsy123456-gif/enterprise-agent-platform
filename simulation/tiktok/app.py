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


def build_app():
    cfg = config()
    auth = SimulationAuth({
        "sim-tiktok-shop-001-token": {"shop_id": schemas.SHOP_ID},
        "sim-tiktok-key": {"shop_id": schemas.SHOP_ID},
    })
    return build_simulation_app(cfg, auth, build_store(), FailureInjector(),
                                register_routes)


__all__ = ["build_app", "config"]
