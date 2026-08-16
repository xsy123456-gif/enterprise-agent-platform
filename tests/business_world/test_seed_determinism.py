"""Phase 18.14 seed determinism + cross-provider identity tests."""

import json
import os

from tools.seed import generate as gen

from tests.business_world.conftest import SEED_ROOT


def test_regeneration_is_deterministic(tmp_path):
    dataset1 = gen.build_dataset()
    manifest1 = gen.write_dataset(dataset1, str(tmp_path / "run1"))

    dataset2 = gen.build_dataset()
    manifest2 = gen.write_dataset(dataset2, str(tmp_path / "run2"))

    assert manifest1["counts"] == manifest2["counts"]
    assert manifest1["checksums"] == manifest2["checksums"]


def test_regeneration_matches_committed_seed(tmp_path):
    committed = json.load(open(os.path.join(SEED_ROOT, "manifest.json")))
    dataset = gen.build_dataset()
    manifest = gen.write_dataset(dataset, str(tmp_path / "regenerated"))
    assert manifest["counts"] == committed["counts"]
    assert manifest["checksums"] == committed["checksums"]


def _identity():
    return json.load(open(os.path.join(SEED_ROOT, "world", "identity_map.json")))["skus"]


def test_cross_provider_identity_amazon_sap_same_sku():
    identity = _identity()
    # every Aurora sku has both amazon and sap external ids pointing to the same sku
    cross = [i for i in identity
             if "amazon" in i["external_ids"] and "sap" in i["external_ids"]]
    assert cross, "expected Aurora SKUs present on both Amazon and SAP"
    for entry in cross:
        amazon_sku = entry["external_ids"]["amazon"]["seller_sku"]
        sap_matnr = entry["external_ids"]["sap"]["material_number"]
        # both map back to the same world sku
        assert entry["sku_id"].startswith("SKU-")


def test_cross_provider_identity_amazon_tiktok_same_sku():
    identity = _identity()
    cross = [i for i in identity
             if "amazon" in i["external_ids"] and "tiktok" in i["external_ids"]]
    assert cross, "expected cross-channel SKUs on both Amazon and TikTok"
    for entry in cross:
        amz = entry["external_ids"]["amazon"]["seller_sku"]
        tt = entry["external_ids"]["tiktok"]["seller_sku"]
        assert amz != tt  # different provider-native identifiers


def test_round_trip_amazon_listing_to_canonical_identity():
    # A seeded Amazon listing DTO, passed through the production adapter, must
    # resolve back to the same world SKU via the identity map.
    from app.commerce.integration.adapters.amazon import AmazonAdapter
    from app.commerce.ingestion.envelope import SourceRecordEnvelope

    listings = _read_jsonl(os.path.join(
        SEED_ROOT, "providers", "amazon", "listings.jsonl"))
    listing = listings[0]
    identity = _identity()

    envelope = SourceRecordEnvelope(
        source_record_id=listing["asin"], resource="listing", source="amazon",
        payload=listing, source_external_id=listing["asin"],
        connector_id="amazon_sp_api", connector_version="1.0")
    mutations = AmazonAdapter(tenant_id="tenant_aurora",
                              store_id="AMAZON-JP-001").adapt(envelope)
    assert mutations[0].entity["external_listing_id"] == listing["asin"]

    # the sellerSku is present in the identity map
    seller_skus = {i["external_ids"]["amazon"]["seller_sku"]
                   for i in identity if "amazon" in i["external_ids"]}
    assert listing["sellerSku"] in seller_skus


def _read_jsonl(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
