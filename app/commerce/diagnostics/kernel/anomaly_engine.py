"""AnomalyEngine — versioned, deterministic anomaly detection.

Decision model (``relative_change_zscore_v1``), considering, in order:

1. data presence      — current value absent -> UNKNOWN;
2. applicability      — subject type outside the policy -> NOT_APPLICABLE;
3. sample sufficiency — missing / tiny baseline -> INSUFFICIENT_DATA;
4. relative change    — (current - baseline) / baseline;
5. historical variance — z-score of current vs the baseline series;
6. severity           — max(relative-change level, z-score level) mapped to
                        NORMAL / WARNING / ABNORMAL / CRITICAL.

It is never a bare ``change < -10%`` rule: relative and absolute change are
combined with sample sufficiency, historical variance and data quality.
"""

import uuid
from statistics import mean, stdev

from app.commerce.contracts.signal import (
    DIRECTION_DOWN,
    DIRECTION_STABLE,
    DIRECTION_UP,
    SIGNAL_ABNORMAL,
    SIGNAL_CRITICAL,
    SIGNAL_INSUFFICIENT_DATA,
    SIGNAL_NORMAL,
    SIGNAL_NOT_APPLICABLE,
    SIGNAL_UNKNOWN,
    SIGNAL_WARNING,
    Signal,
)

ALGORITHM_VERSION = "relative_change_zscore_v1"

_STATUS_LEVELS = (SIGNAL_NORMAL, SIGNAL_WARNING, SIGNAL_ABNORMAL, SIGNAL_CRITICAL)


class AnomalyEngine:
    ALGORITHM_VERSION = ALGORITHM_VERSION

    def detect(self, subject, signal_code, domain, current_value, baseline_value,
               baseline_series, policy, evidence_ids=(), detected_at="", signal_id=None):
        """Produce a ``Signal`` for one metric anomaly.

        ``baseline_series`` is the historical series used for variance/z-score;
        ``policy`` supplies all thresholds and sample-sufficiency floors.
        """
        base = dict(
            signal_id=signal_id or uuid.uuid4().hex,
            signal_code=signal_code,
            domain=domain,
            subject=subject,
            detection_method=self.ALGORITHM_VERSION,
            algorithm_version=self.ALGORITHM_VERSION,
            policy_version=policy.version,
            detected_at=detected_at,
            evidence_ids=tuple(evidence_ids),
        )
        if current_value is None:
            return Signal(**base, status=SIGNAL_UNKNOWN, direction=DIRECTION_STABLE)
        if policy.applicable_subject_types and subject.type not in policy.applicable_subject_types:
            return Signal(**base, status=SIGNAL_NOT_APPLICABLE, direction=DIRECTION_STABLE)
        if baseline_value is None or baseline_value < policy.min_baseline_volume:
            return Signal(**base, status=SIGNAL_INSUFFICIENT_DATA, direction=DIRECTION_STABLE)
        if policy.min_sample_size and (
            baseline_series is None or len(baseline_series) < policy.min_sample_size
        ):
            return Signal(**base, status=SIGNAL_INSUFFICIENT_DATA, direction=DIRECTION_STABLE)

        relative_change = (
            (current_value - baseline_value) / baseline_value if baseline_value != 0 else None
        )
        absolute_change = current_value - baseline_value
        zscore = None
        if baseline_series and len(baseline_series) >= 2:
            mu = mean(baseline_series)
            sd = stdev(baseline_series)
            if sd > 0:
                zscore = (current_value - mu) / sd

        relative_level = (
            self._level(
                abs(relative_change),
                (policy.warning_relative_change, policy.abnormal_relative_change,
                 policy.critical_relative_change),
            )
            if relative_change is not None else 0
        )
        zscore_level = (
            self._level(
                abs(zscore),
                (policy.warning_zscore, policy.abnormal_zscore, policy.critical_zscore),
            )
            if zscore is not None else 0
        )
        level = max(relative_level, zscore_level)
        status = _STATUS_LEVELS[level]

        direction = DIRECTION_STABLE
        if relative_change is not None and relative_change > 0:
            direction = DIRECTION_UP
        elif relative_change is not None and relative_change < 0:
            direction = DIRECTION_DOWN

        anomaly_score = zscore if zscore is not None else abs(relative_change)
        return Signal(
            **base, status=status, direction=direction,
            magnitude=round(relative_change, 6) if relative_change is not None else None,
            anomaly_score=round(anomaly_score, 6) if anomaly_score is not None else None,
        )

    @staticmethod
    def _level(value, thresholds):
        level = 0
        for threshold in thresholds:
            if value >= threshold:
                level += 1
        return level


__all__ = ["AnomalyEngine", "ALGORITHM_VERSION"]
