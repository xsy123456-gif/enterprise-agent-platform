# Ground Truth Changelog

Ground truth is frozen per benchmark version.  Any correction must be recorded
here explicitly (scenario, old expectation, new expectation, reason, seed
evidence) — never silently modified.

## v1.0.0

Frozen (2026-08-15).  Initial ground truth for the 20 primary scenarios.
Ground truth checksum `fdcd23675eb451377e4361881c17ff0514dd541025e07b3db3c7af1f63106a58`.

## v1.0.1

Benchmark authoring completeness correction (NOT a change to match product output):

- **E2 specification completion**: diagnostic scenarios (B004-B014, B020) now
  carry explicit expected signal sets (existing frozen signal IDs only); normal
  controls / insufficient-data / governance scenarios remain E2 N/A.
- B011/B014 diagnostic semantics unchanged (primary/secondary causes preserved).

Ground truth checksum `62e1121b82b2e94cdf17b12e097545de9b600e5f83775ac2c190f145ea40c489`.
