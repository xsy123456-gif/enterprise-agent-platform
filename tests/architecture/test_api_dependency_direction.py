"""Phase 18.12 guard: API is the outermost adapter.

The API layer depends on the platform; the platform never depends on the API.
The API layer never executes tools / plans / repository / diagnostic kernel
directly (it goes through the Product Gateway + public service ports).
"""

from tests.architecture._scan import all_imports, scan_imports

_CORE_AREAS = (
    "app/core",
    "app/runtime",
    "app/execution",
    "app/commerce/domain",
    "app/commerce/repositories",
    "app/commerce/diagnostics",
    "app/platform",
)


def test_platform_does_not_import_api():
    for area in _CORE_AREAS:
        imports = all_imports(area)
        for mod in imports:
            assert not mod.startswith("app.api"), (
                f"{area} imports the API layer {mod!r}"
            )


def test_api_does_not_execute_tools_or_plans_directly():
    forbidden = (
        "app.runtime.tool_runner",
        "app.commerce.diagnostics.plans.executor",
        "app.commerce.repositories.inmemory",
        "app.commerce.repositories.postgres",
    )
    for path, imports in scan_imports("app/api").items():
        for mod in imports:
            for prefix in forbidden:
                assert not mod.startswith(prefix), (
                    f"{path} imports forbidden boundary {mod!r}"
                )


def test_api_idempotency_does_not_depend_on_runtime():
    imports = all_imports("app/api/idempotency")
    for mod in imports:
        assert not mod.startswith("app.runtime"), (
            f"api/idempotency imports runtime {mod!r}"
        )
        assert not mod.startswith("app.execution"), (
            f"api/idempotency imports execution {mod!r}"
        )


def test_product_agent_version_is_control_plane_authoritative():
    # The Product Gateway must not self-decide a managed agent's version from
    # a manifest default / local registry latest / hardcoded value: when the
    # control-plane registry owns the agent, resolution failure must raise
    # (fail-closed) instead of returning None or a fallback version.
    from app.api.gateway import EnterpriseProductGateway
    from app.platform.agent_control import AgentManifest
    from app.platform.agent_control.domain import AgentArtifact
    from app.platform.agent_control.registry import AgentRegistry
    from app.platform.agent_control.versioning import artifact_checksum

    manifest = AgentManifest.from_dict({
        "agent_id": "managed_agent", "version": "1.0", "owner": "team",
        "department": "commerce", "description": "ops",
        "skills": ("store_performance_diagnosis",),
        "required_capabilities": ("commerce.metrics.read",),
    })
    registry = AgentRegistry()
    registry.register(AgentArtifact(
        agent_id="managed_agent", version="1.0", manifest=manifest,
        checksum=artifact_checksum(manifest)))
    registry.validate("managed_agent", "1.0")
    registry.activate("managed_agent", "1.0")

    gateway = EnterpriseProductGateway(
        agent_directory={}, agent_definitions={}, execution_store=None,
        trace_collector=None, approval_repository=None, approval_engine=None,
        workflow_repository=None, workflow_engine=None, fact_executor=None,
        control_plane_registry=registry, allow_unmanaged_agent_fallback=False,
    )
    assert gateway._resolve_agent_version("managed_agent") == "1.0"

    # now break resolution: managed agent inactive -> must raise, never None
    registry.disable("managed_agent", "1.0")
    from app.api.errors import ApiError
    try:
        gateway._resolve_agent_version("managed_agent")
    except ApiError:
        pass
    else:
        raise AssertionError("managed-agent resolution must fail-closed")


