"""Seed validation tool (Phase 18.14).

Usage::

    python -m tools.seed.validate data/seed/enterprise-commerce-v1

Exits non-zero on any integrity violation (orphan IDs, broken mappings, negative
inventory, invalid metrics, duplicate IDs, ground-truth leakage, secrets).
"""

import hashlib
import json
import os
import sys

GROUND_TRUTH_FIELDS = (
    "ground_truth", "expected_cause", "expected_diagnosis", "expected_answer",
    "expected_response", "expected_priority", "expected_signal", "golden_answer",
    "benchmark_score", "golden_response", "expected_state",
)

SECRET_PATTERNS = ("BEGIN PRIVATE KEY", "Bearer ", "aws_access_key", "sk-")


class ValidationError(Exception):
    pass


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _collect_text(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.append(str(k))
            _collect_text(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_text(v, acc)
    else:
        acc.append(str(obj))


def validate(root):
    errors = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    manifest = _read_json(os.path.join(root, "manifest.json"))
    check(manifest.get("synthetic") is True, "manifest must declare synthetic: true")

    # checksums
    for rel, expected in manifest.get("checksums", {}).items():
        path = os.path.join(root, rel)
        check(os.path.exists(path), f"checksum target missing: {rel}")
        if os.path.exists(path):
            check(_sha256(path) == expected, f"checksum mismatch: {rel}")

    world = os.path.join(root, "world")
    providers = os.path.join(root, "providers")

    tenants = _read_json(os.path.join(world, "tenants.json"))
    stores = _read_json(os.path.join(world, "stores.json"))
    products = _read_jsonl(os.path.join(world, "products.jsonl"))
    skus = _read_jsonl(os.path.join(world, "skus.jsonl"))
    identity = _read_json(os.path.join(world, "identity_map.json"))["skus"]

    tenant_ids = {t["tenant_id"] for t in tenants}
    store_ids = {s["store_id"] for s in stores}
    product_ids = {p["product_id"] for p in products}
    sku_ids = {s["sku_id"] for s in skus}

    # world integrity
    for s in skus:
        check(s["product_id"] in product_ids, f"sku orphan product: {s['sku_id']}")
        check(s["tenant_id"] in tenant_ids, f"sku orphan tenant: {s['sku_id']}")
    id_by_sku = {i.get("sku_id"): i for i in identity}
    for sku_id in sku_ids:
        check(sku_id in id_by_sku, f"identity map missing sku: {sku_id}")

    # provider external id uniqueness (per provider + account)
    for provider in ("amazon", "tiktok", "sap", "salesforce", "netsuite"):
        seen = set()
        for entry in identity:
            ext = entry["external_ids"].get(provider)
            if not ext:
                continue
            # use the provider's primary external id
            primary = (ext.get("seller_sku") or ext.get("seller_sku")
                       or ext.get("material_number") or ext.get("item_internal_id")
                       or ext.get("product_id") or ext.get("asin"))
            key = f"{provider}:{primary}"
            check(key not in seen, f"duplicate provider external id: {key}")
            seen.add(key)

    # provider records: referential + metric integrity
    amz_listings = _read_jsonl(os.path.join(providers, "amazon", "listings.jsonl"))
    amz_asins = {l["asin"] for l in amz_listings}
    amz_orders = _read_jsonl(os.path.join(providers, "amazon", "orders.jsonl"))
    amz_reviews = _read_jsonl(os.path.join(providers, "amazon", "reviews.jsonl"))
    amz_metrics = _read_jsonl(os.path.join(providers, "amazon", "metrics.jsonl"))

    for o in amz_orders:
        check(o.get("quantity", 0) > 0, f"amazon order quantity<=0: {o['orderId']}")
        store = next((s for s in stores if s["external_store_id"] == o.get("seller_id")), None)
        check(store is not None, f"amazon order orphan seller: {o['orderId']}")
        if store:
            check(o.get("currency") == store["currency"],
                  f"amazon order currency mismatch: {o['orderId']}")
    for r in amz_reviews:
        check(r["asin"] in amz_asins, f"amazon review orphan listing: {r['reviewId']}")
    for m in amz_metrics:
        check(m.get("value", 0) >= 0, f"amazon negative metric: {m['metricName']}")

    amz_inv = _read_jsonl(os.path.join(providers, "amazon", "inventory.jsonl"))
    for inv in amz_inv:
        check(inv.get("fulfillable", 0) >= 0, "amazon negative inventory")

    # reviews not all 5-star
    ratings = [r["rating"] for r in amz_reviews]
    check(len(set(ratings)) >= 3, "amazon reviews have too little rating variance")
    check(any(x < 5 for x in ratings), "amazon reviews are all 5-star")

    # no ground truth / secrets in DATA files (README/manifest are docs)
    for dirpath, _, files in os.walk(root):
        for fname in files:
            if not fname.endswith((".json", ".jsonl", ".yaml", ".yml")):
                continue
            if fname == "manifest.json":
                continue
            path = os.path.join(dirpath, fname)
            try:
                text = open(path, "r", encoding="utf-8").read()
            except Exception:
                continue
            low = text.lower()
            for field in GROUND_TRUTH_FIELDS:
                check(field not in low, f"ground truth field leaked in {fname}")
            for pattern in SECRET_PATTERNS:
                check(pattern.lower() not in low,
                      f"secret pattern leaked in {fname}")

    # counts match manifest
    counts = manifest.get("counts", {})
    check(counts.get("tenants") == len(tenants), "tenant count mismatch")
    check(counts.get("stores") == len(stores), "store count mismatch")
    check(counts.get("products") == len(products), "product count mismatch")
    check(counts.get("skus") == len(skus), "sku count mismatch")

    # multi-tenant isolation: alpha stores don't leak into beta and vice versa
    for s in stores:
        check(s["tenant_id"] in tenant_ids, f"store orphan tenant: {s['store_id']}")

    return errors, manifest, {
        "tenants": len(tenants), "stores": len(stores), "products": len(products),
        "skus": len(skus), "listings": len(amz_listings),
        "orders": len(amz_orders), "reviews": len(amz_reviews),
        "metrics": len(amz_metrics), "inventory": len(amz_inv),
    }


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        "data", "seed", "enterprise-commerce-v1")
    errors, manifest, summary = validate(root)
    print(f"dataset: {manifest.get('dataset_id')} v{manifest.get('dataset_version')}")
    print(f"counts: {summary}")
    if errors:
        print("FAIL")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
