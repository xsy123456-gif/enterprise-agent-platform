"""Phase 18.14 seed integrity + ground-truth isolation tests."""

import json
import os

from tools.seed.validate import validate

from tests.business_world.conftest import SEED_ROOT


def test_seed_validation_passes():
    errors, manifest, _ = validate(SEED_ROOT)
    assert errors == []


def test_manifest_declares_synthetic_and_anchor():
    manifest = json.load(open(os.path.join(SEED_ROOT, "manifest.json")))
    assert manifest["dataset_id"] == "enterprise-commerce-v1"
    assert manifest["dataset_version"] == "1.0.0"
    assert manifest["synthetic"] is True
    assert manifest["anchor_date"] == "2026-08-15"
    assert manifest["history_days"] == 90
    assert manifest["random_seed"] == 18014


def test_seed_has_no_ground_truth_fields():
    forbidden = ("ground_truth", "expected_cause", "expected_diagnosis",
                 "expected_answer", "expected_response", "golden_answer",
                 "benchmark_score")
    for dirpath, _, files in os.walk(SEED_ROOT):
        for fname in files:
            if not fname.endswith((".json", ".jsonl", ".yaml", ".yml")):
                continue
            text = open(os.path.join(dirpath, fname), encoding="utf-8").read().lower()
            for field in forbidden:
                assert field not in text, f"{fname} leaks {field!r}"


def test_seed_has_no_secrets():
    for dirpath, _, files in os.walk(SEED_ROOT):
        for fname in files:
            if not fname.endswith((".json", ".jsonl", ".yaml", ".yml")):
                continue
            text = open(os.path.join(dirpath, fname), encoding="utf-8").read().lower()
            for pattern in ("begin private key", "bearer ", "aws_access_key"):
                assert pattern not in text, f"{fname} leaks secret material"


def test_seed_scale_is_business_world_not_fixture():
    manifest = json.load(open(os.path.join(SEED_ROOT, "manifest.json")))
    counts = manifest["counts"]
    assert counts["tenants"] == 2
    assert counts["stores"] == 4
    assert counts["products"] >= 15
    assert counts["skus"] >= 20
    assert counts["orders"] >= 1500
    assert counts["reviews"] >= 200
    assert counts["inventory_snapshots"] >= 2000


def test_identity_map_covers_all_skus():
    world = os.path.join(SEED_ROOT, "world")
    skus = _read_jsonl(os.path.join(world, "skus.jsonl"))
    identity = json.load(open(os.path.join(world, "identity_map.json")))["skus"]
    identity_by_sku = {i["sku_id"] for i in identity}
    for sku in skus:
        assert sku["sku_id"] in identity_by_sku, f"missing identity for {sku['sku_id']}"


def _read_jsonl(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
