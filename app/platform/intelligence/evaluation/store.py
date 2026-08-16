"""Evaluation store port (Phase 18.10).

``AgentEvaluation`` is operational history (Type B): it must have a sink/store
boundary.  The ``EvaluationSubscriber`` produces evaluations via the engine;
the store only persists them.
"""

from abc import ABC, abstractmethod


class EvaluationStore(ABC):
    @abstractmethod
    def put(self, evaluation):
        pass

    @abstractmethod
    def list(self):
        pass


class InMemoryEvaluationStore(EvaluationStore):

    def __init__(self):
        self._evaluations = []

    def put(self, evaluation):
        self._evaluations.append(evaluation)
        return evaluation

    def list(self):
        return list(self._evaluations)


__all__ = ["EvaluationStore", "InMemoryEvaluationStore"]
