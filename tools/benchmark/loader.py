"""Benchmark suite loader (Phase 18.15)."""

import json
import os

import yaml


def load_manifest(suite_root):
    with open(os.path.join(suite_root, "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


def load_scenario(suite_root, scenario_id):
    path = os.path.join(suite_root, "scenarios", f"{scenario_id}.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_ground_truth(suite_root, scenario_id):
    path = os.path.join(suite_root, "ground_truth", f"{scenario_id}.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def list_scenarios(suite_root):
    directory = os.path.join(suite_root, "scenarios")
    return sorted(
        f[:-5] for f in os.listdir(directory)
        if f.endswith(".yaml") and f.startswith("B")
    )


def load_all(suite_root):
    manifest = load_manifest(suite_root)
    scenarios = {}
    ground_truth = {}
    for scenario_id in list_scenarios(suite_root):
        scenarios[scenario_id] = load_scenario(suite_root, scenario_id)
        ground_truth[scenario_id] = load_ground_truth(suite_root, scenario_id)
    return manifest, scenarios, ground_truth


def seed_manifest_checksum(seed_root):
    import hashlib
    path = os.path.join(seed_root, "manifest.json")
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


__all__ = [
    "load_manifest",
    "load_scenario",
    "load_ground_truth",
    "list_scenarios",
    "load_all",
    "seed_manifest_checksum",
]
