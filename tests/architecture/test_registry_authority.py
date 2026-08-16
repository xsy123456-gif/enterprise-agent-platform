"""Phase 18.0 guard: Registry Authority.

The Agent Control Plane Registry is the source of truth for enterprise Agent
assets (AgentArtifact + version + lifecycle + deployment + checksum).  The
Runtime Registry and the Commerce Agent Registry are projections, not the asset
authority — so ``AgentArtifact`` (with content checksum) must be owned only by
the control plane.
"""

from tests.architecture._scan import scan_imports

_CONTROL_PLANE = "app/platform/agent_control"


def test_control_plane_owns_agent_artifact():
    control_files = scan_imports(_CONTROL_PLANE)
    artifact_owner = [f for f in control_files if "domain" in f]
    assert artifact_owner, "control plane must own the agent artifact domain"


def test_runtime_and_commerce_do_not_own_artifact():
    # Runtime / Commerce agent registries are projections; they must not define
    # their own AgentArtifact (content-addressed asset) concept.
    for area in ("app/runtime", "app/commerce/agents"):
        for path, imports in scan_imports(area).items():
            assert "app.platform.agent_control" not in imports, (
                f"{path} must not import the control-plane domain (projection "
                f"should be constructed by the DeploymentProjector, not imported)"
            )
