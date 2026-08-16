"""Deterministic enterprise commerce world generator (Phase 18.14).

Builds a synthetic, multi-tenant, multi-provider business world ("enterprise-
commerce-v1") and projects it into provider-native DTO files.  The generator is
fully deterministic (fixed random seed + fixed anchor date), world-first, and
produces no benchmark ground truth.

Run::

    python -m tools.seed.generate data/seed/enterprise-commerce-v1
"""

import hashlib
import json
import os
import random
from datetime import date, timedelta

DATASET_ID = "enterprise-commerce-v1"
SCHEMA_VERSION = 1
DATASET_VERSION = "1.0.0"
ANCHOR_DATE = date(2026, 8, 15)
HISTORY_DAYS = 90
RANDOM_SEED = 18014

START_DATE = ANCHOR_DATE - timedelta(days=HISTORY_DAYS - 1)
DAYS = [START_DATE + timedelta(days=i) for i in range(HISTORY_DAYS)]

TENANT_AURORA = "tenant_aurora"
TENANT_NORTHSTAR = "tenant_northstar"

# ── Static world definitions ────────────────────────────────────────────────

TENANTS = [
    {"tenant_id": TENANT_AURORA, "name": "Aurora Commerce"},
    {"tenant_id": TENANT_NORTHSTAR, "name": "Northstar Retail"},
]

STORES = [
    {"store_id": "AMAZON-JP-001", "tenant_id": TENANT_AURORA, "provider": "amazon",
     "external_store_id": "seller-aurora-jp", "marketplace": "JP",
     "country": "JP", "currency": "JPY", "timezone": "Asia/Tokyo",
     "status": "active", "order_prefix": "AMZJP"},
    {"store_id": "TIKTOK-US-001", "tenant_id": TENANT_AURORA, "provider": "tiktok",
     "external_store_id": "shop-aurora-us", "marketplace": "US",
     "country": "US", "currency": "USD", "timezone": "America/Los_Angeles",
     "status": "active", "order_prefix": "TTUSA"},
    {"store_id": "AMAZON-US-002", "tenant_id": TENANT_NORTHSTAR, "provider": "amazon",
     "external_store_id": "seller-northstar-us", "marketplace": "US",
     "country": "US", "currency": "USD", "timezone": "America/New_York",
     "status": "active", "order_prefix": "AMZUS"},
    {"store_id": "TIKTOK-UK-002", "tenant_id": TENANT_NORTHSTAR, "provider": "tiktok",
     "external_store_id": "shop-northstar-uk", "marketplace": "UK",
     "country": "GB", "currency": "GBP", "timezone": "Europe/London",
     "status": "active", "order_prefix": "TTUK"},
]

# product_id -> (tenant, title, brand, category, [(variant_code, variant_name)])
PRODUCT_SPECS = [
    (TENANT_AURORA, "Wireless Desk Lamp", "AuroraHome", "Lighting",
     [("BLK", "Black"), ("WHT", "White")]),
    (TENANT_AURORA, "Mechanical Keyboard", "AuroraHome", "Computer Accessories",
     [("BLK", "Black"), ("WHT", "White")]),
    (TENANT_AURORA, "Wireless Mouse", "AuroraHome", "Computer Accessories",
     [("BLK", "Black")]),
    (TENANT_AURORA, "USB-C Hub 7-in-1", "AuroraHome", "Computer Accessories",
     [("STD", "Standard")]),
    (TENANT_AURORA, "Monitor Stand", "AuroraHome", "Office Furniture",
     [("SLV", "Silver"), ("BLK", "Black")]),
    (TENANT_AURORA, "Ergonomic Office Chair", "AuroraHome", "Office Furniture",
     [("BLK", "Black")]),
    (TENANT_AURORA, "LED Desk Light", "AuroraHome", "Lighting",
     [("WHT", "White")]),
    (TENANT_AURORA, "Laptop Sleeve 13 inch", "AuroraHome", "Accessories",
     [("GRY", "Grey")]),
    (TENANT_AURORA, "Noise-Cancelling Headphones", "AuroraHome", "Audio",
     [("BLK", "Black"), ("WHT", "White")]),
    (TENANT_AURORA, "Smart Thermostat", "AuroraHome", "Smart Home",
     [("STD", "Standard")]),
    (TENANT_NORTHSTAR, "Standing Desk Converter", "NorthstarOffice", "Office Furniture",
     [("BLK", "Black"), ("WHT", "White")]),
    (TENANT_NORTHSTAR, "Wireless Charger Pad", "NorthstarOffice", "Accessories",
     [("STD", "Standard")]),
    (TENANT_NORTHSTAR, "Bluetooth Speaker", "NorthstarOffice", "Audio",
     [("BLK", "Black"), ("BLU", "Blue")]),
    (TENANT_NORTHSTAR, "Fitness Tracker Band", "NorthstarOffice", "Wearables",
     [("BLK", "Black")]),
    (TENANT_NORTHSTAR, "Air Purifier Compact", "NorthstarOffice", "Appliances",
     [("STD", "Standard")]),
    (TENANT_NORTHSTAR, "Insulated Bottle 1L", "NorthstarOffice", "Household",
     [("BLU", "Blue"), ("GRN", "Green")]),
]

# products sold on TikTok too (cross-channel).  Others are Amazon-only.
# Indices are 1-based global product indices.
AURORA_CROSS_CHANNEL = {1, 2, 3, 6, 9}
NORTHSTAR_CROSS_CHANNEL = {11, 12, 13, 14}

# Base daily orders per store.
STORE_BASELINE = {
    "AMAZON-JP-001": 8, "TIKTOK-US-001": 5,
    "AMAZON-US-002": 7, "TIKTOK-UK-002": 4,
}

# Business conditions keyed by (store_id) for cross-channel divergence and
# anomaly windows (facts only, no ground truth).
#   - "traffic_decline":   (start_offset, end_offset) 90-day window indices
#   - "cvr_decline":       conversion deterioration window
#   - "stockout_sku":      sku index that runs out of inventory
#   - "stockout_window":   (start, end)
#   - "ad_inefficiency":   (start, end) rising CPC / falling ROAS window
#   - "review_decline":    (start, end) low-rating cluster window
#   - "promotion":         (start, end) uplift window
STORE_CONDITIONS = {
    "AMAZON-JP-001": {
        "traffic_decline": (55, 75), "cvr_decline": (55, 75),
        "stockout_sku": 0, "stockout_window": (58, 72),
        "review_decline": (60, 75),
    },
    "TIKTOK-US-001": {"promotion": (30, 40)},
    "AMAZON-US-002": {
        "ad_inefficiency": (40, 60), "review_decline": (45, 60),
        "stockout_sku": 3, "stockout_window": (44, 58),
    },
    "TIKTOK-UK-002": {},
}


# ── Builders ─────────────────────────────────────────────────────────────────

def _iso(d):
    return d.isoformat()


def _sku_code(prod_idx, variant_code):
    return f"SKU-{prod_idx:02d}-{variant_code}"


def build_world():
    rng = random.Random(RANDOM_SEED)

    products = []
    skus = []
    for idx, (tenant, title, brand, category, variants) in enumerate(
            PRODUCT_SPECS, start=1):
        product_id = f"PRD-{idx:02d}"
        products.append({
            "product_id": product_id, "tenant_id": tenant, "title": title,
            "brand": brand, "category": category, "product_type": category,
        })
        for vcode, vname in variants:
            skus.append({
                "sku_id": _sku_code(idx, vcode), "tenant_id": tenant,
                "product_id": product_id, "merchant_sku": f"{product_id}-{vcode}",
                "variant": vname, "product_index": idx,
            })

    return {"products": products, "skus": skus}


def build_identity_map(skus):
    identity = {}
    for i, sku in enumerate(skus):
        idx = sku["product_index"]
        variant = sku["sku_id"].rsplit("-", 1)[1]
        ext = {"amazon": {"seller_sku": f"AU-{idx:02d}-{variant}",
                          "asin": f"B0SIM{i + 1:03d}"}}
        tenant = sku["tenant_id"]
        if tenant == TENANT_AURORA:
            ext["sap"] = {"material_number": f"MAT-{10000 + i + 1}"}
        else:
            ext["netsuite"] = {"item_internal_id": f"NS-{30000 + i + 1}"}
        # TikTok only for cross-channel products
        is_cross = (tenant == TENANT_AURORA and idx in AURORA_CROSS_CHANNEL) or \
                   (tenant == TENANT_NORTHSTAR and idx in NORTHSTAR_CROSS_CHANNEL)
        if is_cross:
            ext["tiktok"] = {"seller_sku": f"TT-{idx:02d}-{variant}",
                             "product_id": f"76{i + 1:07d}"}
        identity[sku["sku_id"]] = {
            "sku_id": sku["sku_id"],
            "tenant_id": tenant, "product_id": sku["product_id"],
            "external_ids": ext,
        }
    return identity


def _store_for(store_id):
    return next(s for s in STORES if s["store_id"] == store_id)


def _skus_for(products, skus, tenant):
    product_ids = {p["product_id"] for p in products if p["tenant_id"] == tenant}
    return [s for s in skus if s["product_id"] in product_ids]


def _listings_for_store(store, products, skus, identity):
    """Return provider listing records for a store (provider-native DTO)."""
    tenant = store["tenant_id"]
    tenant_skus = _skus_for(products, skus, tenant)
    cross = (AURORA_CROSS_CHANNEL if tenant == TENANT_AURORA
             else NORTHSTAR_CROSS_CHANNEL)
    out = []
    for sku in tenant_skus:
        idx = sku["product_index"]
        if store["provider"] == "tiktok" and idx not in cross:
            continue
        ext = identity[sku["sku_id"]]["external_ids"][store["provider"]]
        product = next(p for p in products if p["product_id"] == sku["product_id"])
        if store["provider"] == "amazon":
            out.append({
                "sellerSku": ext["seller_sku"], "asin": ext["asin"],
                "itemName": f"{product['title']} {sku['variant']}",
                "status": "Active", "seller_id": store["external_store_id"],
                "marketplace_id": store["marketplace"],
                "price": round(rng_price(sku), 2),
            })
        else:
            out.append({
                "seller_sku": ext["seller_sku"], "product_id": ext["product_id"],
                "title": f"{product['title']} {sku['variant']}",
                "status": "ACTIVE", "shop_id": store["external_store_id"],
                "price": round(rng_price(sku), 2),
            })
    return out


_price_cache = {}


def rng_price(sku):
    # deterministic base price from sku hash
    h = int(hashlib.md5(sku["sku_id"].encode()).hexdigest()[:8], 16)
    return 1500 + (h % 12000)


def _weekday_factor(d):
    return 1.25 if d.weekday() >= 5 else 0.9


def _in_window(d, condition):
    if not condition:
        return False
    start, end = condition
    offset = (d - START_DATE).days
    return start <= offset <= end


def _daily_order_count(store, d, rng):
    base = STORE_BASELINE[store["store_id"]]
    cond = STORE_CONDITIONS[store["store_id"]]
    factor = _weekday_factor(d) * (1.0 + rng.uniform(-0.15, 0.15))
    count = base * factor
    # promotion uplift
    if _in_window(d, cond.get("promotion")):
        count *= 1.8
    # traffic decline
    if _in_window(d, cond.get("traffic_decline")):
        count *= 0.55
    return max(0, int(round(count)))


def _advertised_skus(skus):
    return skus[:20]


def build_dataset():
    world = build_world()
    products = world["products"]
    skus = world["skus"]
    identity = build_identity_map(skus)
    rng = random.Random(RANDOM_SEED)

    # listings per store (world-level, then provider files)
    listings_by_store = {}
    for store in STORES:
        listings_by_store[store["store_id"]] = _listings_for_store(
            store, products, skus, identity)

    # orders + order items (per store, provider-native)
    orders = {}       # store_id -> list
    order_items = {}  # store_id -> list
    for store in STORES:
        tenant = store["tenant_id"]
        tenant_skus = _skus_for(products, skus, tenant)
        store_orders = []
        store_items = []
        seq = 0
        for d in DAYS:
            n = _daily_order_count(store, d, rng)
            for _ in range(n):
                seq += 1
                order_id = f"{store['order_prefix']}-{d.strftime('%Y%m%d')}-{seq:04d}"
                currency = store["currency"]
                pickable = [s for s in tenant_skus
                            if store["provider"] in identity[s["sku_id"]]["external_ids"]]
                items = rng.choices(pickable, k=rng.randint(1, 2))
                lines = []
                for sku in items:
                    ext = identity[sku["sku_id"]]["external_ids"].get(
                        store["provider"])
                    if ext is None:
                        continue
                    qty = rng.randint(1, 2)
                    unit = round(rng_price(sku) * rng.uniform(0.9, 1.1), 2)
                    lines.append({"sku": sku, "qty": qty, "unit": unit,
                                  "ext": ext})
                total = round(sum(l["qty"] * l["unit"] for l in lines), 2)
                store_orders.append({
                    "store": store["store_id"], "order_id": order_id,
                    "currency": currency, "date": _iso(d),
                    "status": "Shipped", "amount": total,
                    "lines": lines,
                })
                for l in lines:
                    store_items.append({
                        "order_id": order_id, "sku_id": l["sku"]["sku_id"],
                        "quantity": l["qty"], "unit_price": l["unit"],
                    })
        orders[store["store_id"]] = store_orders
        order_items[store["store_id"]] = store_items

    # reviews (provider-native)
    reviews = {}
    review_templates = {
        "pos": ["Works great, exactly as described.", "Very happy with this.",
                "Excellent build quality.", "Fast shipping, good value."],
        "neu": ["It is okay, nothing special.", "Average product for the price.",
                "Does the job."],
        "neg_quality": ["Stopped working after two weeks.", "Feels cheap and flimsy."],
        "neg_delivery": ["Arrived damaged.", "Very slow delivery."],
        "neg_size": ["Smaller than expected."],
    }
    for store in STORES:
        tenant = store["tenant_id"]
        store_listings = listings_by_store[store["store_id"]]
        out = []
        ri = 0
        for listing in store_listings:
            ext_id = listing.get("asin") or listing.get("product_id")
            cond = STORE_CONDITIONS[store["store_id"]]
            base_ratings = rng.randint(5, 9)  # reviews per listing
            for _ in range(base_ratings):
                ri += 1
                d = DAYS[rng.randint(0, HISTORY_DAYS - 1)]
                review_window = _in_window(d, cond.get("review_decline"))
                if review_window and rng.random() < 0.5:
                    kind = rng.choice(["neg_quality", "neg_delivery", "neg_size"])
                    rating = rng.randint(1, 3)
                else:
                    kind = rng.choice(["pos", "pos", "pos", "neu", "pos"])
                    rating = 5 if kind == "pos" else (4 if kind == "neu"
                                                      else rng.randint(3, 4))
                text = rng.choice(review_templates[kind])
                if store["provider"] == "amazon":
                    out.append({"reviewId": f"R-{store['order_prefix']}-{ri:04d}",
                                "asin": ext_id, "rating": rating,
                                "title": text.split(".")[0],
                                "content": text, "reviewDate": _iso(d)})
                else:
                    out.append({"review_id": f"R-{store['order_prefix']}-{ri:04d}",
                                "product_id": ext_id, "rating": rating,
                                "comment": text, "review_date": _iso(d)})
        reviews[store["store_id"]] = out

    # inventory snapshots (provider-native), coherent with sales
    inventory = {}
    for store in STORES:
        tenant = store["tenant_id"]
        tenant_skus = _skus_for(products, skus, tenant)
        cond = STORE_CONDITIONS[store["store_id"]]
        stockout_sku_idx = cond.get("stockout_sku")
        out = []
        for si, sku in enumerate(tenant_skus):
            ext = identity[sku["sku_id"]]["external_ids"].get(store["provider"])
            if ext is None:
                continue
            opening = 300 + (hashlib.md5(sku["sku_id"].encode()).digest()[0] % 400)
            available = opening
            for d in DAYS:
                # sales drain
                daily_sales = rng.randint(1, 6)
                available = max(0, available - daily_sales)
                # stockout: force depletion window
                if stockout_sku_idx is not None and si == stockout_sku_idx and \
                        _in_window(d, cond.get("stockout_window")):
                    available = 0
                elif available == 0 and d.day % 7 == 0:
                    available = rng.randint(50, 150)  # restock
                reserved = rng.randint(0, min(5, available))
                if store["provider"] == "amazon":
                    out.append({"sku": ext["seller_sku"], "fnSku": f"X{ext['asin'][-3:]}",
                                "fulfillable": available, "reserved": reserved,
                                "lastUpdated": _iso(d),
                                "seller_id": store["external_store_id"]})
                else:
                    out.append({"seller_sku": ext["seller_sku"],
                                "available_stock": available,
                                "reserved_stock": reserved, "updated_at": _iso(d),
                                "shop_id": store["external_store_id"]})
        inventory[store["store_id"]] = out

    # advertising (campaigns/adgroups/ads/keywords/searchterms)
    campaigns = {}
    for store in STORES:
        cond = STORE_CONDITIONS[store["store_id"]]
        prefix = "CMP-" + store["order_prefix"]
        out = []
        for c in range(rng.randint(3, 5)):
            out.append({
                "campaignId": f"{prefix}-{c + 1}", "name": f"Launch {c + 1}",
                "dailyBudget": 100.0, "state": "ENABLED",
                "targetingType": "AUTO" if c % 2 == 0 else "MANUAL",
                "seller_id": store["external_store_id"],
            })
        campaigns[store["store_id"]] = out

    # store daily metrics + sku advertising metrics
    store_metrics = {}
    ad_metrics = {}
    for store in STORES:
        cond = STORE_CONDITIONS[store["store_id"]]
        base_sessions = 2000
        rows = []
        for d in DAYS:
            wk = _weekday_factor(d)
            traffic = base_sessions * wk * (1 + rng.uniform(-0.1, 0.1))
            if _in_window(d, cond.get("traffic_decline")):
                traffic *= 0.5
            if _in_window(d, cond.get("promotion")):
                traffic *= 1.5
            cvr = 0.03 * (1 + rng.uniform(-0.2, 0.2))
            if _in_window(d, cond.get("cvr_decline")):
                cvr *= 0.6
            orders_n = int(traffic * cvr)
            gmv = orders_n * 3200
            rows.append({"store": store["store_id"], "date": _iso(d),
                         "sessions": int(traffic), "orders": orders_n,
                         "units": orders_n, "gmv": round(gmv, 2),
                         "conversion": round(cvr, 6)})
        store_metrics[store["store_id"]] = rows

        # sku-level advertising metrics
        adv = _advertised_skus(_skus_for(products, skus, store["tenant_id"]))
        adv_rows = []
        for sku in adv:
            for d in DAYS:
                imp = rng.randint(500, 3000)
                ctr = 0.02 + rng.uniform(0, 0.03)
                if _in_window(d, cond.get("ad_inefficiency")):
                    ctr *= 0.5  # falling efficiency
                clicks = int(imp * ctr)
                cpc = 20 + rng.uniform(0, 30)
                if _in_window(d, cond.get("ad_inefficiency")):
                    cpc *= 1.5
                spend = round(clicks * cpc, 2)
                orders_a = max(0, int(clicks * 0.08))
                sales = round(orders_a * rng_price(sku), 2)
                adv_rows.append({"store": store["store_id"], "sku_id": sku["sku_id"],
                                 "date": _iso(d), "impressions": imp,
                                 "clicks": clicks, "spend": spend,
                                 "orders": orders_a, "sales": sales})
        ad_metrics[store["store_id"]] = adv_rows

    # business events (facts only)
    events = [
        {"event_id": "EVT-0001", "event_type": "STOCKOUT",
         "effective_at": "2026-07-13T00:00:00Z", "store_id": "AMAZON-JP-001",
         "entity_id": "SKU-01-BLK"},
        {"event_id": "EVT-0002", "event_type": "PROMOTION_START",
         "effective_at": "2026-06-18T00:00:00Z", "store_id": "TIKTOK-US-001",
         "entity_id": "TIKTOK-US-001"},
        {"event_id": "EVT-0003", "event_type": "CAMPAIGN_BUDGET_CHANGED",
         "effective_at": "2026-06-28T00:00:00Z", "store_id": "AMAZON-US-002",
         "entity_id": "CMP-AMZUS-1"},
        {"event_id": "EVT-0004", "event_type": "LISTING_PRICE_CHANGED",
         "effective_at": "2026-07-20T00:00:00Z", "store_id": "AMAZON-JP-001",
         "entity_id": "B0SIM001"},
    ]

    return {
        "tenants": TENANTS, "stores": STORES, "products": products, "skus": skus,
        "identity": identity, "listings": listings_by_store, "orders": orders,
        "order_items": order_items, "reviews": reviews, "inventory": inventory,
        "campaigns": campaigns, "store_metrics": store_metrics,
        "ad_metrics": ad_metrics, "events": events,
    }


# ── Projection helpers ───────────────────────────────────────────────────────

def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _amazon_metrics(store, rows):
    out = []
    for r in rows:
        for name in ("sessions", "orders", "units", "gmv"):
            out.append({"metricName": name.upper(), "value": r.get(name, 0),
                        "period": "DAILY", "periodStart": r["date"],
                        "periodEnd": r["date"], "seller_id": store["external_store_id"]})
    return out


def _tiktok_metrics(store, rows):
    out = []
    for r in rows:
        for name in ("sessions", "orders", "units", "gmv"):
            out.append({"metric_name": name, "value": r.get(name, 0),
                        "period": "DAILY", "period_start": r["date"],
                        "period_end": r["date"], "shop_id": store["external_store_id"]})
    return out


def _sap_materials(skus, identity):
    out = []
    for sku in skus:
        ext = identity[sku["sku_id"]]["external_ids"].get("sap")
        if not ext:
            continue
        out.append({"MATNR": ext["material_number"],
                    "MAKTX": sku["merchant_sku"], "MTART": "FERT",
                    "WERKS": "PL01", "BUKRS": "CC01"})
    return out


def _sap_inventory(skus, identity, rng):
    out = []
    for sku in skus:
        ext = identity[sku["sku_id"]]["external_ids"].get("sap")
        if not ext:
            continue
        out.append({"MATNR": ext["material_number"], "WERKS": "PL01",
                    "LABST": 200 + rng.randint(0, 300), "UMLMC": rng.randint(0, 20),
                    "MEINS": "PC", "ERSDA": "2026-08-14"})
    return out


def _netsuite_items(skus, identity):
    out = []
    for sku in skus:
        ext = identity[sku["sku_id"]]["external_ids"].get("netsuite")
        if not ext:
            continue
        out.append({"internalId": ext["item_internal_id"], "itemId": sku["merchant_sku"],
                    "displayName": sku["merchant_sku"], "type": "InventoryItem",
                    "onHand": 200})
    return out


def _netsuite_sales_orders(order_lists):
    out = []
    for orders in order_lists:
        for o in orders:
            for l in o["lines"]:
                out.append({"internalId": f"NS-SO-{o['order_id']}",
                            "itemId": l["sku"]["merchant_sku"],
                            "quantity": l["qty"], "status": "PendingFulfillment",
                            "amount": o["amount"]})
    return out


def write_dataset(dataset, root):
    os.makedirs(root, exist_ok=True)
    world_dir = os.path.join(root, "world")
    providers_dir = os.path.join(root, "providers")
    os.makedirs(world_dir, exist_ok=True)
    for provider in ("amazon", "tiktok", "sap", "salesforce", "netsuite"):
        os.makedirs(os.path.join(providers_dir, provider), exist_ok=True)

    _write_json(os.path.join(world_dir, "tenants.json"), dataset["tenants"])
    _write_json(os.path.join(world_dir, "stores.json"), dataset["stores"])
    _write_jsonl(os.path.join(world_dir, "products.jsonl"), dataset["products"])
    _write_jsonl(os.path.join(world_dir, "skus.jsonl"), dataset["skus"])
    _write_json(os.path.join(world_dir, "identity_map.json"),
                {"skus": list(dataset["identity"].values())})
    _write_jsonl(os.path.join(world_dir, "business_events.jsonl"), dataset["events"])

    store_id_map = {s["store_id"]: s for s in dataset["stores"]}

    # Amazon projection (Aurora JP + Northstar US)
    amz_listings = dataset["listings"]["AMAZON-JP-001"] + \
        dataset["listings"]["AMAZON-US-002"]
    amz_orders = dataset["orders"]["AMAZON-JP-001"] + \
        dataset["orders"]["AMAZON-US-002"]
    amz_inv = dataset["inventory"]["AMAZON-JP-001"] + \
        dataset["inventory"]["AMAZON-US-002"]
    amz_reviews = dataset["reviews"]["AMAZON-JP-001"] + \
        dataset["reviews"]["AMAZON-US-002"]
    amz_campaigns = dataset["campaigns"]["AMAZON-JP-001"] + \
        dataset["campaigns"]["AMAZON-US-002"]
    amz_metrics = _amazon_metrics(store_id_map["AMAZON-JP-001"],
                                  dataset["store_metrics"]["AMAZON-JP-001"]) + \
        _amazon_metrics(store_id_map["AMAZON-US-002"],
                        dataset["store_metrics"]["AMAZON-US-002"])

    _write_jsonl(os.path.join(providers_dir, "amazon", "listings.jsonl"), amz_listings)
    _write_jsonl(os.path.join(providers_dir, "amazon", "orders.jsonl"),
                 [_amazon_order(o, store_id_map) for o in amz_orders])
    _write_jsonl(os.path.join(providers_dir, "amazon", "inventory.jsonl"), amz_inv)
    _write_jsonl(os.path.join(providers_dir, "amazon", "campaigns.jsonl"), amz_campaigns)
    _write_jsonl(os.path.join(providers_dir, "amazon", "reviews.jsonl"), amz_reviews)
    _write_jsonl(os.path.join(providers_dir, "amazon", "metrics.jsonl"), amz_metrics)

    # TikTok projection
    tt_products = dataset["listings"]["TIKTOK-US-001"] + \
        dataset["listings"]["TIKTOK-UK-002"]
    tt_orders = dataset["orders"]["TIKTOK-US-001"] + \
        dataset["orders"]["TIKTOK-UK-002"]
    tt_inv = dataset["inventory"]["TIKTOK-US-001"] + \
        dataset["inventory"]["TIKTOK-UK-002"]
    tt_reviews = dataset["reviews"]["TIKTOK-US-001"] + \
        dataset["reviews"]["TIKTOK-UK-002"]
    tt_campaigns = dataset["campaigns"]["TIKTOK-US-001"] + \
        dataset["campaigns"]["TIKTOK-UK-002"]
    tt_metrics = _tiktok_metrics(store_id_map["TIKTOK-US-001"],
                                 dataset["store_metrics"]["TIKTOK-US-001"]) + \
        _tiktok_metrics(store_id_map["TIKTOK-UK-002"],
                        dataset["store_metrics"]["TIKTOK-UK-002"])

    _write_jsonl(os.path.join(providers_dir, "tiktok", "products.jsonl"), tt_products)
    _write_jsonl(os.path.join(providers_dir, "tiktok", "orders.jsonl"),
                 [_tiktok_order(o, store_id_map) for o in tt_orders])
    _write_jsonl(os.path.join(providers_dir, "tiktok", "inventory.jsonl"), tt_inv)
    _write_jsonl(os.path.join(providers_dir, "tiktok", "campaigns.jsonl"), tt_campaigns)
    _write_jsonl(os.path.join(providers_dir, "tiktok", "reviews.jsonl"), tt_reviews)
    _write_jsonl(os.path.join(providers_dir, "tiktok", "metrics.jsonl"), tt_metrics)

    # SAP projection (Aurora)
    aurora_skus = _skus_for(dataset["products"], dataset["skus"], TENANT_AURORA)
    sap_rng = random.Random(RANDOM_SEED)
    _write_jsonl(os.path.join(providers_dir, "sap", "materials.jsonl"),
                 _sap_materials(aurora_skus, dataset["identity"]))
    _write_jsonl(os.path.join(providers_dir, "sap", "inventory.jsonl"),
                 _sap_inventory(aurora_skus, dataset["identity"], sap_rng))
    _write_jsonl(os.path.join(providers_dir, "sap", "purchase_orders.jsonl"),
                 _sap_po(aurora_skus, dataset["identity"]))

    # NetSuite projection (Northstar)
    ns_skus = _skus_for(dataset["products"], dataset["skus"], TENANT_NORTHSTAR)
    _write_jsonl(os.path.join(providers_dir, "netsuite", "items.jsonl"),
                 _netsuite_items(ns_skus, dataset["identity"]))
    _write_jsonl(os.path.join(providers_dir, "netsuite", "inventory.jsonl"),
                 _netsuite_inventory(ns_skus, dataset["identity"]))
    ns_order_lists = [dataset["orders"]["AMAZON-US-002"],
                      dataset["orders"]["TIKTOK-UK-002"]]
    _write_jsonl(os.path.join(providers_dir, "netsuite", "sales_orders.jsonl"),
                 _netsuite_sales_orders(ns_order_lists))
    _write_jsonl(os.path.join(providers_dir, "netsuite", "purchase_orders.jsonl"),
                 _netsuite_purchase_orders(ns_skus, dataset["identity"]))
    _write_jsonl(os.path.join(providers_dir, "netsuite", "fulfillments.jsonl"),
                 _netsuite_fulfillments(ns_order_lists))

    # Salesforce projection
    _write_jsonl(os.path.join(providers_dir, "salesforce", "accounts.jsonl"),
                 _salesforce_accounts())
    _write_jsonl(os.path.join(providers_dir, "salesforce", "contacts.jsonl"),
                 _salesforce_contacts())
    _write_jsonl(os.path.join(providers_dir, "salesforce", "opportunities.jsonl"),
                 _salesforce_opportunities())
    _write_jsonl(os.path.join(providers_dir, "salesforce", "cases.jsonl"),
                 _salesforce_cases())

    return _write_manifest(root, dataset, providers_dir)


def _amazon_order(o, store_id_map):
    store = store_id_map[o["store"]]
    lines = [l for l in o["lines"] if l["ext"]]
    first = lines[0] if lines else None
    return {
        "orderId": o["order_id"], "asin": first["ext"]["asin"] if first else "",
        "sellerSku": first["ext"]["seller_sku"] if first else "",
        "quantity": sum(l["qty"] for l in lines), "orderStatus": o["status"],
        "amount": o["amount"], "currency": o["currency"],
        "purchaseDate": o["date"] + "T00:00:00Z",
        "seller_id": store["external_store_id"],
    }


def _tiktok_order(o, store_id_map):
    store = store_id_map[o["store"]]
    lines = [l for l in o["lines"] if l["ext"]]
    first = lines[0] if lines else None
    return {
        "order_id": o["order_id"], "product_id": first["ext"]["product_id"] if first else "",
        "seller_sku": first["ext"]["seller_sku"] if first else "",
        "quantity": sum(l["qty"] for l in lines), "status": o["status"],
        "price": o["amount"], "currency": o["currency"],
        "created_at": o["date"] + "T00:00:00Z",
        "shop_id": store["external_store_id"],
    }


def _sap_po(skus, identity):
    out = []
    for i, sku in enumerate(skus):
        ext = identity[sku["sku_id"]]["external_ids"].get("sap")
        if not ext:
            continue
        out.append({"EBELN": f"PO-{5000 + i}", "MATNR": ext["material_number"],
                    "MENGE": 50 + i * 10, "WERKS": "PL01", "STATUS": "OPEN"})
    return out


def _netsuite_inventory(skus, identity):
    out = []
    for sku in skus:
        ext = identity[sku["sku_id"]]["external_ids"].get("netsuite")
        if not ext:
            continue
        out.append({"internalId": ext["item_internal_id"],
                    "itemId": sku["merchant_sku"], "location": "MAIN",
                    "onHand": 200, "committed": 5, "available": 195})
    return out


def _salesforce_accounts():
    names = ["Tesla", "Panasonic", "Sony", "Nintendo", "Canon", "Nikon",
             "Dell", "Lenovo", "HP", "Samsung", "LG", "Fujitsu"]
    return [{"Id": f"001000{1000 + i}", "Name": n, "Industry": "Electronics",
             "AnnualRevenue": 1000000.0 * (i + 1), "Type": "Customer"}
            for i, n in enumerate(names)]


def _salesforce_cases():
    out = []
    for i in range(20):
        out.append({"Id": f"500000{i:06d}", "AccountId": f"001000{1000 + i % 12}",
                    "CaseNumber": f"0001{i:04d}",
                    "Status": "Open" if i % 3 else "Closed",
                    "Priority": ["High", "Medium", "Low"][i % 3],
                    "Subject": "Order status inquiry" if i % 2 else
                               "Product quality concern"})
    return out


def _salesforce_contacts():
    out = []
    for i in range(12):
        out.append({"Id": f"003000{1000 + i}", "AccountId": f"001000{1000 + i}",
                    "FirstName": f"Contact{i + 1}", "LastName": "Example",
                    "Email": f"contact{i + 1}@example.com"})
    return out


def _salesforce_opportunities():
    out = []
    for i in range(10):
        out.append({"Id": f"006000{1000 + i}", "AccountId": f"001000{1000 + i % 12}",
                    "Name": f"Deal {i + 1}",
                    "StageName": "Negotiation" if i % 3 else "Closed Won",
                    "Amount": 50000.0 * (i + 1), "CloseDate": "2026-09-15"})
    return out


def _netsuite_purchase_orders(skus, identity):
    out = []
    for i, sku in enumerate(skus):
        ext = identity[sku["sku_id"]]["external_ids"].get("netsuite")
        if not ext:
            continue
        out.append({"internalId": f"PO-{3000 + i}", "itemId": sku["merchant_sku"],
                    "quantity": 40 + i * 5, "status": "PendingReceipt"})
    return out


def _netsuite_fulfillments(order_lists):
    out = []
    for orders in order_lists:
        for o in orders:
            if not o["lines"]:
                continue
            l = o["lines"][0]
            out.append({"internalId": f"IF-{o['order_id']}",
                        "salesOrderId": f"NS-SO-{o['order_id']}",
                        "itemId": l["sku"]["merchant_sku"], "quantity": l["qty"],
                        "status": "Shipped"})
    return out


def _write_manifest(root, dataset, providers_dir):
    counts = {
        "tenants": len(dataset["tenants"]),
        "stores": len(dataset["stores"]),
        "products": len(dataset["products"]),
        "skus": len(dataset["skus"]),
        "listings": sum(len(v) for v in dataset["listings"].values()),
        "orders": sum(len(v) for v in dataset["orders"].values()),
        "inventory_snapshots": sum(len(v) for v in dataset["inventory"].values()),
        "reviews": sum(len(v) for v in dataset["reviews"].values()),
        "campaigns": sum(len(v) for v in dataset["campaigns"].values()),
        "store_metrics": sum(len(v) for v in dataset["store_metrics"].values()),
        "ad_metrics": sum(len(v) for v in dataset["ad_metrics"].values()),
        "business_events": len(dataset["events"]),
    }
    checksums = {}
    for dirpath, _, files in os.walk(root):
        for fname in sorted(files):
            if fname == "manifest.json":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fname), root)
            checksums[rel] = _sha256(os.path.join(dirpath, fname))

    manifest = {
        "dataset_id": DATASET_ID,
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "anchor_date": ANCHOR_DATE.isoformat(),
        "history_days": HISTORY_DAYS,
        "random_seed": RANDOM_SEED,
        "synthetic": True,
        "counts": counts,
        "checksums": checksums,
    }
    _write_json(os.path.join(root, "manifest.json"), manifest)
    return manifest


def main():
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join("data", "seed", DATASET_ID)
    dataset = build_dataset()
    manifest = write_dataset(dataset, root)
    print(f"wrote {DATASET_ID} v{DATASET_VERSION} to {root}")
    print(f"counts: {manifest['counts']}")


if __name__ == "__main__":
    main()
