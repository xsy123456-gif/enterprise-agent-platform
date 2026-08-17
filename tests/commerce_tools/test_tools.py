"""Commerce Read Tool unit tests: scope, validation, contracts."""

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans.ports import FactQuerySpec
from app.commerce.platform import ToolRunnerFactQueryExecutor
from app.commerce.trusted_context import set_trusted_context, reset_trusted_context


def _execute(tool, arguments, trusted):
    token = set_trusted_context(trusted)
    try:
        return tool.execute(arguments)
    finally:
        reset_trusted_context(token)


def test_store_get_allowed(store_tool, trusted_u001):
    result = _execute(store_tool, {"store_id": "JP01"}, trusted_u001)
    assert result.data[0].store_id == "JP01"


def test_store_get_scope_denied(store_tool, trusted_u001):
    result = _execute(store_tool, {"store_id": "US01"}, trusted_u001)
    assert result.code == "PERMISSION_DENIED"


def test_metric_query_source_allowed(metric_tool, trusted_u001):
    result = _execute(metric_tool, {
        "subject_type": "STORE", "subject_id": "JP01",
        "metric_names": ["GMV"],
    }, trusted_u001)
    assert result.data[0].metric_name == "GMV"


def test_metric_query_derived_rejected(metric_tool, trusted_u001):
    result = _execute(metric_tool, {
        "subject_type": "STORE", "subject_id": "JP01",
        "metric_names": ["ROAS"],
    }, trusted_u001)
    assert result.code == "INVALID_REQUEST"


def test_inventory_query_facts_only(inventory_tool, trusted_u001):
    result = _execute(inventory_tool, {"store_id": "JP01", "sku_id": "sku_1"}, trusted_u001)
    assert result.data[0].inventory_snapshot_id == "inv1"
    assert not hasattr(result.data[0], "days_of_supply")


def test_review_query_include_raw_default_false(review_tool, trusted_u001):
    result = _execute(review_tool, {"listing_id": "listing_1", "store_id": "JP01"}, trusted_u001)
    assert "content" not in result.data[0]


def test_missing_trusted_context_denied(store_tool):
    result = store_tool.execute({"store_id": "JP01"})
    assert result.code == "PERMISSION_DENIED"


@pytest.fixture
def store_tool(surface):
    return surface.tools["store.get"]


@pytest.fixture
def metric_tool(surface):
    return surface.tools["metric.query"]


@pytest.fixture
def inventory_tool(surface):
    return surface.tools["inventory.query"]


@pytest.fixture
def review_tool(surface):
    return surface.tools["review.query"]
