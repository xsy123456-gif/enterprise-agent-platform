"""TrendEngine — versioned, deterministic trend classification.

Algorithm ``rolling_baseline_slope_v1``.  For a chronological series:

- ``slope`` = (recent-window mean - baseline-window mean) / |baseline mean|;
- ``d_max`` = max relative deviation from the baseline mean;
- ``head_tail`` = relative change between the earliest and latest
  ``recent_window`` points (transient detection);
- ``persistent_count`` = how many of the last ``persistence_periods`` points
  stay on the deviating side (|dev| >= stability).

Classification (priority order):

1. UNKNOWN    — fewer than ``trend_min_points`` samples;
2. STABLE     — |slope| and d_max both <= ``stability_threshold``;
3. TRANSIENT  — returned to the head level (|head_tail| <= stability) but a
                large deviation (>= ``sudden_threshold``) occurred in between;
4. SUDDEN     — |slope| >= ``sudden_threshold`` (fast change);
5. PERSISTENT — ``persistent_count`` >= ``persistence_periods`` (sustained);
6. GRADUAL    — otherwise (moderate, not yet established change).

All thresholds come from a versioned ``DiagnosticPolicy``; the algorithm version
is recorded for replay.
"""

from app.commerce.contracts.signal import (
    DIRECTION_DOWN,
    DIRECTION_STABLE,
    DIRECTION_UP,
)
from app.commerce.diagnostics.models import (
    TREND_GRADUAL,
    TREND_PERSISTENT,
    TREND_STABLE,
    TREND_SUDDEN,
    TREND_TRANSIENT,
    TREND_UNKNOWN,
    TrendResult,
)

ALGORITHM_VERSION = "rolling_baseline_slope_v1"


def _mean(values):
    return sum(values) / len(values)


class TrendEngine:
    ALGORITHM_VERSION = ALGORITHM_VERSION

    def detect_trend(self, values, policy):
        """Classify a chronological series of numeric values (oldest-first)."""
        values = [float(v) for v in values]
        n = len(values)
        if n < policy.trend_min_points:
            return TrendResult(
                pattern=TREND_UNKNOWN, direction=DIRECTION_STABLE, slope=None,
                algorithm_version=self.ALGORITHM_VERSION, policy_version=policy.version,
                sample_size=n,
            )

        baseline_mean = _mean(values[: policy.baseline_window])
        recent_mean = _mean(values[-policy.recent_window:])
        denom = abs(baseline_mean) if baseline_mean != 0 else 1.0
        slope = (recent_mean - baseline_mean) / denom
        d_max = max(abs(v - baseline_mean) / denom for v in values)

        head = _mean(values[: policy.recent_window])
        tail = _mean(values[-policy.recent_window:])
        head_denom = abs(head) if head != 0 else 1.0
        head_tail = (tail - head) / head_denom
        middle_max = max(abs(v - head) / head_denom for v in values)

        direction = DIRECTION_STABLE
        if slope > 0:
            direction = DIRECTION_UP
        elif slope < 0:
            direction = DIRECTION_DOWN

        if abs(slope) <= policy.stability_threshold and d_max <= policy.stability_threshold:
            pattern = TREND_STABLE
        elif abs(head_tail) <= policy.stability_threshold and middle_max >= policy.sudden_threshold:
            pattern = TREND_TRANSIENT
        elif abs(slope) >= policy.sudden_threshold:
            pattern = TREND_SUDDEN
        else:
            persistent_count = sum(
                1 for v in values[-policy.persistence_periods:]
                if (v - baseline_mean) * slope > 0
                and abs(v - baseline_mean) / denom >= policy.stability_threshold
            )
            pattern = (
                TREND_PERSISTENT if persistent_count >= policy.persistence_periods
                else TREND_GRADUAL
            )

        return TrendResult(
            pattern=pattern, direction=direction, slope=round(slope, 6),
            algorithm_version=self.ALGORITHM_VERSION, policy_version=policy.version,
            sample_size=n,
        )


__all__ = ["TrendEngine", "ALGORITHM_VERSION"]
