"""Agent lifecycle validation (Phase 13.2).

The control-plane lifecycle: REGISTER -> VALIDATE -> PUBLISH (ACTIVE) ->
DEPRECATE.  Validation checks structural integrity (checksum + manifest
completeness); transitions are enforced by the registry.
"""

from app.platform.agent_control.errors import AgentValidationError
from app.platform.agent_control.versioning import ensure_valid_checksum


def validate_manifest(manifest):
    if not manifest.skills:
        raise AgentValidationError(
            f"agent {manifest.agent_id!r} declares no skills"
        )
    if not manifest.required_capabilities:
        raise AgentValidationError(
            f"agent {manifest.agent_id!r} declares no capabilities"
        )
    if not manifest.owner:
        raise AgentValidationError(
            f"agent {manifest.agent_id!r} has no owner"
        )
    if not manifest.department:
        raise AgentValidationError(
            f"agent {manifest.agent_id!r} has no department"
        )


def validate_artifact(artifact):
    ensure_valid_checksum(artifact)
    validate_manifest(artifact.manifest)
    return artifact


__all__ = ["validate_manifest", "validate_artifact"]
