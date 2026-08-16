"""Health public schemas (Phase 18.12)."""

from app.api.v1.schemas.common import PublicModel


class LiveResponse(PublicModel):
    status: str = "alive"


class ReadyResponse(PublicModel):
    status: str
    components: dict = {}


__all__ = ["LiveResponse", "ReadyResponse"]
