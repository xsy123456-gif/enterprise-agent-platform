"""Data provenance helpers.

Every canonical read must be able to state where the data came from
(CANONICAL / REFRESHED_CANONICAL / DERIVED_CANONICAL) and which schema /
adapter / connector versions produced it.
"""

from app.commerce.contracts.query import DataProvenance, PROVENANCE_CANONICAL


def canonical_provenance(canonical_schema_version, upstream_platform=""):
    return DataProvenance(
        source_type=PROVENANCE_CANONICAL,
        canonical_schema_version=canonical_schema_version,
        upstream_platform=upstream_platform,
    )


__all__ = ["canonical_provenance"]
