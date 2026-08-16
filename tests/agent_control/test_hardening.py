"""Phase 13.8 Hardening + Enterprise E2E tests."""

from types import SimpleNamespace

import pytest

from app.platform.agent_control.audit import (
    AgentAuditLogger,
    OP_CREATED,
    OP_EXECUTED,
    OP_PUBLISHED,
)
from app.platform.agent_control.deployment import DeploymentManager
from app.platform.agent_control.domain import (
    AgentArtifact,
    PERM_EXECUTE,
    SUBJECT_DEPARTMENT,
)
from app.platform.agent_control.errors import AgentAccessDeniedError
from app.platform.agent_control.evaluation import AgentEvaluation, AgentEvaluationStore
from app.platform.agent_control.governance import AgentAccessControl, AgentAccessPolicy
from app.platform.agent_control.manifest import AgentManifest
from app.platform.agent_control.registry import AgentRegistry
from app.platform.agent_control.router import (
    AgentRoutingRequest,
    EnterpriseAgentRouter,
    RuleRouter,
)
from app.platform.agent_control.versioning import artifact_checksum


def _build_agent(agent_id, version, department, skills, capabilities):
    manifest = AgentManifest.from_dict({
        "agent_id": agent_id, "version": version, "owner": f"{agent_id}_team",
        "department": department, "skills": skills,
        "required_capabilities": capabilities,
        "security_policy": "default", "evaluation_policy": "default",
    })
    return AgentArtifact(
        agent_id=agent_id, version=version, manifest=manifest,
        skills=manifest.skills, capabilities=manifest.required_capabilities,
        checksum=artifact_checksum(manifest))


def _active_registry():
    registry = AgentRegistry()
    for artifact in (
        _build_agent("commerce_agent", "1.0", "marketing",
                     ("store_diagnosis",), ("commerce.metrics.read",)),
        _build_agent("finance_agent", "1.0", "finance",
                     ("finance_report",), ("finance.report.read",)),
    ):
        registry.register(artifact)
        registry.validate(artifact.agent_id)
        registry.activate(artifact.agent_id)
    return registry


# ── Enterprise E2E ──────────────────────────────────────────

def test_enterprise_e2e_control_plane_flow():
    registry = _active_registry()
    deployments = DeploymentManager(registry)
    governance = AgentAccessControl([AgentAccessPolicy(
        policy_id="p1", agent_id="commerce_agent",
        subject_type=SUBJECT_DEPARTMENT, subject_id="marketing",
        permission=PERM_EXECUTE)])
    router = EnterpriseAgentRouter(rule_router=RuleRouter(keyword_map={
        "commerce_agent": ("广告", "商品"), "finance_agent": ("财务", "报表")}))
    evaluation = AgentEvaluationStore()
    audit = AgentAuditLogger()

    # 1. deploy commerce agent to production
    deployments.deploy("commerce_agent", "PRODUCTION")
    assert deployments.get("commerce_agent", "PRODUCTION").agent_version == "1.0"

    # 2. authorize a marketing employee, deny a finance employee
    marketing = SimpleNamespace(subject_id="E1", department_id="marketing")
    finance = SimpleNamespace(subject_id="E2", department_id="finance")
    governance.authorize("commerce_agent", marketing, PERM_EXECUTE)
    with pytest.raises(AgentAccessDeniedError):
        governance.authorize("commerce_agent", finance, PERM_EXECUTE)

    # 3. route a message to the commerce agent
    result = router.route(AgentRoutingRequest(
        message="广告花费上涨", available_agents=("commerce_agent", "finance_agent")))
    assert result.selected_agent == "commerce_agent"

    # 4. record an evaluation
    evaluation.record(AgentEvaluation(
        evaluation_id="e1", agent_id="commerce_agent", agent_version="1.0",
        task_success=True, tool_calls=2, latency_ms=100, feedback=4.5))
    assert evaluation.summary("commerce_agent").success_rate == 1.0

    # 5. audit trail
    audit.record("commerce_agent", "1.0", "admin", OP_CREATED)
    audit.record("commerce_agent", "1.0", "admin", OP_PUBLISHED)
    audit.record("commerce_agent", "1.0", "E1", OP_EXECUTED, trace_id="t1")
    assert len(audit.list()) == 3


# ── Version replay ──────────────────────────────────────────

def test_version_replay_pins_old_version():
    registry = _active_registry()
    # commerce_agent@1.0 was executed; later 1.1 is published, but historical
    # replay must still resolve 1.0 by explicit version.
    v11 = _build_agent("commerce_agent", "1.1", "marketing",
                       ("store_diagnosis",), ("commerce.metrics.read",))
    registry.register(v11)
    registry.validate("commerce_agent", "1.1")
    assert registry.get("commerce_agent", "1.0").version == "1.0"
    assert registry.get("commerce_agent", "1.1").version == "1.1"
    # active remains 1.0 until explicitly activated
    assert registry.get_active_artifact("commerce_agent").version == "1.0"


# ── Audit / security ────────────────────────────────────────

def test_audit_record_never_contains_secret_or_credential():
    audit = AgentAuditLogger()
    record = audit.record("finance_agent", "1.0", "admin", OP_EXECUTED)
    data = record.to_dict()
    for forbidden in ("secret", "credential", "token", "password", "private"):
        assert forbidden not in data
        assert not hasattr(record, forbidden)


def test_agent_artifact_never_holds_private_data():
    artifact = _build_agent("sales_agent", "1.0", "sales",
                            ("sales_report",), ("sales.report.read",))
    data = artifact.to_dict()
    for forbidden in ("secret", "credential", "token", "user_list", "role"):
        assert forbidden not in data
