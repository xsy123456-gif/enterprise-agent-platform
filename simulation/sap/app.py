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


def build_app():
    cfg = config()
    auth = SimulationAuth({
        "sim-sap-key": {"plant": schemas.PLANT,
                        "company_code": schemas.COMPANY_CODE},
    })
    return build_simulation_app(cfg, auth, build_store(), FailureInjector(),
                                register_routes)


__all__ = ["build_app", "config"]
