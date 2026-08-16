"""Business scenario contract (validation harness, not the Benchmark).

A ``ScenarioInput`` pairs a plan with deterministic facts; a ``GroundTruth``
states the expected signals, primary causes, excluded causes, priority and
unknown causes.  Used to prove a plan does not over-attribute (false
correlation) or fabricate causes.
"""

from dataclasses import dataclass, field

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans import (
    CompileContext,
    DiagnosticPlanRegistry,
    FakeFactQueryExecutor,
    PlanExecutor,
)


@dataclass(frozen=True)
class ScenarioInput:
    scenario_id: str
    plan_id: str
    subject: SubjectRef
    facts: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GroundTruth:
    expected_signals: tuple[str, ...] = ()
    primary_causes: tuple[str, ...] = ()
    excluded_causes: tuple[str, ...] = ()
    expected_priority: str | None = None
    expected_unknowns: tuple[str, ...] = ()


def run_scenario(plan, compile_context: CompileContext, scenario: ScenarioInput,
                 trusted_context=None):
    """Compile + execute ``plan`` against ``scenario`` facts and return the
    ``PlanExecutionState``."""
    registry = DiagnosticPlanRegistry(compile_context)
    registry.register(plan)
    registry.activate(plan.plan_id)
    fact_executor = FakeFactQueryExecutor(dict(scenario.facts))
    return PlanExecutor().execute(
        registry.get_active_ir(plan.plan_id), compile_context, fact_executor,
        scenario.subject, trusted_context=trusted_context,
    )


def assert_ground_truth(state, ground_truth: GroundTruth):
    signals = {s.signal_code for s in state.signals}
    assert set(ground_truth.expected_signals) <= signals, (
        f"expected signals {set(ground_truth.expected_signals)} missing from "
        f"{signals}"
    )
    primary = {c.cause_code for c in state.causes if c.causal_role == "PRIMARY"}
    assert primary == set(ground_truth.primary_causes), (
        f"primary causes {primary} != expected {set(ground_truth.primary_causes)}"
    )
    for code in ground_truth.excluded_causes:
        assert code not in primary, f"excluded cause {code!r} became PRIMARY"
    if ground_truth.expected_priority is not None:
        assert state.priority is not None, "priority was not produced"
        assert state.priority.level == ground_truth.expected_priority, (
            f"priority {state.priority.level} != expected "
            f"{ground_truth.expected_priority}"
        )
    for code in ground_truth.expected_unknowns:
        cause = next((c for c in state.causes if c.cause_code == code), None)
        assert cause is not None, f"expected UNKNOWN cause {code!r} missing"
        assert cause.support_level == "INSUFFICIENT_EVIDENCE", (
            f"cause {code!r} support {cause.support_level} != INSUFFICIENT_EVIDENCE"
        )


__all__ = ["ScenarioInput", "GroundTruth", "run_scenario", "assert_ground_truth"]
