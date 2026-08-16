"""The seven v1 Business Skills (Phase 10).

Skill -> DiagnosticPlan mapping (§60):

- store_performance_diagnosis -> store_health_scan, gmv_decline_diagnosis,
  conversion_decline_diagnosis
- product_performance_diagnosis -> product_anomaly_diagnosis
- advertising_performance_diagnosis -> advertising_health_scan,
  roas_decline_diagnosis, high_spend_low_conversion, search_term_waste
- inventory_risk_diagnosis -> stockout_risk, slow_moving_inventory,
  inventory_sales_imbalance
- review_issue_diagnosis -> rating_deterioration, emerging_product_issue
- product_360_diagnosis -> product_360
- daily_operations_triage -> daily_operations_scan
"""

from app.commerce.skills.models import SkillDefinition

_VERSION = "1.0"


def build_business_skill_definitions():
    return [
        SkillDefinition(
            skill_id="store_performance_diagnosis", version=_VERSION, domain="sales",
            description="店铺经营诊断（巡检/GMV/转化）",
            plan_ids=("store_health_scan", "gmv_decline_diagnosis",
                      "conversion_decline_diagnosis"),
            default_plan_id="store_health_scan",
        ),
        SkillDefinition(
            skill_id="product_performance_diagnosis", version=_VERSION, domain="sales",
            description="商品/SKU 经营表现诊断",
            plan_ids=("product_anomaly_diagnosis",),
            default_plan_id="product_anomaly_diagnosis",
        ),
        SkillDefinition(
            skill_id="advertising_performance_diagnosis", version=_VERSION,
            domain="advertising", description="广告经营诊断（巡检/ROAS/高消耗/搜索词）",
            plan_ids=("advertising_health_scan", "roas_decline_diagnosis",
                      "high_spend_low_conversion", "search_term_waste"),
            default_plan_id="advertising_health_scan",
        ),
        SkillDefinition(
            skill_id="inventory_risk_diagnosis", version=_VERSION, domain="inventory",
            description="库存风险诊断（缺货/滞销/供需失衡）",
            plan_ids=("stockout_risk", "slow_moving_inventory",
                      "inventory_sales_imbalance"),
            default_plan_id="stockout_risk",
        ),
        SkillDefinition(
            skill_id="review_issue_diagnosis", version=_VERSION, domain="review",
            description="评价问题诊断（评分下滑/新兴质量问题）",
            plan_ids=("rating_deterioration", "emerging_product_issue"),
            default_plan_id="rating_deterioration",
        ),
        SkillDefinition(
            skill_id="product_360_diagnosis", version=_VERSION, domain="sales",
            description="商品 360 跨域诊断",
            plan_ids=("product_360",),
            default_plan_id="product_360",
        ),
        SkillDefinition(
            skill_id="daily_operations_triage", version=_VERSION, domain="sales",
            description="今日运营待办（跨域信号聚合）",
            plan_ids=("daily_operations_scan",),
            default_plan_id="daily_operations_scan",
        ),
    ]


__all__ = ["build_business_skill_definitions"]
