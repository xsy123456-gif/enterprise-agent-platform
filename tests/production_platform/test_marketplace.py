"""Phase 15.6 Marketplace tests."""

import pytest

from app.platform.production.errors import ProductionError
from app.platform.production.marketplace import (
    AgentCatalog,
    AgentCatalogEntry,
    AgentPublisher,
)


def test_catalog_entry_and_install():
    catalog = AgentCatalog()
    catalog.add(AgentCatalogEntry(
        agent_id="finance_agent", description="finance ops", category="finance",
        publisher="acme"))
    assert catalog.get("finance_agent").install_count == 0
    catalog.install("finance_agent", "company_A")
    assert catalog.get("finance_agent").install_count == 1


def test_publishing_state_machine():
    publisher = AgentPublisher()
    publisher.submit(AgentCatalogEntry(agent_id="finance_agent"))
    assert publisher.status("finance_agent") == "SUBMITTED"
    publisher.review("finance_agent")
    publisher.approve("finance_agent")
    publisher.publish("finance_agent")
    assert publisher.status("finance_agent") == "PUBLISHED"
    assert publisher.catalog.get("finance_agent") is not None


def test_publishing_requires_review_and_approval():
    publisher = AgentPublisher()
    publisher.submit(AgentCatalogEntry(agent_id="sales_agent"))
    with pytest.raises(ProductionError):
        publisher.publish("sales_agent")  # skip review/approve


def test_publishing_reject_is_terminal():
    publisher = AgentPublisher()
    publisher.submit(AgentCatalogEntry(agent_id="marketing_agent"))
    publisher.review("marketing_agent")
    publisher.reject("marketing_agent")
    with pytest.raises(ProductionError):
        publisher.approve("marketing_agent")
