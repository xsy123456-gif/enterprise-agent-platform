"""Phase 18.10 Persistence Boundary tests.

Behavioral proof that core Services use Repository/Store Ports (not internal
dicts): injecting a recording adapter shows the Service writes through the
boundary, so a future PostgreSQL adapter requires zero Service change.
"""

from app.platform.business.action import (
    ActionProposal,
    BusinessActionRuntime,
    BusinessActionRepository,
)
from app.platform.business.approval import (
    ApprovalEngine,
    ApprovalPolicy,
    ApprovalRepository,
)
from app.platform.business.workflow import (
    ApprovalStepAdapter,
    BusinessWorkflow,
    WorkflowEngine,
    WorkflowRunRepository,
    WorkflowStep,
)
from app.platform.intelligence.evaluation import (
    EvaluationStore,
    EvaluationSubscriber,
)
from app.platform.production.observability import AgentMetricSample


class _RecordingApprovalRepository(ApprovalRepository):
    def __init__(self):
        self.requests = []

    def put(self, request):
        self.requests.append(request)
        return request

    def get(self, approval_id):
        matches = [r for r in self.requests if r.approval_id == approval_id]
        return matches[-1] if matches else None

    def list_pending(self):
        return [r for r in self.requests if r.status == "PENDING"]


class _RecordingActionRepository(BusinessActionRepository):
    def __init__(self):
        self.actions = []

    def put(self, action):
        self.actions.append(action)
        return action

    def get(self, action_id):
        matches = [a for a in self.actions if a.action_id == action_id]
        return matches[-1] if matches else None


class _RecordingRunRepository(WorkflowRunRepository):
    def __init__(self):
        self.runs = []

    def save(self, run):
        self.runs.append(run)
        return run

    def get(self, run_id):
        return next((r for r in self.runs if r.run_id == run_id), None)


class _RecordingEvaluationStore(EvaluationStore):
    def __init__(self):
        self.evaluations = []

    def put(self, evaluation):
        self.evaluations.append(evaluation)
        return evaluation

    def list(self):
        return list(self.evaluations)


def test_approval_engine_uses_repository():
    repo = _RecordingApprovalRepository()
    engine = ApprovalEngine([ApprovalPolicy(
        policy_id="p1", action_type="UPDATE_AD_BUDGET", risk_level="HIGH",
        required_approvers=("director",))], repository=repo)
    request = engine.create_request("a1", "act1", "company_A", "agent",
                                    "UPDATE_AD_BUDGET", "HIGH")
    approved = engine.approve(request, "director")
    assert repo.get("a1") == approved
    assert len(repo.requests) == 2  # create + approve


def test_business_action_runtime_uses_repository():
    repo = _RecordingActionRepository()
    runtime = BusinessActionRuntime(repository=repo,
                                    action_handler=lambda a, c: None)
    action = runtime.create_action(ActionProposal(
        proposal_id="p1", agent_id="agent", action_type="UPDATE_AD_BUDGET",
        target="campaign_A", risk_level="LOW"))
    result = runtime.execute(action)
    assert repo.get(action.action_id) == result
    assert any(a.status == "SUCCEEDED" for a in repo.actions)


def test_workflow_engine_uses_run_repository():
    repo = _RecordingRunRepository()
    engine = WorkflowEngine(
        step_adapters=[ApprovalStepAdapter(
            lambda step, ctx: ctx.get("approval_state", "PENDING"))],
        run_repository=repo)
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[WorkflowStep(step_id="a", step_type="APPROVAL")],
    )
    run = engine.run(workflow, context={"approval_state": "PENDING"})
    assert run.status == "WAITING_APPROVAL"
    assert repo.get(run.run_id) is not None
    resumed = engine.resume(run.run_id, {"approval_state": "APPROVED"})
    assert resumed.status == "COMPLETED"


def test_evaluation_subscriber_uses_store():
    store = _RecordingEvaluationStore()
    subscriber = EvaluationSubscriber(evaluation_store=store)
    subscriber.on_metric_sample(AgentMetricSample(
        tenant_id="company_A", agent_id="ag", agent_version="1.0",
        success=True, latency_ms=5.0, execution_id="e1", trace_id="t1"))
    assert len(store.evaluations) == 1
    assert store.evaluations[0].execution_id == "e1"


def test_workflow_resume_by_unknown_id_fails():
    from app.platform.business.errors import WorkflowError
    import pytest
    engine = WorkflowEngine()
    with pytest.raises(WorkflowError):
        engine.resume("missing-run-id")
