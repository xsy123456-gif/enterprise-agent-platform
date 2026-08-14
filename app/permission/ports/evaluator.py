"""Policy evaluator port — replaceable decision engine."""

from abc import ABC, abstractmethod

from app.permission.evaluation.combiner import EvaluationResult
from app.permission.models.request import PermissionRequest
from app.permission.models.snapshot import PolicySnapshot


class PolicyEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        request: PermissionRequest,
        snapshot: PolicySnapshot,
    ) -> EvaluationResult:
        raise NotImplementedError
