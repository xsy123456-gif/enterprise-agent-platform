"""Diagnostic infrastructure (Phases 3-4).

Deterministic computation of DERIVED metrics (MetricEngine), current-vs-baseline
comparison (ComparisonEngine), and the diagnostic kernel engines (Trend /
Anomaly / Contribution / Rule / Impact / Priority) backed by versioned
definitions (MetricDefinitionRegistry, DiagnosticPolicyRegistry, RuleSetRegistry,
ImpactFormulaRegistry, PriorityPolicyRegistry).

Engines never hard-code business knowledge: thresholds, rules, formulas and
priority weights all come from versioned definitions.  No LLM, no prompt, no
eval/exec, no arbitrary Python rules.
"""

from app.commerce.diagnostics.definitions.impact import ImpactFormula
from app.commerce.diagnostics.definitions.metrics import (
    build_core_metric_definitions,
    build_core_metric_registry,
)
from app.commerce.diagnostics.definitions.policies import DiagnosticPolicy
from app.commerce.diagnostics.definitions.priority import (
    PRIORITY_FACTORS,
    PriorityPolicy,
)
from app.commerce.diagnostics.definitions.rules import (
    Rule,
    RuleCondition,
    RuleConsequent,
    RuleSet,
)
from app.commerce.diagnostics.kernel.anomaly_engine import AnomalyEngine
from app.commerce.diagnostics.kernel.comparison_engine import ComparisonEngine
from app.commerce.diagnostics.kernel.contribution_engine import ContributionEngine
from app.commerce.diagnostics.kernel.impact_engine import ImpactEngine
from app.commerce.diagnostics.kernel.metric_engine import MetricEngine
from app.commerce.diagnostics.kernel.priority_engine import PriorityEngine
from app.commerce.diagnostics.kernel.rule_engine import RuleEngine
from app.commerce.diagnostics.kernel.trend_engine import TrendEngine
from app.commerce.diagnostics.models import (
    METRIC_STATUS_COMPLETE,
    METRIC_STATUS_INSUFFICIENT,
    METRIC_STATUS_NULL_RESULT,
    METRIC_STATUSES,
    TREND_GRADUAL,
    TREND_PATTERNS,
    TREND_PERSISTENT,
    TREND_STABLE,
    TREND_SUDDEN,
    TREND_TRANSIENT,
    TREND_UNKNOWN,
    ComparisonResult,
    ContributionAnalysis,
    ContributionResult,
    MetricResult,
    PriorityFactors,
    TrendResult,
)
from app.commerce.diagnostics.registry.impact_registry import ImpactFormulaRegistry
from app.commerce.diagnostics.registry.metric_registry import MetricDefinitionRegistry
from app.commerce.diagnostics.registry.policy_registry import DiagnosticPolicyRegistry
from app.commerce.diagnostics.registry.priority_registry import PriorityPolicyRegistry
from app.commerce.diagnostics.registry.resolver import MetricRequirementResolver
from app.commerce.diagnostics.registry.ruleset_registry import RuleSetRegistry

__all__ = [
    "MetricEngine",
    "ComparisonEngine",
    "TrendEngine",
    "AnomalyEngine",
    "ContributionEngine",
    "RuleEngine",
    "ImpactEngine",
    "PriorityEngine",
    "MetricResult",
    "ComparisonResult",
    "TrendResult",
    "ContributionResult",
    "ContributionAnalysis",
    "PriorityFactors",
    "MetricDefinitionRegistry",
    "MetricRequirementResolver",
    "DiagnosticPolicyRegistry",
    "RuleSetRegistry",
    "ImpactFormulaRegistry",
    "PriorityPolicyRegistry",
    "DiagnosticPolicy",
    "RuleCondition",
    "RuleConsequent",
    "Rule",
    "RuleSet",
    "ImpactFormula",
    "PriorityPolicy",
    "PRIORITY_FACTORS",
    "build_core_metric_definitions",
    "build_core_metric_registry",
    "METRIC_STATUS_COMPLETE",
    "METRIC_STATUS_INSUFFICIENT",
    "METRIC_STATUS_NULL_RESULT",
    "METRIC_STATUSES",
    "TREND_PATTERNS",
    "TREND_SUDDEN",
    "TREND_GRADUAL",
    "TREND_PERSISTENT",
    "TREND_TRANSIENT",
    "TREND_STABLE",
    "TREND_UNKNOWN",
]
