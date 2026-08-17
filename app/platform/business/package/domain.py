"""Vertical agent package domain (Phase 16.1).

A package bundles Agents + Skills + Plans + Knowledge + Workflow templates +
integrations into an installable industry solution.
"""

import hashlib
import json
from dataclasses import dataclass, field

from app.core.time import utc_now

PACKAGE_DRAFT = "DRAFT"
PACKAGE_VALIDATED = "VALIDATED"
PACKAGE_PUBLISHED = "PUBLISHED"
PACKAGE_INSTALLED = "INSTALLED"
PACKAGE_DEPRECATED = "DEPRECATED"
PACKAGE_STATUSES = frozenset({
    PACKAGE_DRAFT, PACKAGE_VALIDATED, PACKAGE_PUBLISHED, PACKAGE_INSTALLED,
    PACKAGE_DEPRECATED,
})


def _canonical(value):
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def package_checksum(package) -> str:
    serialized = json.dumps(_canonical({
        "package_id": package.package_id,
        "version": package.version,
        "agents": list(package.agents),
        "skills": list(package.skills),
        "plans": list(package.plans),
        "knowledge_bundle": list(package.knowledge_bundle),
        "workflow_templates": list(package.workflow_templates),
        "required_integrations": list(package.required_integrations),
    }), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AgentPackage:
    package_id: str
    version: str
    name: str = ""
    domain: str = ""
    agents: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    plans: tuple[str, ...] = ()
    knowledge_bundle: tuple[str, ...] = ()
    workflow_templates: tuple[str, ...] = ()
    required_integrations: tuple[str, ...] = ()
    checksum: str = ""
    status: str = PACKAGE_DRAFT
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        for name in ("agents", "skills", "plans", "knowledge_bundle",
                     "workflow_templates", "required_integrations"):
            object.__setattr__(self, name, tuple(getattr(self, name) or ()))
        if not self.package_id:
            raise ValueError("package_id is required")
        if not self.version:
            raise ValueError("version is required")
        if self.status not in PACKAGE_STATUSES:
            raise ValueError(f"unknown package status: {self.status}")
        if not self.checksum:
            object.__setattr__(self, "checksum", package_checksum(self))

    def to_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "version": self.version,
            "name": self.name,
            "domain": self.domain,
            "agents": list(self.agents),
            "skills": list(self.skills),
            "plans": list(self.plans),
            "knowledge_bundle": list(self.knowledge_bundle),
            "workflow_templates": list(self.workflow_templates),
            "required_integrations": list(self.required_integrations),
            "checksum": self.checksum,
            "status": self.status,
            "created_at": self.created_at,
        }


__all__ = [
    "AgentPackage",
    "package_checksum",
    "PACKAGE_STATUSES",
    "PACKAGE_DRAFT",
    "PACKAGE_VALIDATED",
    "PACKAGE_PUBLISHED",
    "PACKAGE_INSTALLED",
    "PACKAGE_DEPRECATED",
]
