"""Experiment traffic assignment (Phase 17.4)."""

import hashlib

from app.platform.intelligence.experiment.domain import (
    STRATEGY_SHADOW,
    AgentExperiment,
)

CONTROL = "control"
CANDIDATE = "candidate"


class TrafficAssignment:

    def __init__(self, experiment: AgentExperiment):
        self.experiment = experiment

    def route(self, user_key) -> str:
        if self.experiment.strategy == STRATEGY_SHADOW:
            return CONTROL
        bucket = self._bucket(user_key)
        if bucket < self.experiment.traffic_ratio * 100:
            return CANDIDATE
        return CONTROL

    @staticmethod
    def _bucket(user_key):
        digest = hashlib.sha256(str(user_key).encode("utf-8")).hexdigest()
        return int(digest[:2], 16) % 100


__all__ = ["TrafficAssignment", "CONTROL", "CANDIDATE"]
