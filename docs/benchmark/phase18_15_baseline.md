# Phase 18.15 Baseline — Enterprise Benchmark & Ground Truth Evaluation

Synthetic deterministic benchmark baseline.

> Results are measured on a deterministic synthetic benchmark.  They are **not**
> production accuracy, real-customer accuracy, or vendor certification.

## Metadata

| | |
|---|---|
| benchmark_suite_id | enterprise-commerce-benchmark-v1 |
| benchmark_version | 1.0.0 |
| dataset | enterprise-commerce-v1 (1.0.0) |
| dataset_checksum | `2dec1cd5…857d2a0` |
| ground_truth_checksum | `fdcd2367…1f63106a58` |
| clock | 2026-08-15 |
| scenarios | 20 |

## Scenario taxonomy

| category | scenarios |
|---|---|
| normal_control | B001, B002, B003 |
| single_factor | B004, B005, B006, B007, B008 |
| cross_channel | B009, B010 |
| multi_factor | B011, B012, B013, B014 |
| data_quality | B015, B016, B017 |
| governance | B018, B019 |
| multi_intent | B020 |

## Evaluation layers

```text
E1  Data / Ingestion correctness
E2  Metric & Signal correctness
E3  Diagnostic correctness
E4  Governance / Security correctness
E5  Agent Response correctness
```

## Result

```text
4 / 20 scenarios PASS
```

Passing: B001, B002, B003, B017.

Failing scenarios expose real product gaps (see below) — this is the benchmark
doing its job: it answers *whether the platform diagnoses correctly*, not
whether code runs.

## Benchmark-exposed product gaps

| Scenario(s) | Layer | Root cause |
|---|---|---|
| B004, B009–B014 | E3 | `TRAFFIC_DROP` signal is referenced by the sales rule but never detected by any plan, so `TRAFFIC_DECLINE` can never be asserted. |
| B005 | E3 | `store_health_scan` evaluates only the sales rule set; `CVR_DROP` has no sales-rule consequent. |
| B006, B008 | E3/E5 | Missing evidence raises a fact-query error that breaks the plan chain (HTTP 500) instead of flowing to `INSUFFICIENT_DATA`. |
| B007, B012, B020 | E3 | `advertising_health_scan` detects `ROAS_DROP` but not `CPC_RISE`, so `TRAFFIC_COST_INCREASE` is never asserted. |
| B015, B016 | E3 | Sparse / missing data is not surfaced as `INSUFFICIENT_DATA` (chain break). |
| B018, B019 | E4 | No multi-tenant message denial at the agent boundary (single-tenant agent). |

These are diagnostic/plumbing bugs, not ground-truth errors; ground truth was
authored from seed facts + frozen diagnostic semantics and is independent of the
production rule engine.

## Key metrics

```text
scenario pass rate        4/20
false positive rate       0/3 (normal controls all PASS)
false negative rate       12/14 (single/multi-factor scenarios FAIL)
unsupported cause count   0 (no fabricated causes — the failures are UNKNOWN/500, not wrong causes)
```

## Reproduction

```bash
python -m tools.benchmark.validate benchmark/enterprise-commerce-v1 \
    --seed data/seed/enterprise-commerce-v1

python -m tools.benchmark.run \
    --suite benchmark/enterprise-commerce-v1 \
    --seed data/seed/enterprise-commerce-v1
```

## Known limitations

- Deterministic synthetic benchmark; not production accuracy.
- Diagnostic correctness (E3) currently blocked by real signal-wiring and
  failure-handling gaps listed above.
- Ground truth is physically isolated; it never enters agent context.
