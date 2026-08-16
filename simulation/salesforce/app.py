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


def build_app():
    cfg = config()
    auth = SimulationAuth({
        "sim-salesforce-key": {"org_id": schemas.ORG_ID},
    })
    return build_simulation_app(cfg, auth, build_store(), FailureInjector(),
                                register_routes)


__all__ = ["build_app", "config"]
