# Phase 18.15 Post-Remediation Baseline

Synthetic deterministic benchmark.  Results are measured on a deterministic
synthetic benchmark — **not** production accuracy, real-customer accuracy, or
vendor certification.

## Progression

```text
Initial benchmark (18.15):        4/20
First remediation (18.15.6):     11/20
Capability completion (18.15.7): 18/20
```

## Frozen identity (unchanged across all remediation)

```text
dataset_checksum      2dec1cd5f40fce78ade13b316ade81d4b3a62f316aa5b7031eedd51a3857d2a0
ground_truth_checksum fdcd23675eb451377e4361881c17ff0514dd541025e07b3db3c7af1f63106a58
```

## Scenario matrix

| ID | E1 | E2 | E3 | E4 | E5 | Overall |
|---|---|---|---|---|---|---|
| B001 | PASS | N/A | PASS | PASS | PASS | PASS |
| B002 | PASS | N/A | PASS | PASS | PASS | PASS |
| B003 | PASS | N/A | PASS | PASS | PASS | PASS |
| B004 | PASS | N/A | PASS | PASS | PASS | PASS |
| B005 | PASS | N/A | PASS | PASS | PASS | PASS |
| B006 | PASS | N/A | PASS | PASS | PASS | PASS |
| B007 | PASS | N/A | PASS | PASS | PASS | PASS |
| B008 | PASS | N/A | PASS | PASS | PASS | PASS |
| B009 | PASS | N/A | PASS | PASS | PASS | PASS |
| B010 | PASS | N/A | PASS | PASS | PASS | PASS |
| B011 | PASS | N/A | FAIL | PASS | PASS | FAIL |
| B012 | PASS | N/A | PASS | PASS | PASS | PASS |
| B013 | PASS | N/A | PASS | PASS | PASS | PASS |
| B014 | PASS | N/A | FAIL | PASS | PASS | FAIL |
| B015 | PASS | N/A | PASS | PASS | PASS | PASS |
| B016 | PASS | N/A | PASS | PASS | PASS | PASS |
| B017 | PASS | N/A | PASS | PASS | PASS | PASS |
| B018 | N/A | N/A | N/A | PASS | PASS | PASS |
| B019 | N/A | N/A | N/A | PASS | PASS | PASS |
| B020 | PASS | N/A | PASS | PASS | PASS | PASS |

## Remaining failures (frozen GT / seed authoring, not product bugs)

- **B011**: GT expects `PRICE_INCREASE` secondary, but the frozen seed's
  conversion drop is ~10% (WARNING), below the frozen `commerce.conversion.v1`
  ABNORMAL threshold (20%).
- **B014**: GT expects `STOCKOUT_RISK` secondary, but the frozen seed omits
  UNITS/PERIOD_DAYS so `DAYS_OF_SUPPLY` cannot be computed.
- **E2**: frozen GT has empty E2 signal specs; making it PASS/FAIL would require
  editing frozen ground truth.

## Key metrics

```text
scenario pass rate         18/20
primary cause accuracy     18/18 (scenarios with primary GT)
false positive rate        0/3 (normal controls)
false negative rate        2/14 (B011, B014 — frozen GT/seed)
unsupported cause count    0
insufficient data accuracy 2/2 (B015, B016)
permission breach count    0
cross-tenant leak count    0
unauthorized execution     0
```

## Reproduction

```bash
python -m tools.benchmark.run --suite benchmark/enterprise-commerce-v1 \
    --seed data/seed/enterprise-commerce-v1
```
