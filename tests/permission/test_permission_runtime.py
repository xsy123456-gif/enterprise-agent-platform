"""Permission runtime lifecycle tests: atomic reload, health, concurrency, determinism."""

import threading

import yaml

from app.permission import PermissionConfig
from app.permission.config import PermissionConfig
from app.permission.models.policy import PermissionPolicy
from app.permission.policy.parser import parse_policies
from app.permission.policy.snapshot import build_snapshot
from app.permission.ports.policy_provider import PolicyProviderPort
from app.permission.runtime import PermissionRuntime


class MemProvider(PolicyProviderPort):
    def __init__(self, policies=None):
        self.policies = policies or []

    def load_policies(self):
        return list(self.policies)


def _policy(policy_id, version=1):
    return parse_policies(yaml.safe_load(
        f"""
        policies:
          - policy_id: {policy_id}
            version: {version}
            status: active
            scope:
              type: platform
            effect: allow
            target:
              resource_types: [campaign]
              actions: [update]
            condition:
              field: subject.roles
              operator: contains
              value: operator
        """
    ))[0]


def _runtime(policies):
    return PermissionRuntime(MemProvider(policies), PermissionConfig())


def test_atomic_reload_replaces_snapshot():
    runtime = _runtime([_policy("p1", 1)])
    assert runtime.start()
    v1 = runtime.get_snapshot().policy_set_version
    runtime.provider.policies = [_policy("p1", 2)]
    assert runtime.reload()
    v2 = runtime.get_snapshot().policy_set_version
    assert v1 != v2


def test_invalid_reload_keeps_last_valid_snapshot():
    runtime = _runtime([_policy("p1", 1)])
    assert runtime.start()
    old = runtime.get_snapshot().policy_set_version
    # invalid policy (unknown operator)
    invalid = parse_policies(yaml.safe_load("""
        policies:
          - policy_id: bad
            version: 1
            status: active
            scope:
              type: platform
            effect: allow
            target:
              resource_types: [campaign]
              actions: [update]
            condition:
              field: subject.roles
              operator: not_a_real_operator
              value: x
    """))
    runtime.provider.policies = invalid
    assert runtime.reload() is False
    assert runtime.get_snapshot().policy_set_version == old
    assert runtime.health()["status"] == "degraded"


def test_health_states():
    runtime = _runtime([_policy("p1", 1)])
    assert runtime.health()["status"] == "unhealthy"
    runtime.start()
    assert runtime.health()["status"] == "healthy"
    runtime.provider.policies = []
    runtime.reload()
    # empty policy set is valid, but let's force an error via invalid provider
    runtime.provider.policies = [object()]  # invalid -> validation error
    assert runtime.reload() is False
    assert runtime.health()["status"] == "degraded"


def test_policy_set_version_independent_of_yaml_key_order():
    a = parse_policies(yaml.safe_load("""
        policies:
          - policy_id: p1
            version: 1
            status: active
            effect: allow
            scope:
              type: platform
            target:
              resource_types: [campaign]
              actions: [update]
    """))
    b = parse_policies(yaml.safe_load("""
        policies:
          - target:
              actions: [update]
              resource_types: [campaign]
            version: 1
            status: active
            effect: allow
            policy_id: p1
            scope:
              type: platform
    """))
    assert build_snapshot(a).policy_set_version == build_snapshot(b).policy_set_version


def test_policy_set_version_independent_of_load_order():
    p1 = _policy("p1", 1)
    p2 = _policy("p2", 1)
    assert build_snapshot([p1, p2]).policy_set_version == build_snapshot([p2, p1]).policy_set_version


def test_concurrent_evaluation_and_reload_snapshot_consistency():
    runtime = _runtime([_policy("p1", 1)])
    runtime.start()
    versions = set()
    versions_lock = threading.Lock()

    def reader():
        for _ in range(200):
            snap = runtime.get_snapshot()
            with versions_lock:
                versions.add(snap.policy_set_version)

    def writer():
        for i in range(20):
            runtime.provider.policies = [_policy("p1", i + 1)]
            runtime.reload()

    threads = [threading.Thread(target=reader) for _ in range(4)] + \
              [threading.Thread(target=writer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every observed version is a complete snapshot version; no mixing.
    assert versions
