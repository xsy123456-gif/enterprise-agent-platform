# Phase 18.15.6 Remediation Log

Benchmark-driven correctness remediation against the **unchanged** seed, ground
truth, scenario and evaluator set.

## Frozen benchmark identity (unchanged)

```text
dataset_checksum      2dec1cd5f40fce78ade13b316ade81d4b3a62f316aa5b7031eedd51a3857d2a0
ground_truth_checksum fdcd23675eb451377e4361881c17ff0514dd541025e07b3db3c7af1f63106a58
```

## Result

```text
Before remediation: 4/20
After remediation:  11/20
```

## Root cause matrix

| ID | Symptom | Root cause | Classification | Fixed |
|---|---|---|---|---|
| R1 | E1 subject empty | Reclassified: the empty subject was a downstream symptom of R3 (500), not a resolution failure | — (was R3) | via R3 |
| R2 | `TRAFFIC_DROP`/`CPC_RISE` never asserted | Plans queried the metrics but never wired an anomaly step for the existing signal codes | Bug | YES |
| R3 | missing evidence -> HTTP 500 | Plan executor stopped the chain on a skipped step, so RESULT_ASSEMBLE never ran | Bug | YES |
| R4 | E2 NOT_APPLICABLE | Diagnostic signal *status* not observable through the product response | Gap | NO |
| R5 | cross-tenant query not denied | single-tenant agent; no message-level tenant ownership check | Gap | NO |
| R6 | B020 multi-intent | B020 is an advertising-diagnosis scenario; it now passes via R2 (not a new router) | n/a | via R2 |

## Fixes

### R3 — missing evidence returns typed uncertainty (not 500)

- `app/commerce/diagnostics/plans/executor.py`: on `FAILURE_SKIP` /
  `FAILURE_MARK_UNKNOWN`, still activate successors so the terminal
  `RESULT_ASSEMBLE` step always runs and emits `INSUFFICIENT_DATA`.
- `app/commerce/diagnostics/plans/handlers.py`: default `Priority()` when the
  priority step was skipped.

Effect: B015/B016 return `INSUFFICIENT_DATA` (was 500).

### R2 — wire existing signals into active plans

- `store_health_scan` / `gmv_decline_diagnosis`: added SESSIONS -> `TRAFFIC_DROP`
  anomaly step (existing metric + existing signal + existing rule).
- `advertising_health_scan`: added CPC compute + `CPC_RISE` anomaly step.

Effect: B004/B009/B010 (traffic), B007/B020 (advertising) now produce the
correct primary cause.

## Remaining gaps (not fixed — require capability decisions, not bugs)

- B005: conversion diagnosis needs plan-level routing to
  `conversion_decline_diagnosis` (the scan plan is frozen as signals-only).
- B006/B008: production `inventory.query` / `review.query` tools do not serve the
  store-level aggregate facts (`AVAILABLE_INVENTORY`, `REVIEW_RATING`,
  `NEGATIVE_REVIEW_RATE`) that the plans (and frozen unit tests) expect.
- B011-B014: cross-domain secondary causes require multi-rule-set evaluation
  beyond the single-domain scan plans.
- B018/B019: no message-level multi-tenant resource ownership check.

No new signal, cause, rule, capability or benchmark special-case was added.

## Phase 18.15.7 — Frozen Capability Completion

```text
Before (18.15):      4/20
After (18.15.6):    11/20
After (18.15.7):    18/20
```

### Fixes

- R5 (governance): tenant-aware entity resolution + `ResourceOwnershipError`
  (deny before execution, 404). B018/B019 PASS.
- R2 (query facts): AVAILABLE_INVENTORY / REVIEW_RATING / NEGATIVE_REVIEW_RATE
  served as leaf metrics via `metric.query`. B006/B008 PASS.
- Plan selection + cross-domain composition: `SkillSystem.diagnose` maps
  ABNORMAL/CRITICAL signals to existing domain plans and merges causes.
  B005/B012/B013 PASS.

### Remaining (not fixed — frozen GT / seed authoring, not product bugs)

- B011: GT expects `PRICE_INCREASE` secondary, but the frozen seed's conversion
  drop is ~10% (WARNING), below the frozen `commerce.conversion.v1` ABNORMAL
  threshold (20%).  Would require changing frozen thresholds/seed/GT.
- B014: GT expects `STOCKOUT_RISK` secondary, but the frozen seed omits
  UNITS/PERIOD_DAYS, so `DAYS_OF_SUPPLY` cannot be computed.  Would require
  changing frozen seed/GT.
- E2: frozen GT has empty E2 signal specs (`{"signals": {}}`), so E2 evaluates
  as NOT_APPLICABLE; making it PASS/FAIL would require editing frozen GT.
