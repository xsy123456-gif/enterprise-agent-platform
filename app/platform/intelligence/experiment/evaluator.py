"""Experiment evaluator (Phase 17.4).

Release decision: the candidate may release only when it beats the control and
risk stays below threshold.  Never released on an LLM opinion.
"""


class ExperimentEvaluator:

    def __init__(self, max_risk=0.3):
        self.max_risk = max_risk

    def decide(self, control_quality, candidate_quality, risk) -> bool:
        return candidate_quality > control_quality and risk <= self.max_risk


__all__ = ["ExperimentEvaluator"]
