# Phase 11 — ReviewInsight Intelligence Worker
## Implementation Plan (sub-phase breakdown)

This plan decomposes the frozen design (`docs/review-insight-worker.md`) into
seven sub-phases, each with concrete files, interfaces, tests and an acceptance
gate.  **Constraint:** no modification to the frozen Phase 0–10 Platform Kernel.
All new code lives under `app/commerce/review_insight/` plus additive,
backward-compatible extensions to Phase 1/2 contracts (version-bumped).

### Frozen reuse map

| Need | Existing frozen capability |
|---|---|
| Review entity | `app/commerce/domain/review.py::Review` |
| ReviewInsight entity | `app/commerce/domain/review.py::ReviewInsight` (extend, don't replace) |
| Canonical review-insight store | `CommerceRepository.upsert_review_insight` / `list_review_insights_by_review` (Phase 2) |
| Postgres table | `commerce_review_insights` (Phase 2 schema) |
| Event bus | `app.events.bus.EventBus` + `app.events.models.Event` |
| Publish event | `commerce.data.published` (Phase 7 `SyncEvents`) |
| Trusted context | `app.commerce.diagnostics.plans.ports.TrustedExecutionContext` |
| Evidence contract | `app.commerce.contracts.evidence.Evidence` |
| Tool surface | `app.commerce.platform` (COMMERCE_CAPABILITIES / CAPABILITY_TOOL / build_commerce_tools) |
| Query service | `app.commerce.query.service.CommerceQueryService` (has `list_review_insights_by_review`) |

---

## 11.1 Domain + Contract

**Files**
- `app/commerce/review_insight/__init__.py`
- `app/commerce/review_insight/errors.py` — `ReviewInsightError`,
  `ExtractionError`, `ExtractorUnavailableError`, `JobNotFoundError`
- `app/commerce/review_insight/domain.py`
  - `ReviewInput` (review_id, title, content, rating, language)
  - `ReviewExtractionResult` (review_id, sentiment, topics, issues, strengths,
    intent, severity, confidence)
  - `ReviewExtractionBatchResult` (results, failed_review_ids, provider_meta)
  - `ReviewInsightJob` (job_id, tenant_id, event_id, review_ids, extractor_id,
    extractor_version, status, total/success/failed_count, retry_count, trace_id)
  - `ReviewAvailableEvent` (event_id, tenant_id, resource, review_ids,
    sync_run_id, published_at)
- `app/commerce/review_insight/contracts.py` — `ReviewExtractorPort`
  (`extract_batch(reviews, context=None) -> ReviewExtractionBatchResult`)

**Contract change (version-bumped):** extend `app.commerce.domain.review.ReviewInsight`
with `extractor_id`, `prompt_version`, `knowledge_policy_version`,
`knowledge_context_version` (all defaulted).  `review_insight_id` stays the
canonical id; `insight_id` is the logical alias in the worker layer.

**Tests:** `tests/commerce_review_insight/test_domain.py`
- model validation (ReviewInsight never carries cause/impact/priority/recommendation/action)
- ReviewInput / ReviewExtractionResult / batch serialization round-trip
- ReviewInsight serialization round-trip with new governance fields

**Gate:** Domain + Contract Freeze.

---

## 11.2 Repository

**Files**
- `app/commerce/review_insight/repository.py`
  - `ReviewInsightRepositoryPort` (ABC): `save`, `save_batch`, `get`,
    `list_by_review`, `list_by_listing`, `exists`
  - `CanonicalReviewInsightRepository` — delegates to `CommerceRepository`
    (`upsert_review_insight`, `list_review_insights_by_review`,
    `list_reviews_by_listing`), and implements `exists` via the natural key.
- Extend Postgres schema `commerce_review_insights` (idempotent `ALTER ... ADD
  COLUMN IF NOT EXISTS`) with `extractor_id`, `prompt_version`,
  `knowledge_policy_version`, `knowledge_context_version`, and a unique index
  `(tenant_id, review_id, extractor_id, extractor_version)`.
- Extend in-memory repository `InMemoryCommerceRepository.upsert_review_insight`
  to honor the same natural key (idempotent).

**Natural key:** `tenant_id + review_id + extractor_id + extractor_version`.

**Tests:** `tests/commerce_review_insight/test_repository.py`
- save / get / list_by_review / list_by_listing / exists
- idempotent save (duplicate natural key -> no duplicate row)
- Postgres integration (gated by `COMMERCE_TEST_DATABASE_URL`)

**Gate:** Repository Freeze.

---

## 11.3 Worker Runtime

**Files**
- `app/commerce/review_insight/worker.py`
  - `ReviewInsightWorker` — subscribes to `commerce.data.published`
    (`resource == "review"`), enqueues a `ReviewInsightJob`, drives the Service.
- `app/commerce/review_insight/job.py`
  - `ReviewInsightJobManager` — job lifecycle (CREATED → RUNNING → PARTIAL /
    SUCCEEDED / FAILED / CANCELLED), retry counters.
- `app/commerce/review_insight/service.py`
  - `ReviewInsightService` — fetch Reviews (via a `ReviewAccessPort`), call the
    Extractor, stamp provenance, call the Repository; enforce "provider-wide
    failure → FAILED; partial single-review failure → PARTIAL".

**Event contract:** the worker consumes `commerce.data.published` where
`resource == "review"` and treats it as `commerce.review.available`; the event
payload never contains review content.

**Tests:** `tests/commerce_review_insight/test_worker.py`
- event consume -> job created -> insights saved
- batch execution (N reviews -> N insights)
- partial (one review fails -> PARTIAL, others saved)
- provider-wide failure -> FAILED, nothing saved
- no `except: pass` (every failure recorded in job.failed_count)

**Gate:** Worker Runtime Freeze.

---

## 11.4 Extractor Provider

**Files**
- `app/commerce/review_insight/extractor/__init__.py`
- `app/commerce/review_insight/extractor/rule_based.py`
  - `RuleBasedExtractor` — deterministic v1 baseline (keyword/rating heuristics)
    so the worker is testable with no external provider.
- `app/commerce/review_insight/extractor/providers.py`
  - `ProviderAdapter` protocol; `DeepSeekAdapter` / `OpenAIAdapter` /
    `ClaudeAdapter` stubs that map provider output -> canonical
    `ReviewExtractionResult`.
- `app/commerce/review_insight/extractor/factory.py`
  - `build_extractor(provider_config)` returning a `ReviewExtractorPort`.

**Constraint:** a Provider never returns a `ReviewInsight`; the Service stamps
provenance.

**Tests:** `tests/commerce_review_insight/test_extractor.py`
- rule-based mapping determinism
- invalid provider output -> typed `ExtractionError` (never swallowed)
- provider mapping never fabricates `cause/impact/priority`

**Gate:** Extractor Provider Freeze.

---

## 11.5 Tool Integration

**Files**
- `app/commerce/tools/__init__.py` — add `ReviewInsightQueryTool`
  (`review_insight.query`, capability `commerce.review_insight.read`,
  STRICT scope, include_raw irrelevant since insights carry no raw content).
- `app/commerce/platform/__init__.py` — add capability + binding +
  `CAPABILITY_TOOL["commerce.review_insight.read"] = "review_insight.query"`.

**Tool contract:** returns structured insight fields (issues/topics/confidence/
severity + provenance); never Cause/Impact/Priority.

**Tests:** `tests/commerce_review_insight/test_tool.py`
- allowed query returns insights with extractor/model/prompt version provenance
- STRICT scope denial (out-of-scope store) before any canonical query
- zero-invocation assertion on denial

**Gate:** Tool Capability Freeze.

---

## 11.6 Diagnostic Integration

**Files**
- `app/commerce/review_insight/evidence_adapter.py`
  - `ReviewInsightEvidenceAdapter` — `ReviewInsight -> Evidence`
    (`code = "REVIEW_<ISSUE>", confidence, source = REVIEW_INSIGHT`,
    `evidence_type = AI_DERIVED`, subject = listing/store).
- `app/commerce/review_insight/metric_source_adapter.py`
  - `MetricSourceAdapter` skeleton (deferred; no metric computation in Phase 11).

**Tests:** `tests/commerce_review_insight/test_diagnostic_integration.py`
- adapter maps an insight to an `Evidence` with the right code/confidence/source
- a RuleEngine RuleSet can consume the produced Evidence (e.g.
  `REVIEW_BATTERY_FAILURE` -> cause) — proving the Diagnostic Kernel boundary.

**Gate:** Diagnostic Adapter Freeze.

---

## 11.7 Hardening

**Files**
- `app/commerce/review_insight/evaluation.py`
  - `ExtractionEvaluation` — schema validation (fields/types/ranges) +
    consistency validation (text vs result).  Business evaluation deferred.

**Cross-cutting checks (tests):**
- Idempotency: duplicate `commerce.data.published` -> no duplicate insight.
- Version replay: same review + extractor/prompt/knowledge version ->
  deterministic insight fields.
- Security: worker only consumes the Runtime `TrustedExecutionContext`; a job
  input cannot set tenant/principal/scope.
- Quality: schema-invalid provider output -> quarantined/typed failure.
- Full regression: Phase 0–10 + Phase 11 green; Commerce PostgreSQL integration
  green.

**Gate:** ReviewInsight Worker Hardening Freeze.

---

## Acceptance Gate (final)

Run and verify all of §22 of the design doc; record the commit.  Deliverables:

1. `app/commerce/review_insight/` (domain, contracts, repository, worker,
   extractor, service, evidence/metric adapters, evaluation)
2. additive Phase 1/2 contract extension (ReviewInsight governance fields +
   `commerce_review_insights` natural key)
3. `commerce.review_insight.read` capability + `review_insight.query` tool
4. `tests/commerce_review_insight/` covering all §20 testing layers
5. full regression + Postgres integration

**Commit convention (per sub-phase):**
```
feat(review-insight-domain): ...
feat(review-insight-repository): ...
feat(review-insight-worker): ...
feat(review-insight-extractor): ...
feat(review-insight-tool): ...
feat(review-insight-diagnostic): ...
fix(review-insight): harden
```
