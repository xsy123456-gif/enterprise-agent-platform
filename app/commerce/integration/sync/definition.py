"""Sync connector binding (Phase 12.9.6).

A ``ConnectorBinding`` links a Phase 7 ``SyncDefinition`` to a concrete
connector + adapter (with pinned versions) and a credential reference.  The
frozen ``SyncDefinition`` (Phase 7) is reused unchanged.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConnectorBinding:
    sync_id: str
    connector_id: str
    adapter_id: str
    credential_ref: str = ""
    connector_version: str = ""
    adapter_version: str = ""
    connector_config: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "connector_config", dict(self.connector_config or {}))
        if not self.sync_id:
            raise ValueError("sync_id is required")
        if not self.connector_id:
            raise ValueError("connector_id is required")
        if not self.adapter_id:
            raise ValueError("adapter_id is required")

    def to_dict(self) -> dict:
        return {
            "sync_id": self.sync_id,
            "connector_id": self.connector_id,
            "adapter_id": self.adapter_id,
            "credential_ref": self.credential_ref,
            "connector_version": self.connector_version,
            "adapter_version": self.adapter_version,
            "connector_config": dict(self.connector_config),
        }


__all__ = ["ConnectorBinding"]
