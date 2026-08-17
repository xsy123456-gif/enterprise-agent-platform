"""Phase 18.0 guard: Agent isolation from data/execution boundaries.

An Agent (Employee Agent, Control Plane, Collaboration) must never reach the
Repository, the Tool surface, or an external Connector directly — it goes
through Skill / Plan / ToolRunner / Runtime.
"""

from tests.architecture._scan import all_imports

_AGENT_AREAS = (
    "app/commerce/agents",
    "app/platform/agent_control",
    "app/platform/agent_collaboration",
)

_FORBIDDEN_PREFIXES = (
    "app.commerce.repositories",
    "app.commerce.query",
    "app.commerce.tools",
    "app.commerce.integration.connectors",
    "app.commerce.integration",
    "app.runtime.tool_runner",
    "app.runtime.dispatcher",
)


def test_agent_does_not_reach_repository_query_or_connector():
    for area in _AGENT_AREAS:
        imports = all_imports(area)
        for forbidden in _FORBIDDEN_PREFIXES:
            for mod in imports:
                assert not mod.startswith(forbidden), (
                    f"{area} imports forbidden boundary {mod!r} "
                    f"(prefix {forbidden!r})"
                )


def test_agent_does_not_import_production_knowledge_store():
    # Knowledge is reached via AgentKnowledgePort (Serving Plane), never by
    # importing the Production Knowledge management store directly.
    for area in _AGENT_AREAS:
        imports = all_imports(area)
        for mod in imports:
            assert not mod.startswith("app.platform.production.knowledge"), (
                f"{area} imports production knowledge store {mod!r}"
            )


def test_agent_does_not_import_connector_credentials():
    # credentials/secret surface is Connector-Runtime-only, never reachable by
    # an agent layer.
    for area in _AGENT_AREAS:
        imports = all_imports(area)
        for mod in imports:
            assert "credential" not in mod.lower(), (
                f"{area} imports credential surface {mod!r}"
            )
