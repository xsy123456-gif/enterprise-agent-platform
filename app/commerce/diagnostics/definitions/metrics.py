"""Core metric definitions (v1 first batch).

Every DERIVED metric has exactly one definition here — no Skill re-implements
a formula.  Leaf SOURCE / AGGREGATED metrics are also registered so the
resolver can distinguish them from DERIVED metrics and reject unknown
dependencies.

``SALES_VELOCITY`` is DERIVED (UNITS / PERIOD_DAYS), never a platform SOURCE
fact: it is computed from canonical sales facts plus period context, and no
fixed observation window is hard-coded.  ``DAYS_OF_SUPPLY`` depends on it and
pins its version so replay never drifts.
"""

from app.commerce.diagnostics.registry.metric_registry import MetricDefinitionRegistry
from app.commerce.domain.metrics import (
    METRIC_CLASS_AGGREGATED,
    METRIC_CLASS_DERIVED,
    METRIC_CLASS_SOURCE,
    MetricDefinition,
)

_VERSION = "1.0"


def _source(metric, unit=""):
    return MetricDefinition(
        metric=metric, metric_class=METRIC_CLASS_SOURCE, version=_VERSION, unit=unit,
    )


def _aggregated(metric, unit=""):
    return MetricDefinition(
        metric=metric, metric_class=METRIC_CLASS_AGGREGATED, version=_VERSION, unit=unit,
    )


def _derived(metric, dependencies, formula, unit="ratio", precision=4,
             zero_policy="NULL", dependency_versions=None):
    return MetricDefinition(
        metric=metric,
        metric_class=METRIC_CLASS_DERIVED,
        version=_VERSION,
        dependencies=tuple(dependencies),
        formula=formula,
        unit=unit,
        precision=precision,
        zero_policy=zero_policy,
        dependency_versions=dependency_versions or {},
    )


def build_core_metric_definitions():
    """Return the v1 core metric definitions (source + derived)."""
    source_metrics = [
        _source("IMPRESSIONS", "count"),
        _source("CLICKS", "count"),
        _source("SESSIONS", "count"),
        _source("AD_SPEND", "currency"),
        _source("AD_SALES", "currency"),
        _source("AD_CLICKS", "count"),
        _source("AVAILABLE_INVENTORY", "units"),
        # Period context for velocity; supplied by the plan from period start/end.
        _source("PERIOD_DAYS", "days"),
        _aggregated("GMV", "currency"),
        _aggregated("NET_SALES", "currency"),
        _aggregated("ORDERS", "count"),
        _aggregated("UNITS", "count"),
        _aggregated("AD_ORDERS", "count"),
        _aggregated("ADD_TO_CARTS", "count"),
        _aggregated("REFUND_AMOUNT", "currency"),
    ]
    derived_metrics = [
        # Sales
        _derived("AOV", ("GMV", "ORDERS"), "GMV / ORDERS", unit="currency", precision=2),
        _derived("REFUND_RATE", ("REFUND_AMOUNT", "GMV"), "REFUND_AMOUNT / GMV"),
        # Traffic
        _derived("CTR", ("CLICKS", "IMPRESSIONS"), "CLICKS / IMPRESSIONS"),
        # Conversion
        _derived("CVR", ("ORDERS", "SESSIONS"), "ORDERS / SESSIONS"),
        _derived("ADD_TO_CART_RATE", ("ADD_TO_CARTS", "SESSIONS"),
                 "ADD_TO_CARTS / SESSIONS"),
        # Advertising
        _derived("CPC", ("AD_SPEND", "CLICKS"), "AD_SPEND / CLICKS", unit="currency"),
        _derived("ROAS", ("AD_SALES", "AD_SPEND"), "AD_SALES / AD_SPEND"),
        _derived("ACOS", ("AD_SPEND", "AD_SALES"), "AD_SPEND / AD_SALES"),
        _derived("AD_CVR", ("AD_ORDERS", "AD_CLICKS"), "AD_ORDERS / AD_CLICKS"),
        # Inventory
        _derived("SALES_VELOCITY", ("UNITS", "PERIOD_DAYS"), "UNITS / PERIOD_DAYS",
                 unit="units/day", precision=2),
        _derived("DAYS_OF_SUPPLY", ("AVAILABLE_INVENTORY", "SALES_VELOCITY"),
                 "AVAILABLE_INVENTORY / SALES_VELOCITY", unit="days", precision=2,
                 dependency_versions={"SALES_VELOCITY": _VERSION}),
    ]
    return source_metrics + derived_metrics


def build_core_metric_registry():
    """Return a ``MetricDefinitionRegistry`` preloaded with the core metrics."""
    return MetricDefinitionRegistry().register_many(build_core_metric_definitions())


__all__ = [
    "build_core_metric_definitions",
    "build_core_metric_registry",
]
