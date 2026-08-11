from dataclasses import replace
import hashlib
from threading import RLock

from .models import AgentDeploymentPolicy, ArtifactBinding, RolloutStrategy


class AgentDeploymentManager:
    """Maintains immutable artifact bindings and deterministic rollout selection."""

    def __init__(self, artifact_repository, on_change=None):
        self.artifact_repository = artifact_repository
        self._policies: dict[str, AgentDeploymentPolicy] = {}
        self._history: dict[str, list[AgentDeploymentPolicy]] = {}
        self._lock = RLock()
        self._on_change = on_change

    def deploy(self, policy: AgentDeploymentPolicy) -> AgentDeploymentPolicy:
        self._validate_binding(policy.active_artifact)
        if policy.candidate_artifact is not None:
            self._validate_binding(policy.candidate_artifact)
        with self._lock:
            previous = self._policies.get(policy.agent_id)
            if previous is not None:
                self._history.setdefault(policy.agent_id, []).append(previous)
            self._policies[policy.agent_id] = policy
        self._notify("deployment", previous, policy)
        return policy

    def get(self, agent_id: str) -> AgentDeploymentPolicy:
        try:
            return self._policies[agent_id]
        except KeyError as error:
            raise KeyError(f"Deployment policy not found: {agent_id}") from error

    def select(self, agent_id: str, routing_key: str) -> ArtifactBinding:
        if not routing_key:
            raise ValueError("routing_key is required for stable rollout selection")
        policy = self.get(agent_id)
        candidate = policy.candidate_artifact
        if candidate is None or policy.rollout_percentage == 0:
            return policy.active_artifact
        bucket = int.from_bytes(
            hashlib.sha256(routing_key.encode("utf-8")).digest()[:8], "big"
        ) % 100
        return candidate if bucket < policy.rollout_percentage else policy.active_artifact

    def promote_candidate(self, agent_id: str) -> AgentDeploymentPolicy:
        policy = self.get(agent_id)
        if policy.candidate_artifact is None:
            raise ValueError("No candidate artifact to promote")
        promoted = replace(
            policy,
            active_artifact=policy.candidate_artifact,
            candidate_artifact=None,
            rollout_strategy=RolloutStrategy.IMMEDIATE,
            rollout_percentage=0,
        )
        return self.deploy(promoted)

    def rollback(self, agent_id: str) -> AgentDeploymentPolicy:
        with self._lock:
            history = self._history.get(agent_id, [])
            if not history:
                raise ValueError(f"No deployment available for rollback: {agent_id}")
            current = self.get(agent_id)
            restored = history.pop()
            self._policies[agent_id] = restored
        self._notify("rollback", current, restored)
        return restored

    def _validate_binding(self, binding: ArtifactBinding) -> None:
        artifact = self.artifact_repository.get(binding.artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact does not exist: {binding.artifact_id}")
        if getattr(artifact, "artifact_hash", None) != binding.artifact_hash:
            raise ValueError("Artifact binding hash mismatch")

    def _notify(self, action, previous, current):
        if self._on_change is not None:
            self._on_change(action, previous, current)
