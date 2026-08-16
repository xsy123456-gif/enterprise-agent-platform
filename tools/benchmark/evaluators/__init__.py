"""Benchmark evaluators (Phase 18.15).

Five independent, deterministic evaluators (E1..E5).  Each takes captured
platform output + a ground-truth spec and returns an ``EvaluationResult``.
"""

from tools.benchmark.evaluators.e1_data import evaluate_e1
from tools.benchmark.evaluators.e2_metrics import evaluate_e2
from tools.benchmark.evaluators.e3_diagnostic import evaluate_e3
from tools.benchmark.evaluators.e4_governance import evaluate_e4
from tools.benchmark.evaluators.e5_response import evaluate_e5

EVALUATORS = {
    "E1": evaluate_e1,
    "E2": evaluate_e2,
    "E3": evaluate_e3,
    "E4": evaluate_e4,
    "E5": evaluate_e5,
}

__all__ = [
    "EVALUATORS",
    "evaluate_e1",
    "evaluate_e2",
    "evaluate_e3",
    "evaluate_e4",
    "evaluate_e5",
]
