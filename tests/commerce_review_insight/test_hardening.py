"""Phase 11.7 Hardening cross-cutting checks."""

import pytest

from app.commerce.domain import Listing, Review, Store
from app.commerce.repositories.inmemory import InMemoryCommerceRepository
from app.commerce.review_insight import (
    EVAL_INCONSISTENT,
    EVAL_SCHEMA_INVALID,
    EVAL_VALID,
    CanonicalReviewAccess,
    CanonicalReviewInsightRepository,
    ExtractionError,
    ExtractionEvaluation,
    JOB_PARTIAL,
    JOB_SUCCEEDED,
    ReviewAvailableEvent,
    ReviewExtractionResult,
    ReviewInput,
    ReviewInsightJobManager,
    ReviewInsightProvenance,
    ReviewInsightService,
    ReviewInsightWorker,
)
from app.commerce.review_insight.extractor import (
    DeepSeekAdapter,
    RuleBasedExtractor,
)

TENANT = "company_A"
LISTING_ID = "listing_1"


def _seed(repository, review_ids=("rev1", "rev2")):
    repository.upsert_store(TENANT, Store(
        store_id="JP01", tenant_id=TENANT, platform="amazon", marketplace="JP",
        external_store_id="ext", name="JP01", currency="JPY", timezone="Asia/Tokyo",
    ))
    repository.upsert_listing(TENANT, Listing(
        listing_id=LISTING_ID, tenant_id=TENANT, store_id="JP01",
        platform="amazon", external_listing_id="B0",
    ))
    for review_id in review_ids:
        repository.upsert_review(TENANT, Review(
            review_id=review_id, tenant_id=TENANT, store_id="JP01",
            listing_id=LISTING_ID, platform="amazon",
            external_review_id=f"ext-{review_id}", rating=2.0,
            title="broken", content="battery issue",
        ))
    return repository


def _provenance():
    return ReviewInsightProvenance(
        extractor_id="review_extractor", extractor_version="1.0",
    )


def _worker(repository, extractor):
    manager = ReviewInsightJobManager()
    service = ReviewInsightService(
        CanonicalReviewInsightRepository(repository), _provenance(),
        CanonicalReviewAccess(repository), extractor,
    )
    return ReviewInsightWorker(service, manager)


@pytest.fixture
def repo():
    return _seed(InMemoryCommerceRepository())


# ── Quality: schema validation ──────────────────────────────

def test_evaluation_schema_valid():
    evaluation = ExtractionEvaluation()
    result = evaluation.evaluate(ReviewExtractionResult(
        review_id="rev1", sentiment="negative", issues=("BATTERY_FAILURE",),
        confidence=0.9,
    ))
    assert result.status == EVAL_VALID
    assert result.schema_valid is True


def test_evaluation_schema_invalid_confidence():
    evaluation = ExtractionEvaluation()
    result = evaluation.evaluate(ReviewExtractionResult(
        review_id="rev1", confidence=1.5,
    ))
    assert result.status == EVAL_SCHEMA_INVALID
    assert any("confidence" in issue for issue in result.schema_issues)


def test_evaluation_schema_invalid_review_id_and_types():
    evaluation = ExtractionEvaluation()
    result = evaluation.evaluate(ReviewExtractionResult(
        review_id="", sentiment=123, issues=("BATTERY_FAILURE",),
    ))
    assert result.status == EVAL_SCHEMA_INVALID
    assert any("review_id" in issue for issue in result.schema_issues)
    assert any("sentiment" in issue for issue in result.schema_issues)


# ── Quality: consistency validation ─────────────────────────

def test_evaluation_consistency_rating_contradiction():
    evaluation = ExtractionEvaluation()
    review = ReviewInput(review_id="rev1", content="good", rating=5.0)
    result = evaluation.evaluate(ReviewExtractionResult(
        review_id="rev1", sentiment="negative",
    ), review)
    assert result.status == EVAL_INCONSISTENT
    assert any("rating" in issue for issue in result.consistency_issues)


def test_evaluation_consistency_high_confidence_no_signal():
    evaluation = ExtractionEvaluation()
    review = ReviewInput(review_id="rev1", content="it is what it is", rating=3.0)
    result = evaluation.evaluate(ReviewExtractionResult(
        review_id="rev1", confidence=0.95,
    ), review)
    assert result.status == EVAL_INCONSISTENT
    assert any("confidence" in issue for issue in result.consistency_issues)


def test_evaluation_business_deferred():
    evaluation = ExtractionEvaluation()
    result = evaluation.evaluate(ReviewExtractionResult(review_id="rev1"))
    assert result.business_evaluation == "DEFERRED"
    for forbidden in ("cause", "impact", "priority", "recommendation"):
        assert forbidden not in result.to_dict()


# ── Quality: schema-invalid provider output -> typed failure ─

def test_schema_invalid_provider_output_is_typed_failure():
    adapter = DeepSeekAdapter()
    import json
    with pytest.raises(ExtractionError):
        adapter.map_response(
            {"choices": [{"message": {"content": json.dumps({"confidence": 1.5})}}]},
            "rev1",
        )
    evaluation = ExtractionEvaluation()
    result = evaluation.evaluate(ReviewExtractionResult(review_id="rev1", confidence=1.5))
    assert result.status == EVAL_SCHEMA_INVALID


# ── Idempotency: duplicate data.published -> no duplicate ───

def test_duplicate_event_no_duplicate_insight(repo):
    worker = _worker(repo, RuleBasedExtractor())
    event = ReviewAvailableEvent(event_id="e1", tenant_id=TENANT, review_ids=("rev1",))
    first = worker.handle(event)
    second = worker.handle(event)
    assert first.status == JOB_SUCCEEDED
    assert second.status == JOB_SUCCEEDED
    assert len(repo.list_review_insights_by_review(TENANT, "rev1")) == 1


# ── Version replay: deterministic fields ────────────────────

def test_version_replay_deterministic_fields(repo):
    worker = _worker(repo, RuleBasedExtractor())
    event = ReviewAvailableEvent(event_id="e1", tenant_id=TENANT, review_ids=("rev1",))
    worker.handle(event)
    insight = repo.list_review_insights_by_review(TENANT, "rev1")[0]
    # Re-run the same review + same extractor/prompt/knowledge versions.
    worker.handle(event)
    insights = repo.list_review_insights_by_review(TENANT, "rev1")
    assert len(insights) == 1
    assert insights[0].sentiment == insight.sentiment
    assert insights[0].issues == insight.issues
    assert insights[0].confidence == insight.confidence


# ── Security: job input cannot set tenant / principal / scope ─

def test_review_input_ignores_security_fields():
    review = ReviewInput.from_dict({
        "review_id": "rev1", "content": "x", "rating": 3.0,
        "tenant_id": "evil", "principal_id": "hacker",
        "scopes": ["business.store:ALL"], "permissions": ["admin"],
    })
    assert not hasattr(review, "tenant_id")
    assert not hasattr(review, "principal_id")
    assert not hasattr(review, "scopes")
    assert not hasattr(review, "permissions")
    assert review.to_dict() == {
        "review_id": "rev1", "title": "", "content": "x",
        "rating": 3.0, "language": "",
    }


def test_review_available_event_has_no_principal_scope_fields():
    event = ReviewAvailableEvent(event_id="e1", tenant_id=TENANT,
                                 review_ids=("rev1",))
    data = event.to_dict()
    for forbidden in ("principal_id", "scopes", "permissions", "principal"):
        assert forbidden not in data


def test_worker_uses_event_tenant_not_review_content(repo):
    worker = _worker(repo, RuleBasedExtractor())
    event = ReviewAvailableEvent(event_id="e1", tenant_id=TENANT, review_ids=("rev1",))
    job = worker.handle(event)
    # The job's tenant is the trusted event tenant; insights are persisted
    # under that tenant only.
    assert job.tenant_id == TENANT
    assert repo.get_review_insight(TENANT, repo.list_review_insights_by_review(
        TENANT, "rev1")[0].review_insight_id) is not None
    assert repo.list_review_insights_by_review("other_tenant", "rev1") == []
