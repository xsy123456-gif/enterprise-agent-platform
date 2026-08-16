# Enterprise Agent Platform — Commerce Business Layer
## Phase 11 — ReviewInsight Intelligence Worker
## Implementation Design Specification v1.0

**Status:** Frozen Design / Implementation Baseline
**Baseline:** Phases 0–10 frozen (Runtime / Commerce Contract / Data Core / Metric /
Diagnostic Kernel / Plan Framework / Tool Surface / Ingestion / Business Plans /
Skill Framework)
**Module:** AI Commerce — ReviewInsight Intelligence Worker
**Runtime Mode v1:** READ / ANALYZE / DERIVE (no write-back, no auto action)

---

## 1. Goal Definition

The ReviewInsight Worker turns raw `Review` entities into stable, governed,
regenerable `ReviewInsight` AI-derived facts, so the existing Metric /
Diagnostic / Skill stack can consume structured review intelligence without any
LLM at diagnosis time.

- **Background:** `Review` is a raw business fact (Phase 1).  `ReviewInsight`
  is AI-derived evidence.  The two must stay strictly separated, and a change
  in extraction model must never rewrite raw Reviews.
- **Why a worker:** extraction is async, batchable, provider-mediated and
  failure-prone; it must be event-driven and idempotent rather than inline in
  the sync or diagnosis path.
- **Not an Agent:** the worker is deterministic, event-triggered infrastructure.
  It has no chat, no prompt router, no memory, no customer reply, no auto action.
- **Not the Diagnostic Kernel:** the worker produces *facts*; the Kernel
  (Rule/Metric/Impact/Priority) turns facts into signals / causes / impacts /
  priority.  The worker never computes causes, impacts or priority.

```
Review  -->  ReviewInsight Worker  -->  ReviewInsight  -->  Metric / Diagnostic / Skill
```

---

## 2. Architecture Position

`ReviewInsight` is:

- ✅ AI Derived Fact
- ❌ not Cause
- ❌ not Impact
- ❌ not Priority

It carries structured fields (sentiment / topics / issues / strengths / intent /
severity / confidence) plus full extraction provenance, and nothing else.

---

## 3. Final Architecture

```
                Commerce Sync
                     |
                     v
              Review Entity
                     |
                     |   commerce.review.available Event
                     v
                 EventBus
                     |
                     v
        ReviewInsight Worker
             +-------+-------+
             |               |
             v               v
    ReviewExtractor     Job Manager
             |               |
             v               |
       Provider Adapter      |
             |               |
             v               |
 Canonical ExtractionResult  |
             |               |
             v               |
      ReviewInsight Service   |
             |               |
             v               |
    ReviewInsight Repository  |
             |               |
      +------+------+        |
      |             |        |
      v             v        |
 review_insight.query  Evidence Adapter
                             |
                             v
                     Diagnostic Kernel
```

---

## 4. Domain Model Design

### ReviewInsight Entity

```python
ReviewInsight {
    insight_id,
    review_id,
    sentiment,
    topics[],
    issues[],
    strengths[],
    intent,
    severity,
    confidence,
    extractor_id,
    extractor_version,
    model_provider,
    model_version,
    prompt_version,
    knowledge_policy_version,
    knowledge_context_version,
    generated_at
}
```

Explicitly deleted (must never appear):

```
❌ cause
❌ impact
❌ priority
❌ recommendation
❌ action
```

> **Frozen-state note:** Phase 1 already defines a `ReviewInsight` canonical
> entity (`app/commerce/domain/review/__init__.py`) with
> `review_insight_id / review_id / sentiment / topics / issues / strengths /
> intent / severity / confidence / model_provider / model_version /
> extractor_version / generated_at / supersedes_id`.  Phase 11 *extends* this
> entity (additive fields `extractor_id / prompt_version /
> knowledge_policy_version / knowledge_context_version`) rather than creating a
> second, conflicting entity.  `review_insight_id` remains the canonical id
> (the `insight_id` in this spec is its logical name).

---

## 5. Extraction Contract

New port `ReviewExtractorPort`:

```python
extract_batch(reviews, context=None) -> ReviewExtractionBatchResult
```

Input:

```python
ReviewInput {
    review_id,
    title,
    content,
    rating,
    language
}
```

Output:

```python
ReviewExtractionResult {
    review_id,
    sentiment,
    topics,
    issues,
    strengths,
    intent,
    severity,
    confidence
}
```

---

## 6. Provider Isolation Design

Supported providers: DeepSeek / OpenAI / Claude / Local Model / Rule Based.

```
Provider  -->  Adapter  -->  ReviewExtractorPort  -->  Canonical Result
```

Forbidden: a Provider must never return a `ReviewInsight` directly — it returns
only the canonical `ReviewExtractionResult`; provenance (extractor/model/prompt
versions) is stamped by the Service, never by the Provider.

---

## 7. Worker Runtime Design

Event-driven.  Listens to `commerce.review.available`:

```json
{
  "event_id": "...",
  "tenant_id": "company_A",
  "resource": "REVIEW",
  "review_ids": ["rev1", "rev2"],
  "sync_run_id": "...",
  "published_at": "..."
}
```

Forbidden: the event must never carry review content.

> **Frozen-state note:** Phase 7 already publishes `commerce.data.published`
> (with `resource`) after each atomic publish.  The worker consumes that event
> from the platform EventBus and filters `resource == "review"`; the
> `commerce.review.available` contract is realized as a thin relay/alias in the
> worker module — Phase 7 core is not modified.

---

## 8. Job Lifecycle

New `ReviewInsightJob`:

```
CREATED / RUNNING / PARTIAL / SUCCEEDED / FAILED / CANCELLED
```

```python
{
  job_id,
  tenant_id,
  event_id,
  review_ids,
  extractor_id,
  extractor_version,
  status,
  total_count,
  success_count,
  failed_count,
  retry_count,
  trace_id
}
```

---

## 9. Retry / Failure Model

- A single review failure out of 100 → `PARTIAL` (99 success, 1 failed).
- Provider-wide failure → `FAILED`.
- Forbidden: `except: pass` — every failure is recorded and surfaced.

---

## 10. Idempotency Design

Unique key:

```
tenant_id + review_id + extractor_id + extractor_version
```

Guarantee: duplicate event consumption never produces a duplicate Insight.

---

## 11. Repository Design

New module `app/commerce/review_insight/`:

```
review_insight/
  domain/          # ReviewInput, ReviewExtractionResult, job models
  repository/      # ReviewInsightRepositoryPort + impl
  worker/          # event consumer, job manager
  extractor/       # ReviewExtractorPort + providers
  service/         # ReviewInsightService (orchestrates extract -> stamp -> save)
```

Port:

```python
ReviewInsightRepositoryPort {
  save(insight)
  save_batch(insights)
  get(tenant_id, insight_id)
  list_by_review(tenant_id, review_id)
  list_by_listing(tenant_id, listing_id)
  exists(tenant_id, review_id, extractor_id, extractor_version)
}
```

> **Frozen-state note:** Phase 2 already persists `commerce_review_insights`
> through `CommerceRepository.upsert_review_insight` /
> `list_review_insights_by_review`.  `ReviewInsightRepositoryPort` is a thin
> worker-facing port that delegates to the canonical repository and adds the
> idempotency natural key + `exists()`.

---

## 12. Database Design

Table: `commerce_review_insights` (extends the existing Phase 2 table).

Core columns:

```
id
tenant_id
review_id
sentiment
topics jsonb
issues jsonb
strengths jsonb
confidence
severity
extractor_id
extractor_version
model_version
prompt_version
generated_at
```

Unique index:

```
tenant_id, review_id, extractor_id, extractor_version
```

---

## 13. Tool Ecosystem Integration

- New Capability: `commerce.review_insight.read`
- New Tool: `review_insight.query`

Chain:

```
Skill --> Plan FACT_QUERY --> Capability --> Tool --> Repository
```

Tool returns: `issues / topics / confidence / severity`.
Tool never returns: Cause / Impact / Priority.

---

## 14. Metric Integration

Principle: ReviewInsight does **not** compute metrics.

New `MetricSourceAdapter` (deferred to a later phase) will map ReviewInsight ->
metric source, enabling future metrics:

```
NEGATIVE_REVIEW_RATE
ISSUE_FREQUENCY
TOP_NEGATIVE_TOPIC
ISSUE_TREND
```

---

## 15. Diagnostic Integration

New `ReviewInsightEvidenceAdapter` converts:

```
ReviewInsight  -->  Evidence  -->  RuleEngine
```

Example:

```
Insight: issue = BATTERY_FAILURE, confidence = 0.91
Evidence: code = REVIEW_BATTERY_FAILURE, confidence = 0.91, source = REVIEW_INSIGHT
```

---

## 16. Knowledge Boundary

- v1 default: Knowledge **OFF**.
- Enabled per Listing Policy via a new `ReviewKnowledgePolicy` (not a per-review
  dynamic decision).
- `KnowledgeContext { product_specs, warranty_policy, relevant_faq, provenance }`
  is input to the Extractor only — it never enters `ReviewInsight`.

---

## 17. Quality Governance

New `ExtractionEvaluation` with v1 two layers (business evaluation deferred):

1. **Schema Validation** — fields, types, ranges.
2. **Consistency Validation** — text vs result consistency.
3. **Business Evaluation** — deferred.

---

## 18. Version Governance

`ReviewInsight` records: `extractor_version`, `model_version`, `prompt_version`,
`knowledge_version`.

Replay depends on: `Review + Extractor Version + Prompt Version +
Knowledge Context Version`.

---

## 19. Security Boundary

The Worker consumes the Runtime `TrustedExecutionContext`; it never creates
`tenant / principal / permission / scope`.

---

## 20. Testing Strategy

- **Domain:** model validation, serialization.
- **Extractor:** provider mapping, invalid output.
- **Worker:** event consume, batch execution.
- **Idempotency:** duplicate event.
- **Version:** replay.
- **Failure:** partial, failed.
- **Tool:** permission, provenance.

---

## 21. Implementation Order

```
11.1 Domain + Contract
11.2 Repository
11.3 Worker Runtime
11.4 Extractor Provider
11.5 Tool Integration
11.6 Diagnostic Integration
11.7 Hardening
```

---

## 22. Acceptance Gate

```
ReviewInsight Entity    PASS
Extractor Contract      PASS
Worker Event            PASS
Repository              PASS
Idempotency             PASS
Version Governance      PASS
Tool Capability         PASS
Diagnostic Adapter      PASS
Quality Evaluation      PASS
Regression              PASS
```

---

## Explicitly Excluded from Phase 11

```
❌ Agent
❌ Chat
❌ Prompt Router
❌ Memory
❌ Customer Reply
❌ Auto Action
❌ Product Modification
❌ Dynamic RAG Decision
```

---

## Execution Target

Implement the ReviewInsight Intelligence Worker without modifying the frozen
Phase 0–10 Platform Kernel, so Review data is stably, safely and governance-bound
transformed into AI Derived Facts, consumable by the existing Metric /
Diagnostic / Skill stack.
