"""Typed step handlers for the deterministic plan executor.

Each handler receives ``(step, state, context)`` and mutates ``state`` with a
typed output.  Handlers only call the deterministic Phase 3-4 engines and the
``FactQueryExecutorPort`` (invoked with the Runtime-injected trusted context);
they never touch Repository / QueryService / PostgreSQL and never invoke an LLM.
"""

import uuid

from app.commerce.contracts.diagnostic_result import (
    DIAG_STATUS_COMPLETED,
    DIAG_STATUS_INSUFFICIENT_DATA,
    DiagnosticResult,
)
from app.commerce.contracts.evidence import Evidence
from app.commerce.contracts.query import DataQuality
from app.commerce.diagnostics.kernel.anomaly_engine import AnomalyEngine
from app.commerce.diagnostics.kernel.contribution_engine import ContributionEngine
from app.commerce.diagnostics.kernel.impact_engine import ImpactEngine
from app.commerce.diagnostics.kernel.metric_engine import MetricEngine
from app.commerce.diagnostics.kernel.priority_engine import PriorityEngine
from app.commerce.diagnostics.kernel.rule_engine import RuleEngine
from app.commerce.diagnostics.models import PriorityFactors
from app.commerce.diagnostics.plans.ports import FactQuerySpec
from app.commerce.diagnostics.plans.schema import (
    DataQualityRequirement,
    STEP_ANOMALY_DETECT,
    STEP_CONTRIBUTION_ANALYZE,
    STEP_DATA_QUALITY_GATE,
    STEP_FACT_QUERY,
    STEP_IMPACT_ESTIMATE,
    STEP_METRIC_COMPUTE,
    STEP_PRIORITY_EVALUATE,
    STEP_RESULT_ASSEMBLE,
    STEP_RULE_EVALUATE,
    STOP_INSUFFICIENT_DATA,
    STOP_NORMAL,
    STOP_SUCCESS,
)
from app.commerce.diagnostics.plans.validator import MaxDepthExceededError

_EVIDENCE_QUALITY_MAP = {
    "VALID": "VALID",
    "PARTIAL": "PARTIAL",
    "INSUFFICIENT": "MISSING",
}


def _resolve_value(spec, state):
    if isinstance(spec, (int, float)):
        return float(spec)
    if isinstance(spec, str):
        if spec.startswith("evidence:"):
            return state.evidence_value(spec[len("evidence:"):])
        if spec.startswith("metric:"):
            return state.metric_value(spec[len("metric:"):])
        if ":" in spec:
            raise ValueError(f"unknown value reference {spec!r}")
        return state.metric_value(spec)  # plain name -> metric result
    raise ValueError(f"cannot resolve value reference {spec!r}")


# ── FACT_QUERY ──────────────────────────────────────────────

def handle_fact_query(step, state, context):
    params = step.params
    spec = FactQuerySpec(
        query_id=step.step_id,
        capability=params["capability"],
        resource=params.get("resource", ""),
        subject=state.subject,
        params=params.get("query_params", {}),
    )
    drill_depth = params.get("drill_depth", 1)
    if drill_depth > context.plan_ir.max_depth:
        raise MaxDepthExceededError(
            f"FACT_QUERY step {step.step_id!r} drill_depth {drill_depth} exceeds "
            f"plan max_depth {context.plan_ir.max_depth}"
        )
    state.max_drill_depth = max(state.max_drill_depth, drill_depth)
    result = context.fact_executor.execute(spec, context.trusted_context)
    if getattr(result, "error", None) is not None:
        from app.commerce.diagnostics.plans.ports import FactQueryExecutionError
        raise FactQueryExecutionError(result.error)
    code = params.get("evidence_code", spec.capability)
    state.query_quality[code] = result.quality
    state.freshness[code] = result.freshness
    provenance = None
    if getattr(result, "provenance", None):
        from app.commerce.contracts.query import DataProvenance
        provenance = DataProvenance.from_dict(result.provenance)
    for record in result.records:
        evidence = Evidence(
            evidence_id=uuid.uuid4().hex,
            subject=state.subject,
            evidence_type=params.get("evidence_type", "METRIC"),
            code=code,
            value=record.get("value"),
            quality=_EVIDENCE_QUALITY_MAP.get(result.quality, result.quality),
            provenance=provenance,
        )
        state.evidence.append(evidence)


# ── METRIC_COMPUTE ──────────────────────────────────────────

def handle_metric_compute(step, state, context):
    metric_ref = step.params["metric_ref"]
    definition = context.resolve(metric_ref)
    values = {
        dependency: _resolve_value(spec, state)
        for dependency, spec in step.params.get("inputs", {}).items()
    }
    engine = MetricEngine(context.compile_context.metric_registry)
    result = engine.compute(definition.metric, values, version=definition.version)
    state.metric_results[definition.metric] = result


# ── DATA_QUALITY_GATE ───────────────────────────────────────

def handle_data_quality_gate(step, state, context):
    requirement = DataQualityRequirement.from_dict(step.params.get("requirement"))
    issues = []
    missing = [
        code for code in requirement.required_evidence_codes
        if not state.has_evidence(code)
    ]
    issues.extend(f"missing evidence {code}" for code in missing)
    for evidence in state.evidence:
        if evidence.quality in requirement.unacceptable_evidence_qualities:
            issues.append(f"evidence {evidence.code} quality {evidence.quality}")
    for name, result in state.metric_results.items():
        if result.status in requirement.unacceptable_metric_statuses:
            issues.append(f"metric {name} status {result.status}")
    for code, freshness in state.freshness.items():
        if freshness in requirement.unacceptable_freshness:
            issues.append(f"freshness {code} {freshness}")
    if state.coverage < requirement.min_coverage:
        issues.append(f"coverage {state.coverage} below {requirement.min_coverage}")

    quality = DataQuality(
        status="INSUFFICIENT" if issues else "VALID",
        completeness=1.0 if not issues else max(0.0, 1.0 - len(issues) / max(len(requirement.required_evidence_codes), 1)),
        missing_fields=tuple(missing),
        issues=tuple(issues),
    )
    state.data_quality = quality
    if issues and step.params.get("stop_on_insufficient", False):
        state.outcome = STOP_INSUFFICIENT_DATA
        state.unavailable_evidence.extend(missing)
        state._terminated = True


# ── ANOMALY_DETECT ──────────────────────────────────────────

def handle_anomaly_detect(step, state, context):
    params = step.params
    policy = context.resolve(params["policy_ref"])
    current = _resolve_value(params["metric"], state)
    baseline = None
    if "baseline_metric" in params:
        baseline = _resolve_value(params["baseline_metric"], state)
    else:
        baseline = params.get("baseline_value")
    series = params.get("baseline_series")
    signal = AnomalyEngine().detect(
        subject=state.subject,
        signal_code=params["signal_code"],
        domain=params.get("domain", context.plan_ir.domain if context.plan_ir else ""),
        current_value=current,
        baseline_value=baseline,
        baseline_series=series,
        policy=policy,
        evidence_ids=tuple(e.evidence_id for e in state.evidence),
    )
    state.signals.append(signal)


# ── CONTRIBUTION_ANALYZE ────────────────────────────────────

def handle_contribution_analyze(step, state, context):
    params = step.params
    parent_current = _resolve_value(params["parent_current"], state)
    parent_baseline = _resolve_value(params["parent_baseline"], state)
    children = [
        (child["id"], _resolve_value(child["current"], state),
         _resolve_value(child["baseline"], state))
        for child in params.get("children", ())
    ]
    state.contributions = ContributionEngine().attribute_change(
        parent_current, parent_baseline, children
    )


# ── RULE_EVALUATE ───────────────────────────────────────────

def handle_rule_evaluate(step, state, context):
    rule_set = context.resolve(step.params["rule_set_ref"])
    causes = RuleEngine().evaluate(state.signals, state.evidence, rule_set, state.subject)
    state.causes.extend(causes)


# ── IMPACT_ESTIMATE ─────────────────────────────────────────

def handle_impact_estimate(step, state, context):
    formula = context.resolve(step.params["formula_ref"])
    values = {
        name: _resolve_value(spec, state)
        for name, spec in step.params.get("inputs", {}).items()
    }
    impact = ImpactEngine().compute(formula, values, subject=state.subject)
    state.impacts.append(impact)


# ── PRIORITY_EVALUATE ───────────────────────────────────────

def handle_priority_evaluate(step, state, context):
    policy = context.resolve(step.params["policy_ref"])
    factors = PriorityFactors(
        severity=_resolve_value(step.params["factors"].get("severity", 0.0), state),
        business_impact=_resolve_value(step.params["factors"].get("business_impact", 0.0), state),
        urgency=_resolve_value(step.params["factors"].get("urgency", 0.0), state),
        confidence=_resolve_value(step.params["factors"].get("confidence", 0.0), state),
        actionability=_resolve_value(step.params["factors"].get("actionability", 0.0), state),
    )
    state.priority = PriorityEngine().compute(factors, policy)


# ── RESULT_ASSEMBLE ─────────────────────────────────────────

def handle_result_assemble(step, state, context):
    ir = context.plan_ir
    required_missing = state.missing_required(ir.required_evidence)
    optional_missing = [
        code for code in ir.optional_evidence if not state.has_evidence(code)
    ]
    if required_missing:
        status = DIAG_STATUS_INSUFFICIENT_DATA
        outcome = STOP_INSUFFICIENT_DATA
        state.unavailable_evidence.extend(required_missing)
    else:
        status = DIAG_STATUS_COMPLETED
        abnormal = any(
            s.status in ("ABNORMAL", "CRITICAL") for s in state.signals
        )
        outcome = STOP_SUCCESS if (state.causes or abnormal) else STOP_NORMAL

    result = DiagnosticResult(
        diagnostic_id=uuid.uuid4().hex,
        skill_id=ir.skill_id,
        skill_version=ir.skill_version,
        plan_id=ir.plan_id,
        plan_version=ir.version,
        subject=state.subject,
        analysis_period=state.analysis_period,
        comparison_period=state.comparison_period,
        status=status,
        evidence=tuple(state.evidence),
        signals=tuple(state.signals),
        causes=tuple(state.causes),
        impacts=tuple(state.impacts),
        priority=state.priority,
        data_quality=state.data_quality or DataQuality(),
        coverage=state.coverage,
        unavailable_evidence=tuple(state.unavailable_evidence),
        trace_id=state.execution_id,
        execution_id=state.execution_id,
    )
    state.diagnostic_result = result
    state.outcome = outcome
    state.coverage = 1.0 - (len(required_missing) + len(optional_missing)) / max(
        len(ir.required_evidence) + len(ir.optional_evidence), 1
    )


HANDLERS = {
    STEP_FACT_QUERY: handle_fact_query,
    STEP_METRIC_COMPUTE: handle_metric_compute,
    STEP_DATA_QUALITY_GATE: handle_data_quality_gate,
    STEP_ANOMALY_DETECT: handle_anomaly_detect,
    STEP_CONTRIBUTION_ANALYZE: handle_contribution_analyze,
    STEP_RULE_EVALUATE: handle_rule_evaluate,
    STEP_IMPACT_ESTIMATE: handle_impact_estimate,
    STEP_PRIORITY_EVALUATE: handle_priority_evaluate,
    STEP_RESULT_ASSEMBLE: handle_result_assemble,
}


__all__ = ["HANDLERS"]
