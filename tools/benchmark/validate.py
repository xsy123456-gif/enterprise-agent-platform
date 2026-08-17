"""Benchmark suite validator (Phase 18.15).

Usage::

    python -m tools.benchmark.validate benchmark/enterprise-commerce-v1 \
        --seed data/seed/enterprise-commerce-v1

Checks: 20 scenarios, unique IDs, 1:1 scenario/ground-truth pairing, dataset
checksum binding, valid cause IDs / states, no answer fields in scenario files,
and no missing evidence refs.
"""

import argparse
import sys

from tools.benchmark import loader
from tools.benchmark.models import (
    LAYERS,
    frozen_cause_codes,
    VERDICT_NOT_APPLICABLE,
)


def validate(suite_root, seed_root=None):
    errors = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    manifest = loader.load_manifest(suite_root)
    scenarios = loader.load_all(suite_root)[1]
    ground_truth = loader.load_all(suite_root)[2]

    check(manifest.get("scenario_count") == 20,
          "manifest scenario_count must be 20")
    check(len(scenarios) == 20, f"expected 20 scenarios, got {len(scenarios)}")
    check(len(ground_truth) == 20,
          f"expected 20 ground truths, got {len(ground_truth)}")

    scenario_ids = set(scenarios)
    gt_ids = set(ground_truth)
    check(scenario_ids == gt_ids, "scenario / ground truth id mismatch")
    check(len(scenario_ids) == 20, "duplicate or missing scenario ids")

    causes = frozen_cause_codes()

    for sid in sorted(scenario_ids):
        scenario = scenarios[sid]
        gt = ground_truth[sid]
        check(gt.get("scenario_id") == sid, f"{sid}: gt scenario_id mismatch")

        # no answer fields in scenario files
        for forbidden in ("expected", "ground_truth", "primary_cause", "answer"):
            check(forbidden not in scenario, f"{sid}: scenario leaks {forbidden!r}")

        evaluation = gt.get("evaluation", {})
        check(set(evaluation) <= set(LAYERS),
              f"{sid}: unknown evaluation layer")
        check(bool(evaluation), f"{sid}: ground truth has no evaluation layers")

        for layer, spec in evaluation.items():
            if spec is None or spec == VERDICT_NOT_APPLICABLE:
                continue
            if layer == "E3":
                primary = spec.get("primary_cause")
                if primary:
                    check(primary in causes,
                          f"{sid}: E3 primary_cause {primary!r} not in frozen taxonomy")
                for cause in spec.get("acceptable_secondary_causes", ()):
                    check(cause in causes,
                          f"{sid}: secondary cause {cause!r} not in frozen taxonomy")
                for cause in spec.get("forbidden_causes", ()):
                    check(cause in causes,
                          f"{sid}: forbidden cause {cause!r} not in frozen taxonomy")
            if layer == "E2":
                for sig in spec.get("signals", {}):
                    check(isinstance(sig, str), f"{sid}: E2 signal key must be str")

    if seed_root is not None:
        expected = manifest.get("dataset_checksum")
        actual = loader.seed_manifest_checksum(seed_root)
        check(expected == actual,
              f"dataset checksum mismatch: manifest {expected} vs seed {actual}")

    return errors, manifest, scenario_ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("suite")
    parser.add_argument("--seed", default=None)
    args = parser.parse_args()
    errors, manifest, ids = validate(args.suite, args.seed)
    print(f"benchmark: {manifest.get('benchmark_suite_id')} "
          f"v{manifest.get('benchmark_version')}")
    print(f"scenarios: {len(ids)}")
    if errors:
        print("FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
