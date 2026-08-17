"""SAP simulation app (Phase 18.13)."""

from simulation.common.app import build_simulation_app
from simulation.common.auth import SimulationAuth
from simulation.common.config import SimulationConfig
from simulation.common.control import FailureInjector
from simulation.sap import schemas
from simulation.sap.routes import register_routes
from simulation.sap.store import build_store


def config():
    return SimulationConfig(provider="sap", port=9103, api_key="sim-sap-key")


def build_app(seed_path=None):
    cfg = config()
    auth = SimulationAuth({
        "sim-sap-key": {"plant": schemas.PLANT,
                        "company_code": schemas.COMPANY_CODE},
    })
    store = build_store()
    from simulation.common.loader import load_seed_into
    store, dataset_id, dataset_version = load_seed_into("sap", store, seed_path)
    return build_simulation_app(cfg, auth, store, FailureInjector(),
                                register_routes, dataset_id=dataset_id,
                                dataset_version=dataset_version)


__all__ = ["build_app", "config"]
