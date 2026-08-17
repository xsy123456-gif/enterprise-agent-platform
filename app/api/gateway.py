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
                 access_control=None, approval_authorizer=None,
                 control_plane_registry=None, deployment_projector=None,
                 allow_unmanaged_agent_fallback=False):
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
        self.approval_authorizer = approval_authorizer
        self.control_plane_registry = control_plane_registry
        self.deployment_projector = deployment_projector
        self.allow_unmanaged_agent_fallback = allow_unmanaged_agent_fallback

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
        version = self._resolve_agent_version(agent_id)
        from app.commerce.agents.errors import ResourceOwnershipError
        try:
            return runtime.handle(request, trusted_context, self.fact_executor,
                                  agent_version=version)
        except ResourceOwnershipError:
            raise not_found("Resource")

    def _resolve_agent_version(self, agent_id):
        # Fail-closed: the Control Plane is the sole authoritative source of
        # the executed agent version.  A managed agent whose resolution fails
        # (missing / inactive / mismatched / projection drift / unexpected
        # error) must deny execution — it never falls back to a default or
        # local version.  Only a genuinely unmanaged agent (no control-plane
        # deployment record) may fall back, and only under an explicit
        # dev/test policy (allow_unmanaged_agent_fallback).
        from app.platform.agent_control.errors import (
            AgentControlError,
            AgentNotActiveError,
        )
        registry = self.control_plane_registry
        if registry is None:
            if self.allow_unmanaged_agent_fallback:
                return None
            raise ApiError(ApiErrorCode.SERVICE_UNAVAILABLE,
                           "Agent version resolution is unavailable.",
                           http_status=503)
        if not registry.versions(agent_id):
            if self.allow_unmanaged_agent_fallback:
                return None
            raise not_found("Agent")
        try:
            artifact = registry.get_active_artifact(agent_id)
        except AgentNotActiveError:
            raise not_found("Agent")
        except AgentControlError:
            raise not_found("Agent")
        except Exception:
            raise ApiError(ApiErrorCode.SERVICE_UNAVAILABLE,
                           "Agent version resolution failed.", http_status=503)
        projector = self.deployment_projector
        if projector is not None and not projector.consistent(agent_id):
            raise ApiError(ApiErrorCode.INVALID_STATE,
                           "Agent deployment is inconsistent.", http_status=409)
        return artifact.version

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

    def get_approval(self, trusted_context, approval_id):
        return self._approval(trusted_context, approval_id)

    def approve(self, trusted_context, approval_id, comment):
        request = self._approval(trusted_context, approval_id)
        if not self._may_decide(trusted_context, request):
            from app.api.errors import permission_denied
            raise permission_denied()
        if request.status != "PENDING":
            raise ApiError(ApiErrorCode.INVALID_STATE,
                           "Approval is not pending.", http_status=409)
        updated = self.approval_engine.approve(request,
                                               trusted_context.principal_id)
        self._resume_workflow_after_approval(updated, "APPROVED")
        return updated

    def reject(self, trusted_context, approval_id, comment):
        request = self._approval(trusted_context, approval_id)
        if not self._may_decide(trusted_context, request):
            from app.api.errors import permission_denied
            raise permission_denied()
        if request.status != "PENDING":
            raise ApiError(ApiErrorCode.INVALID_STATE,
                           "Approval is not pending.", http_status=409)
        updated = self.approval_engine.reject(request,
                                              trusted_context.principal_id)
        self._resume_workflow_after_approval(updated, "REJECTED")
        return updated

    def _may_decide(self, trusted_context, request):
        if self.approval_authorizer is None:
            return True
        return self.approval_authorizer(trusted_context, request)

    def _resume_workflow_after_approval(self, request, decision):
        if not request.workflow_run_id:
            return
        run = self.workflow_repository.get(request.workflow_run_id)
        if run is None or run.status != "WAITING_APPROVAL":
            return
        try:
            self.workflow_engine.resume(
                request.workflow_run_id, {"approval_state": decision})
        except Exception:
            # workflow resume failure is visible via the workflow run state;
            # the approval decision itself remains recorded.
            pass

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
