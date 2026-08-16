"""Experiment subpackage (Phase 17.4)."""

from app.platform.intelligence.experiment.assignment import (
    CANDIDATE,
    CONTROL,
    TrafficAssignment,
)
from app.platform.intelligence.experiment.domain import AgentExperiment
from app.platform.intelligence.experiment.evaluator import ExperimentEvaluator

__all__ = ["AgentExperiment", "TrafficAssignment", "ExperimentEvaluator",
           "CONTROL", "CANDIDATE"]
