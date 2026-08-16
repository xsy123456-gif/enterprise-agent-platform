"""Common public schemas (Phase 18.12)."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(PublicModel):
    code: str
    message: str
    request_id: str | None = None
    trace_id: str | None = None
    details: dict[str, Any] = {}


class ResourceLink(PublicModel):
    href: str


__all__ = ["PublicModel", "ErrorBody", "ResourceLink"]
