"""Agent version governance (Phase 13.1).

Content-addressed integrity: every artifact carries a checksum of its manifest
so a tampered manifest can be detected before activation.  Version semantics
(no auto-upgrade, explicit activation) are enforced by the registry.
"""

import hashlib
import json

from app.platform.agent_control.errors import AgentValidationError


def _canonical(value):
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def artifact_checksum(manifest) -> str:
    data = manifest.to_dict() if hasattr(manifest, "to_dict") else dict(manifest)
    serialized = json.dumps(_canonical(data), ensure_ascii=False,
                            sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_checksum(artifact) -> bool:
    return artifact.checksum == artifact_checksum(artifact.manifest)


def ensure_valid_checksum(artifact):
    if not artifact.checksum:
        raise AgentValidationError(
            f"agent {artifact.agent_id!r}@{artifact.version} has no checksum"
        )
    if not verify_checksum(artifact):
        raise AgentValidationError(
            f"agent {artifact.agent_id!r}@{artifact.version} checksum mismatch"
        )


__all__ = ["artifact_checksum", "verify_checksum", "ensure_valid_checksum"]
