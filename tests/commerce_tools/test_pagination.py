"""Pagination contract tests across the five paginated Commerce Read Tools."""

import pytest

from app.commerce.cursor import MAX_PAGE_LIMIT, encode_cursor
from app.commerce.trusted_context import reset_trusted_context, set_trusted_context

# tool_name -> (query args, expected total items)
QUERIES = {
    "catalog.query": ({"subject_type": "PRODUCT"}, 5),
    "metric.query": ({"subject_type": "STORE", "subject_id": "JP01",
                      "metric_names": ["GMV"]}, 5),
    "inventory.query": ({"store_id": "JP01", "sku_id": "sku_1"}, 3),
    "review.query": ({"subject_type": "REVIEW", "listing_id": "listing_1",
                      "store_id": "JP01"}, 3),
    "advertising.query": ({"subject_type": "CAMPAIGN", "store_id": "JP01"}, 3),
}

_ID_FIELDS = (
    "product_id", "metric_record_id", "inventory_snapshot_id", "review_id",
    "campaign_id", "ad_group_id", "ad_id", "keyword_id", "search_term_id",
    "listing_id", "listing_item_id", "review_insight_id",
)


def _key(item):
    if isinstance(item, dict):
        for field in _ID_FIELDS:
            if field in item:
                return (field, item[field])
        return str(sorted(item.items()))
    for field in _ID_FIELDS:
        if hasattr(item, field):
            return (field, getattr(item, field))
    return repr(item)


def _run(tool, args, trusted, **page):
    token = set_trusted_context(trusted)
    try:
        return tool.execute({**args, "page": dict(page)})
    finally:
        reset_trusted_context(token)


def _collect_pages(tool, args, trusted, limit=2):
    items = []
    cursor = None
    pages = []
    while True:
        result = _run(tool, args, trusted, limit=limit, cursor=cursor)
        assert not hasattr(result, "code")  # not a ToolError
        pages.append(result.page)
        items.extend(result.data)
        if not result.page.has_more:
            break
        cursor = result.page.next_cursor
    return items, pages


@pytest.mark.parametrize("tool_name", list(QUERIES))
def test_valid_continuation(surface, trusted_u001, tool_name):
    args, total = QUERIES[tool_name]
    tool = surface.tools[tool_name]
    items, pages = _collect_pages(tool, args, trusted_u001, limit=2)
    # Deterministic, complete, no overlap.
    assert len(items) == total
    assert len({_key(i) for i in items}) == total  # no duplicates across pages
    # next_cursor / has_more / returned_count are consistent.
    for index, page in enumerate(pages):
        assert page.returned_count == len(items[index * 2:(index + 1) * 2])
        if index < len(pages) - 1:
            assert page.has_more is True
            assert page.next_cursor is not None
        else:
            assert page.has_more is False
            assert page.next_cursor is None


@pytest.mark.parametrize("tool_name", list(QUERIES))
def test_malformed_cursor(surface, counting_repository, trusted_u001, tool_name):
    args, _ = QUERIES[tool_name]
    tool = surface.tools[tool_name]
    result = _run(tool, args, trusted_u001, limit=2, cursor="not-a-valid-cursor")
    assert result.code == "INVALID_REQUEST"
    assert counting_repository.query_count == 0


@pytest.mark.parametrize("tool_name", list(QUERIES))
def test_cross_resource_cursor(surface, counting_repository, trusted_u001, tool_name):
    args, _ = QUERIES[tool_name]
    tool = surface.tools[tool_name]
    # A cursor minted for a DIFFERENT context key must be rejected.
    foreign = encode_cursor("other:context", 2)
    result = _run(tool, args, trusted_u001, limit=2, cursor=foreign)
    assert result.code == "INVALID_REQUEST"
    assert counting_repository.query_count == 0


@pytest.mark.parametrize("tool_name", list(QUERIES))
def test_max_limit(surface, counting_repository, trusted_u001, tool_name):
    args, _ = QUERIES[tool_name]
    tool = surface.tools[tool_name]
    result = _run(tool, args, trusted_u001, limit=MAX_PAGE_LIMIT + 1)
    assert result.code == "INVALID_REQUEST"
    assert counting_repository.query_count == 0


@pytest.mark.parametrize("tool_name", list(QUERIES))
def test_deterministic_ordering(surface, trusted_u001, tool_name):
    args, _ = QUERIES[tool_name]
    tool = surface.tools[tool_name]
    first = _collect_pages(tool, args, trusted_u001, limit=2)[0]
    second = _collect_pages(tool, args, trusted_u001, limit=2)[0]
    assert [_key(i) for i in first] == [_key(i) for i in second]


def test_store_get_is_not_paginated(surface, trusted_u001):
    tool = surface.tools["store.get"]
    token = set_trusted_context(trusted_u001)
    try:
        result = tool.execute({"store_id": "JP01", "page": {"cursor": "garbage"}})
    finally:
        reset_trusted_context(token)
    # store.get ignores pagination entirely (single record).
    assert not hasattr(result, "code")
    assert result.data[0].store_id == "JP01"
