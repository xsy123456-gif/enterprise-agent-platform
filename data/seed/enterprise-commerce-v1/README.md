# enterprise-commerce-v1

Synthetic enterprise commerce business world for simulation-driven validation.

**Synthetic only.** All persons, companies, emails, addresses, reviews and CRM
records are fabricated.  No real customer data.

## Purpose

This dataset populates the Phase 18.13 simulation services (Amazon / TikTok /
SAP / Salesforce / NetSuite) with a coherent, multi-tenant business world so
that connectors, adapters and the canonical domain are exercised against a
realistic, cross-system dataset — not unit fixtures.  The platform reaches this
data only over the external HTTP boundary; it never reads these files directly.

## Key facts

| | |
|---|---|
| dataset_id | `enterprise-commerce-v1` |
| dataset_version | `1.0.0` |
| anchor_date | 2026-08-15 |
| history_days | 90 (2026-05-18 .. 2026-08-15) |
| random_seed | 18014 |
| tenants | 2 (Aurora Commerce, Northstar Retail) |
| stores | 4 (Amazon JP, TikTok US, Amazon US, TikTok UK) |
| providers | Amazon, TikTok, SAP, Salesforce, NetSuite |

## Entity scale (approximate)

- 16 products, 23 SKUs, 37 listings
- ~2,100 orders, ~3,300 inventory snapshots, ~270 reviews
- 16 ad campaigns, ~4,500 metric rows
- SAP materials/inventory/POs, NetSuite items/orders/fulfillments, Salesforce
  accounts/contacts/opportunities/cases

## Business conditions

The data includes (as business *facts*, with no labels or expected answers):

- normal stable operation (control entities)
- traffic-decline windows
- conversion-deterioration windows
- inventory depletion / stockout windows
- advertising-efficiency deterioration
- review-rating deterioration windows
- promotion uplift windows
- sparse / new-listing history
- multi-factor periods and cross-channel divergence

**There is no benchmark ground truth in this dataset.**  No `expected_cause`,
`expected_diagnosis`, `golden_answer` or `benchmark_score` fields exist.

## Layout

```text
world/       business-world definitions (tenants, stores, products, skus,
             identity map, business events)
providers/   provider-native projections (Amazon/TikTok/SAP/Salesforce/NetSuite)
manifest.json  dataset metadata + per-file SHA-256 checksums
```

## Generation

```bash
python -m tools.seed.generate data/seed/enterprise-commerce-v1
```

The generator is deterministic (fixed seed + anchor date); re-running produces
identical counts, IDs and checksums.

## Validation

```bash
python -m tools.seed.validate data/seed/enterprise-commerce-v1
```

Verifies checksums, referential integrity, metric/inventory consistency,
cross-provider identity mapping, duplicate IDs, and the absence of ground-truth
or secret material.

## Launching the simulation with this dataset

```bash
python -m simulation.launcher --seed data/seed/enterprise-commerce-v1
```
