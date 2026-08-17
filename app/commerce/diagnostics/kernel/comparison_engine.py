"""ComparisonEngine — current vs baseline period comparison.

Computes only ``current_value``, ``baseline_value``, ``absolute_change`` and
``relative_change``.  It does NOT classify anomalies, trends, or any
interpretation — those belong to the Trend / Anomaly engines in later phases.
"""

from app.commerce.diagnostics.models import ComparisonResult


class ComparisonEngine:

    def compare(self, current_value, baseline_value):
        """Return a ``ComparisonResult`` for one pair of period values.

        ``relative_change`` is ``None`` when the baseline is zero (or when
        either value is ``None``); ``absolute_change`` is ``None`` when either
        value is ``None``.
        """
        if current_value is None or baseline_value is None:
            return ComparisonResult(
                current_value=current_value,
                baseline_value=baseline_value,
                absolute_change=None,
                relative_change=None,
            )
        current = float(current_value)
        baseline = float(baseline_value)
        absolute_change = current - baseline
        if baseline == 0:
            relative_change = None
        else:
            relative_change = (current - baseline) / baseline
        return ComparisonResult(
            current_value=current,
            baseline_value=baseline,
            absolute_change=absolute_change,
            relative_change=relative_change,
        )


__all__ = ["ComparisonEngine"]
