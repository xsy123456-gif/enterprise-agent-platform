from types import SimpleNamespace

import pytest

from app.artifacts.storage import InMemoryArtifactRepository
from app.runtime.production import (
    AgentDeploymentManager,
    AgentDeploymentPolicy,
    ArtifactBinding,
    RolloutStrategy,
)


def setup_deployments():
    repository = InMemoryArtifactRepository()
    for version, digest in (("1.0", "hash-1"), ("1.1", "hash-2")):
        repository.save(SimpleNamespace(
            artifact_id=f"sales:{version}", artifact_hash=digest,
            agent_id="sales_agent", agent_version=version,
        ))
    return repository, AgentDeploymentManager(repository)


def binding(version, digest):
    return ArtifactBinding(f"sales:{version}", digest, version)


def test_deployment_binds_exact_artifact_identity():
    _, manager = setup_deployments()
    policy = manager.deploy(AgentDeploymentPolicy("sales_agent", binding("1.0", "hash-1")))
    assert policy.active_artifact.artifact_hash == "hash-1"


@pytest.mark.parametrize("percentage,expected_candidate", [(0, False), (100, True)])
def test_rollout_boundaries(percentage, expected_candidate):
    _, manager = setup_deployments()
    manager.deploy(AgentDeploymentPolicy(
        "sales_agent", binding("1.0", "hash-1"), binding("1.1", "hash-2"),
        RolloutStrategy.PERCENTAGE, percentage,
    ))
    selected = manager.select("sales_agent", "execution-1")
    assert (selected.artifact_hash == "hash-2") is expected_candidate


def test_rollout_selection_is_stable_for_execution_key():
    _, manager = setup_deployments()
    manager.deploy(AgentDeploymentPolicy(
        "sales_agent", binding("1.0", "hash-1"), binding("1.1", "hash-2"),
        RolloutStrategy.CANARY, 25,
    ))
    assert manager.select("sales_agent", "same-key") == manager.select(
        "sales_agent", "same-key"
    )


def test_promote_candidate_makes_it_active_at_100_percent():
    _, manager = setup_deployments()
    manager.deploy(AgentDeploymentPolicy(
        "sales_agent", binding("1.0", "hash-1"), binding("1.1", "hash-2"),
        RolloutStrategy.CANARY, 10,
    ))
    policy = manager.promote_candidate("sales_agent")
    assert policy.active_artifact.artifact_hash == "hash-2"
    assert policy.candidate_artifact is None
    assert manager.select("sales_agent", "any").artifact_hash == "hash-2"


def test_rollback_restores_previous_exact_binding():
    _, manager = setup_deployments()
    original = AgentDeploymentPolicy("sales_agent", binding("1.0", "hash-1"))
    manager.deploy(original)
    manager.deploy(AgentDeploymentPolicy("sales_agent", binding("1.1", "hash-2")))
    assert manager.rollback("sales_agent") == original


@pytest.mark.parametrize(
    "bad_binding",
    [
        ArtifactBinding("missing", "hash", "1"),
        ArtifactBinding("sales:1.0", "wrong-hash", "1.0"),
    ],
)
def test_invalid_artifact_binding_is_rejected(bad_binding):
    _, manager = setup_deployments()
    with pytest.raises(ValueError, match="Artifact"):
        manager.deploy(AgentDeploymentPolicy("sales_agent", bad_binding))


def test_rollout_requires_nonempty_stable_key():
    _, manager = setup_deployments()
    manager.deploy(AgentDeploymentPolicy("sales_agent", binding("1.0", "hash-1")))
    with pytest.raises(ValueError, match="routing_key"):
        manager.select("sales_agent", "")
