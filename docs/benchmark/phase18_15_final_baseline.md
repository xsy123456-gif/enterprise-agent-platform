# Phase 18.15 Final Baseline (Benchmark v1.0.1)

Synthetic deterministic benchmark.  Results are measured on a deterministic
synthetic benchmark — **not** production accuracy, real-customer accuracy, or
vendor certification.

## Version

```text
Seed:     enterprise-commerce-v1 1.0.1
Benchmark: enterprise-commerce-benchmark-v1 1.0.1
```

## Checksums

```text
dataset 1.0.0 checksum       2dec1cd5f40fce78ade13b316ade81d4b3a62f316aa5b7031eedd51a3857d2a0
dataset 1.0.1 checksum       2dec1cd5f40fce78ade13b316ade81d4b3a62f316aa5b7031eedd51a3857d2a0 (provider data unchanged)
ground truth 1.0.0 checksum  fdcd23675eb451377e4361881c17ff0514dd541025e07b3db3c7af1f63106a58
ground truth 1.0.1 checksum  62e1121b82b2e94cdf17b12e097545de9b600e5f83775ac2c190f145ea40c489
```

Note: the B011/B014 diagnostic facts live in the benchmark scenario authoring
(`setup.metrics`), not the provider simulation data under `data/seed/providers/`
— so the provider dataset checksum is unchanged by the 1.0.1 authoring patch.

## Why 1.0.1 (authoring correction, not a product change)

- **B011**: the scenario's conversion-deterioration facts did not satisfy the
  frozen `commerce.conversion.v1` ABNORMAL threshold (20%); corrected the facts
  (orders 18→12) so the intended secondary cause is supported.
- **B014**: the scenario lacked `UNITS`/`PERIOD_DAYS`, the base facts required by
  the frozen `DAYS_OF_SUPPLY` derived metric; added them.
- **E2**: the ground truth carried empty E2 signal specs; populated explicit
  expected signal sets for the diagnostic scenarios (existing frozen signal IDs).

## Progression (preserved history)

```text
Initial benchmark v1.0.0:       4/20
After bug remediation (18.15.6): 11/20
After capability completion (18.15.7): 18/20
Authoring-corrected v1.0.1:      20/20
```

## Scenario matrix

| ID | E1 | E2 | E3 | E4 | E5 | Overall |
|---|---|---|---|---|---|---|
| B001 | PASS | N/A | PASS | PASS | PASS | PASS |
| B002 | PASS | N/A | PASS | PASS | PASS | PASS |
| B003 | PASS | N/A | PASS | PASS | PASS | PASS |
| B004 | PASS | PASS | PASS | PASS | PASS | PASS |
| B005 | PASS | PASS | PASS | PASS | PASS | PASS |
| B006 | PASS | PASS | PASS | PASS | PASS | PASS |
| B007 | PASS | PASS | PASS | PASS | PASS | PASS |
| B008 | PASS | PASS | PASS | PASS | PASS | PASS |
| B009 | PASS | PASS | PASS | PASS | PASS | PASS |
| B010 | PASS | PASS | PASS | PASS | PASS | PASS |
| B011 | PASS | PASS | PASS | PASS | PASS | PASS |
| B012 | PASS | PASS | PASS | PASS | PASS | PASS |
| B013 | PASS | PASS | PASS | PASS | PASS | PASS |
| B014 | PASS | PASS | PASS | PASS | PASS | PASS |
| B015 | PASS | N/A | PASS | PASS | PASS | PASS |
| B016 | PASS | N/A | PASS | PASS | PASS | PASS |
| B017 | PASS | N/A | PASS | PASS | PASS | PASS |
| B018 | N/A | N/A | N/A | PASS | PASS | PASS |
| B019 | N/A | N/A | N/A | PASS | PASS | PASS |
| B020 | PASS | PASS | PASS | PASS | PASS | PASS |

## Key metrics

```text
Scenario Pass Rate           20/20
E1 applicable Pass Rate      100%
E2 applicable Pass Rate      100% (12 diagnostic scenarios)
E3 applicable Pass Rate      100%
E4 applicable Pass Rate      100%
E5 applicable Pass Rate      100%
Primary Cause Accuracy       100%
Secondary Cause Recall       100% (B011-B014)
Unsupported Cause Count      0
False Positive Rate          0%
False Negative Rate          0%
Insufficient Data Accuracy   2/2 (B015, B016)
Cross-Channel Routing        2/2 (B009, B010)
Permission Breach Count      0
Cross-Tenant Leak Count      0
Unauthorized Provider Request 0
Unauthorized Execution Count 0
Unsupported Claim Count      0
```

## Reproduction

```bash
python -m tools.benchmark.validate benchmark/enterprise-commerce-v1 \
    --seed data/seed/enterprise-commerce-v1

python -m tools.benchmark.run \
    --suite benchmark/enterprise-commerce-v1 \
    --seed data/seed/enterprise-commerce-v1
```
