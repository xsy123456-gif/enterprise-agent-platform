"""Phase 18.1 Composition Gate tests."""

from app.composition.enterprise import (
    EnterpriseApplication,
    build_enterprise_application,
)


def test_enterprise_application_composes_all_partitions():
    app = build_enterprise_application("development")
    assert isinstance(app, EnterpriseApplication)
    # Foundation
    assert app.foundation.runtime is not None
    assert app.foundation.registry is not None
    assert app.foundation.event_bus is not None
    # Commerce (L2)
    assert app.commerce.repository is not None
    assert app.commerce.query_service is not None
    assert app.commerce.skill_system is not None
    assert app.commerce.tool_surface is not None
    # Employee Agent (L3)
    assert app.agents.runtime is not None
    # Control Plane (L4)
    assert app.control_plane.registry is not None
    assert app.control_plane.deployment is not None
    # Collaboration (L4)
    assert app.collaboration.orchestrator is not None
    assert app.collaboration.aggregator is not None
    # Production (L5)
    assert app.production.trace is not None
    assert app.production.metrics is not None
    # Business (L6)
    assert app.business.packages is not None
    assert app.business.action_runtime is not None
    assert app.business.workflow_engine is not None
    # Intelligence (L7)
    assert app.intelligence.evaluation is not None
    assert app.intelligence.governance is not None


def test_enterprise_application_lifecycle():
    app = build_enterprise_application("testing")
    app.start()
    assert app.started is True
    app.stop()
    assert app.started is False


def test_commerce_tools_available_from_composition():
    app = build_enterprise_application("development")
    tools = app.commerce.tool_surface.tools
    assert "store.get" in tools
    assert "review_insight.query" in tools
