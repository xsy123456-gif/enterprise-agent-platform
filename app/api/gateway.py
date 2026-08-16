"""Enterprise Product Gateway (Phase 18.12).

A thin, stable Product Use-Case facade over the already-composed platform.  It
coordinates existing Application Services (Employee Agent, ExecutionManager,
ApprovalEngine, WorkflowEngine) and performs resource lookup + scope
enforcement.  It never re-implements business logic.
"""

from types import SimpleNamespace

from app.api.errors import ApiError, ApiErrorCode, not_found


class EnterpriseProductGateway:

    def __init__(self, agent_directory, agent_definitions, execution_store,
                 trace_collector, approval_repository, approval_engine,
                 workflow_repository, workflow_engine, fact_executor,
                 access_control=None):
        self.agent_directory = agent_directory
        self.agent_definitions = agent_definitions
        self.execution_store = execution_store
        self.trace_collector = trace_collector
        self.approval_repository = approval_repository
        self.approval_engine = approval_engine
        self.workflow_repository = workflow_repository
        self.workflow_engine = workflow_engine
        self.fact_executor = fact_executor
        self.access_control = access_control

    def _subject(self, trusted_context):
        return SimpleNamespace(
            subject_id=trusted_context.principal_id,
            roles=(),
            department_id="",
        )

    def _authorized(self, agent_id, trusted_context):
        if self.access_control is None:
            return True
        return self.access_control.check(
            agent_id, self._subject(trusted_context), "agent.execute")

    # ── Agents ──────────────────────────────────────────────

    def list_agents(self, trusted_context):
        definitions = []
        for agent_id, definition in self.agent_definitions.items():
            if self._authorized(agent_id, trusted_context):
                definitions.append(definition)
        return definitions

    def send_message(self, trusted_context, agent_id, message, session_id,
                     trace_id):
        runtime = self.agent_directory.get(agent_id)
        if runtime is None:
            raise not_found("Agent")
        if not self._authorized(agent_id, trusted_context):
            from app.api.errors import permission_denied
            raise permission_denied()
        from app.commerce.agents.domain import AgentRequest
        request = AgentRequest(
            request_id=trace_id or "",
            session_id=session_id or "",
            message=message,
            trace_id=trace_id or "",
        )
        return runtime.handle(request, trusted_context, self.fact_executor)

    # ── Execution ───────────────────────────────────────────

    def get_execution(self, trusted_context, execution_id):
        record = self.execution_store.get(execution_id)
        if record is None or record.tenant_id != trusted_context.tenant_id:
            raise not_found("Execution")
        return record

    def get_execution_trace(self, trusted_context, execution_id):
        record = self.get_execution(trusted_context, execution_id)
        trace = self.trace_collector.trace(record.trace_id)
        if trace is None:
            raise not_found("Trace")
        return trace, self.trace_collector.spans_for(record.trace_id)

    # ── Approval ────────────────────────────────────────────

    def list_approvals(self, trusted_context, status=None):
        pending = self.approval_repository.list_pending()
        visible = [r for r in pending if r.tenant_id == trusted_context.tenant_id]
        if status is not None:
            visible = [r for r in visible if r.status == status]
        return visible

    def _approval(self, trusted_context, approval_id):
        request = self.approval_repository.get(approval_id)
        if request is None or request.tenant_id != trusted_context.tenant_id:
            raise not_found("Approval")
        return request

    def approve(self, trusted_context, approval_id, comment):
        request = self._approval(trusted_context, approval_id)
        if request.status != "PENDING":
            raise ApiError(ApiErrorCode.INVALID_STATE,
                           "Approval is not pending.", http_status=409)
        return self.approval_engine.approve(request,
                                            trusted_context.principal_id)

    def reject(self, trusted_context, approval_id, comment):
        request = self._approval(trusted_context, approval_id)
        if request.status != "PENDING":
            raise ApiError(ApiErrorCode.INVALID_STATE,
                           "Approval is not pending.", http_status=409)
        return self.approval_engine.reject(request,
                                           trusted_context.principal_id)

    # ── Workflow ────────────────────────────────────────────

    def get_workflow_run(self, trusted_context, run_id):
        run = self.workflow_repository.get(run_id)
        if run is None:
            raise not_found("WorkflowRun")
        return run

    def resume_workflow(self, trusted_context, run_id, signal):
        run = self.workflow_repository.get(run_id)
        if run is None:
            raise not_found("WorkflowRun")
        if run.status == "WAITING_APPROVAL":
            raise ApiError(ApiErrorCode.APPROVAL_REQUIRED,
                           "Workflow is waiting for approval.",
                           http_status=409,
                           details={"approval_required": True})
        if signal != "CONTINUE":
            raise ApiError(ApiErrorCode.INVALID_RESUME_SIGNAL,
                           "Invalid resume signal.", http_status=409)
        return self.workflow_engine.resume(run_id,
                                           {"resume_signal": True})


__all__ = ["EnterpriseProductGateway"]
