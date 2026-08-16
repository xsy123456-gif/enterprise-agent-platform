"""Enterprise Agent Intelligence Optimization Platform (Phase 17).

Continuous agent intelligence optimization: evaluate -> optimize -> approve ->
improve -> experiment -> release -> repeat.  No Agent may autonomously modify
itself — every change is versioned, auditable, governed and deployable through
a controlled lifecycle.
"""

from app.platform.intelligence.audit import (
    IntelligenceAuditLogger,
    IntelligenceAuditRecord,
)
from app.platform.intelligence.errors import (
    DeploymentDeniedError,
    EvaluationError,
    ExperimentError,
    GovernanceDeniedError,
    ImprovementError,
    IntelligenceError,
    OptimizationError,
)
from app.platform.intelligence.evaluation import (
    AgentEvaluation,
    EvaluationEngine,
    EvaluationMetric,
    EvaluationMetricRegistry,
    EvaluationMetrics,
    EvaluationSubscriber,
    ExecutionSample,
)
from app.platform.intelligence.experiment import (
    AgentExperiment,
    ExperimentEvaluator,
    TrafficAssignment,
)
from app.platform.intelligence.feedback import (
    AgentFeedback,
    FeedbackProcessor,
    FeedbackSignal,
)
from app.platform.intelligence.governance import (
    OptimizationGovernance,
    OptimizationPolicy,
)
from app.platform.intelligence.improvement import (
    AgentImprovementRequest,
    ImprovementApproval,
    ImprovementLifecycle,
)
from app.platform.intelligence.optimization import (
    DetectedIssue,
    OptimizationGenerator,
    OptimizationProposal,
    PatternDetector,
)

__all__ = [
    "AgentEvaluation",
    "ExecutionSample",
    "EvaluationEngine",
    "EvaluationSubscriber",
    "EvaluationMetrics",
    "EvaluationMetric",
    "EvaluationMetricRegistry",
    "OptimizationProposal",
    "DetectedIssue",
    "PatternDetector",
    "OptimizationGenerator",
    "AgentImprovementRequest",
    "ImprovementLifecycle",
    "ImprovementApproval",
    "AgentExperiment",
    "TrafficAssignment",
    "ExperimentEvaluator",
    "AgentFeedback",
    "FeedbackProcessor",
    "FeedbackSignal",
    "OptimizationPolicy",
    "OptimizationGovernance",
    "IntelligenceAuditRecord",
    "IntelligenceAuditLogger",
    "IntelligenceError",
    "EvaluationError",
    "OptimizationError",
    "ImprovementError",
    "ExperimentError",
    "GovernanceDeniedError",
    "DeploymentDeniedError",
]
