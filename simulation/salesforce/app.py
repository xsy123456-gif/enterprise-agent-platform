"""Salesforce simulation app (Phase 18.13)."""

from simulation.common.app import build_simulation_app
from simulation.common.auth import SimulationAuth
from simulation.common.config import SimulationConfig
from simulation.common.control import FailureInjector
from simulation.salesforce import schemas
from simulation.salesforce.routes import register_routes
from simulation.salesforce.store import build_store


def config():
    return SimulationConfig(provider="salesforce", port=9104,
                            api_key="sim-salesforce-key")


def build_app(seed_path=None):
    cfg = config()
    auth = SimulationAuth({
        "sim-salesforce-key": {"org_id": schemas.ORG_ID},
    })
    store = build_store()
    from simulation.common.loader import load_seed_into
    store, dataset_id, dataset_version = load_seed_into("salesforce", store,
                                                        seed_path)
    return build_simulation_app(cfg, auth, store, FailureInjector(),
                                register_routes, dataset_id=dataset_id,
                                dataset_version=dataset_version)


__all__ = ["build_app", "config"]
