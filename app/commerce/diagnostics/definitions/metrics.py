"""Core metric definitions (v1 first batch).

Every DERIVED metric has exactly one definition here — no Skill re-implements
a formula.  Leaf SOURCE / AGGREGATED metrics are also registered so the
resolver can distinguish them from DERIVED metrics and reject unknown
dependencies.
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
             zero_policy="NULL"):
    return MetricDefinition(
        metric=metric,
        metric_class=METRIC_CLASS_DERIVED,
        version=_VERSION,
        dependencies=tuple(dependencies),
        formula=formula,
        unit=unit,
        precision=precision,
        zero_policy=zero_policy,
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
        _aggregated("GMV", "currency"),
        _aggregated("NET_SALES", "currency"),
        _aggregated("ORDERS", "count"),
        _aggregated("UNITS", "count"),
        _aggregated("AD_ORDERS", "count"),
        _aggregated("ADD_TO_CARTS", "count"),
        _aggregated("SALES_VELOCITY", "units/day"),
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
        _derived("DAYS_OF_SUPPLY", ("AVAILABLE_INVENTORY", "SALES_VELOCITY"),
                 "AVAILABLE_INVENTORY / SALES_VELOCITY", unit="days", precision=2),
    ]
    return source_metrics + derived_metrics


def build_core_metric_registry():
    """Return a ``MetricDefinitionRegistry`` preloaded with the core metrics."""
    return MetricDefinitionRegistry().register_many(build_core_metric_definitions())


__all__ = [
    "build_core_metric_definitions",
    "build_core_metric_registry",
]
