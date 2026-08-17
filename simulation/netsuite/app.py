"""NetSuite simulation app (Phase 18.13)."""

from simulation.common.app import build_simulation_app
from simulation.common.auth import SimulationAuth
from simulation.common.config import SimulationConfig
from simulation.common.control import FailureInjector
from simulation.netsuite import schemas
from simulation.netsuite.routes import register_routes
from simulation.netsuite.store import build_store


def config():
    return SimulationConfig(provider="netsuite", port=9105,
                            api_key="sim-netsuite-key")


def build_app(seed_path=None):
    cfg = config()
    auth = SimulationAuth({
        "sim-netsuite-key": {"subsidiary": schemas.SUBSIDIARY},
    })
    store = build_store()
    from simulation.common.loader import load_seed_into
    store, dataset_id, dataset_version = load_seed_into("netsuite", store,
                                                        seed_path)
    return build_simulation_app(cfg, auth, store, FailureInjector(),
                                register_routes, dataset_id=dataset_id,
                                dataset_version=dataset_version)


__all__ = ["build_app", "config"]
