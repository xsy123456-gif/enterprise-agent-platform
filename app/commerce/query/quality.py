"""Data quality helpers.

Data quality (VALID / PARTIAL / STALE / INSUFFICIENT / INVALID) is evaluated
independently from freshness and provenance.  Required-data absence must be
reported as INSUFFICIENT, never silently treated as an empty success.
"""

from app.commerce.contracts.query import (
    QUALITY_INSUFFICIENT,
    QUALITY_VALID,
    DataQuality,
)


def evaluate_quality(data, required_fields=(), validator_version=""):
    """Evaluate data quality for a collection of records.

    ``data`` may be a list/tuple of records or a single record.  An empty
    collection is INSUFFICIENT; missing required fields on the first record are
    reported via ``missing_fields``.
    """
    records = data if isinstance(data, (list, tuple)) else [data]
    records = [r for r in records if r is not None]
    if not records:
        return DataQuality(
            status=QUALITY_INSUFFICIENT,
            completeness=0.0,
            validator_version=validator_version,
        )
    missing = []
    for field in required_fields:
        for record in records:
            if getattr(record, field, None) is None:
                missing.append(field)
                break
    if missing:
        return DataQuality(
            status=QUALITY_INSUFFICIENT,
            completeness=1.0 - len(missing) / len(required_fields),
            missing_fields=tuple(sorted(set(missing))),
            validator_version=validator_version,
        )
    return DataQuality(status=QUALITY_VALID, completeness=1.0, validator_version=validator_version)


__all__ = ["evaluate_quality"]
