"""Local filesystem policy provider."""

import os

import yaml

from app.permission.errors import PermissionPolicyError
from app.permission.models.policy import PermissionPolicy
from app.permission.policy.parser import parse_policies
from app.permission.ports.policy_provider import PolicyProviderPort


class LocalFilePolicyProvider(PolicyProviderPort):
    def __init__(self, policy_root: str):
        if not policy_root:
            raise ValueError("policy_root is required")
        self.policy_root = policy_root

    def load_policies(self) -> list[PermissionPolicy]:
        policies: list[PermissionPolicy] = []
        if not os.path.isdir(self.policy_root):
            raise PermissionPolicyError(f"policy root missing: {self.policy_root}")
        for name in sorted(os.listdir(self.policy_root)):
            if not name.endswith(".yaml") and not name.endswith(".yml"):
                continue
            path = os.path.join(self.policy_root, name)
            with open(path, "r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle) or {}
            policies.extend(parse_policies(payload))
        return policies
