"""Policy snapshot builder."""

from app.permission.models.snapshot import PolicySnapshot
from app.permission.policy.canonical import compute_policy_set_version


def build_snapshot(policies) -> PolicySnapshot:
    ordered = sorted(policies, key=lambda p: (p.policy_id, p.version))
    return PolicySnapshot(
        policy_set_version=compute_policy_set_version(ordered),
        policies=tuple(ordered),
    )
