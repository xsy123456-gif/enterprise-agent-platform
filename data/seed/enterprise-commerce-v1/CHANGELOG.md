# Seed Changelog

## 1.0.0

Frozen (2026-08-15).  Initial synthetic enterprise business world.
Dataset manifest checksum `2dec1cd5f40fce78ade13b316ade81d4b3a62f316aa5b7031eedd51a3857d2a0`.

## 1.0.1

Benchmark authoring completeness correction (patch, not a new business world):

- B011 diagnostic facts corrected so the conversion-deterioration signal
  satisfies the frozen `commerce.conversion.v1` ABNORMAL threshold (the
  diagnostic scenario facts live in the benchmark authoring, not the provider
  simulation data below).
- B014 diagnostic facts completed with the `UNITS` / `PERIOD_DAYS` base facts
  required by the frozen `DAYS_OF_SUPPLY` derived metric.

No entity model, schema, provider contract, or platform capability changed.
The provider simulation data under `providers/` is unchanged.
