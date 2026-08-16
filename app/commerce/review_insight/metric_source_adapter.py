"""ReviewInsight -> metric source adapter skeleton (Phase 11.6).

ReviewInsight does NOT compute metrics.  This skeleton only declares the
deferred metric surface; actual metric computation is a later phase.
"""

REVIEW_METRIC_NEGATIVE_REVIEW_RATE = "NEGATIVE_REVIEW_RATE"
REVIEW_METRIC_ISSUE_FREQUENCY = "ISSUE_FREQUENCY"
REVIEW_METRIC_TOP_NEGATIVE_TOPIC = "TOP_NEGATIVE_TOPIC"
REVIEW_METRIC_ISSUE_TREND = "ISSUE_TREND"
REVIEW_METRICS = (
    REVIEW_METRIC_NEGATIVE_REVIEW_RATE,
    REVIEW_METRIC_ISSUE_FREQUENCY,
    REVIEW_METRIC_TOP_NEGATIVE_TOPIC,
    REVIEW_METRIC_ISSUE_TREND,
)


class MetricSourceAdapter:
    """Skeleton only — no metric computation in Phase 11."""

    def available_metrics(self) -> tuple[str, ...]:
        return REVIEW_METRICS

    def map(self, insight):
        raise NotImplementedError(
            "ReviewInsight metric computation is deferred to a later phase"
        )


__all__ = [
    "MetricSourceAdapter",
    "REVIEW_METRICS",
    "REVIEW_METRIC_NEGATIVE_REVIEW_RATE",
    "REVIEW_METRIC_ISSUE_FREQUENCY",
    "REVIEW_METRIC_TOP_NEGATIVE_TOPIC",
    "REVIEW_METRIC_ISSUE_TREND",
]
