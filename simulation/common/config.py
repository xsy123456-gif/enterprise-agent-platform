"""Simulation configuration (Phase 18.13.1)."""

from dataclasses import dataclass

DEFAULT_PORTS = {
    "amazon": 9101,
    "tiktok": 9102,
    "sap": 9103,
    "salesforce": 9104,
    "netsuite": 9105,
}


@dataclass(frozen=True)
class SimulationConfig:
    """Per-provider simulation service configuration.

    ``api_key`` is the Bearer token accepted on provider routes; ``admin_key``
    is the separate credential required to reach ``/__simulation__/*`` control
    endpoints (a provider credential alone must never be able to control the
    simulation).
    """

    provider: str
    port: int = 0
    api_key: str = ""
    admin_key: str = "simulation-admin-token"
    page_size: int = 50

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def resolve_defaults(self):
        if not self.port:
            object.__setattr__(self, "port", DEFAULT_PORTS.get(self.provider, 9100))
        if not self.api_key:
            object.__setattr__(self, "api_key", f"sim-{self.provider}-key")
        return self


__all__ = ["SimulationConfig", "DEFAULT_PORTS"]
