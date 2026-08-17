# enterprise-commerce-benchmark-v1

Offline, deterministic correctness benchmark over the `enterprise-commerce-v1`
business world.

## Purpose

Evaluates *whether the platform diagnoses correctly*, across five layers:

```text
E1  Data / Ingestion correctness
E2  Metric & Signal correctness
E3  Diagnostic correctness
E4  Governance / Security correctness
E5  Agent Response correctness
```

## Dataset binding

The benchmark is bound to a specific seed manifest checksum.  If the seed
drifts, the runner fails before executing.

## Ground Truth isolation

Ground Truth lives in `ground_truth/` and is **physically isolated** from the
platform: `app/**` never imports this package, `simulation/**` never reads
ground truth, and the evaluator compares platform output to ground truth without
ever feeding the answers into an agent prompt or context.

Ground Truth is written from seed business facts + frozen diagnostic semantics —
it is never produced by running the production rule engine, and never saved back
from an agent result.

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

## Reproduction

```bash
python -m tools.benchmark.validate benchmark/enterprise-commerce-v1 \
    --seed data/seed/enterprise-commerce-v1

python -m tools.benchmark.run \
    --suite benchmark/enterprise-commerce-v1 \
    --seed data/seed/enterprise-commerce-v1

python -m tools.benchmark.run \
    --suite benchmark/enterprise-commerce-v1 \
    --seed data/seed/enterprise-commerce-v1 \
    --scenario B004 --verbose
```

## Limitations

Results are measured on a **deterministic synthetic benchmark**.  They are not
production accuracy, real-customer accuracy, or vendor certification.
