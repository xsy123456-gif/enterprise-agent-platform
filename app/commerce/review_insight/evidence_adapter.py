"""ReviewInsight -> Evidence adapter (Phase 11.6).

ReviewInsight supplies evidence only; the Diagnostic Kernel makes the business
judgment.  This adapter maps an insight's issues into AI-derived ``Evidence``
(``code = REVIEW_<ISSUE>``, ``evidence_type = AI_DERIVED``) with the insight's
confidence and extraction provenance.  It never emits a ``Cause`` / ``Signal`` /
priority.
"""

import uuid

from app.commerce.contracts.evidence import EVIDENCE_AI_DERIVED, Evidence
from app.commerce.contracts.query import PROVENANCE_DERIVED, DataProvenance
from app.commerce.contracts.subject import (
    SUBJECT_LISTING,
    SUBJECT_STORE,
    SubjectRef,
)

EVIDENCE_CODE_PREFIX = "REVIEW_"


class ReviewInsightEvidenceAdapter:
    """Maps one ``ReviewInsight`` into one AI-derived Evidence per issue."""

    def to_evidence(self, insight, subject: SubjectRef) -> tuple[Evidence, ...]:
        return tuple(
            Evidence(
                evidence_id=uuid.uuid4().hex,
                subject=subject,
                evidence_type=EVIDENCE_AI_DERIVED,
                code=f"{EVIDENCE_CODE_PREFIX}{issue}",
                value=issue,
                confidence=insight.confidence,
                definition_version=insight.extractor_version,
                algorithm_version=insight.model_version,
                provenance=DataProvenance(
                    source_type=PROVENANCE_DERIVED,
                    adapter_id=insight.extractor_id,
                    adapter_version=insight.extractor_version,
                    canonical_schema_version=insight.prompt_version,
                ),
            )
            for issue in insight.issues
        )

    def to_evidence_for_listing(self, insight, listing_id) -> tuple[Evidence, ...]:
        return self.to_evidence(insight, SubjectRef(SUBJECT_LISTING, listing_id))

    def to_evidence_for_store(self, insight, store_id) -> tuple[Evidence, ...]:
        return self.to_evidence(insight, SubjectRef(SUBJECT_STORE, store_id))


__all__ = ["ReviewInsightEvidenceAdapter", "EVIDENCE_CODE_PREFIX"]
