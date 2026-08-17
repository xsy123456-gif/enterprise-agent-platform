"""Conversation runtime (Phase 12.4).

The ``ConversationManager`` orchestrates the full employee-agent flow:

    User -> session -> memory context -> router -> Skill -> DiagnosticResult
         -> response builder -> response -> (async) memory submit.

It manages history and context organization only; it never queries data
directly, never decides permissions, and never performs business analysis.
``trusted_context`` is the *only* source of tenant / principal / scope and is
injected by the caller — never derived from the request.
"""

import uuid

from app.commerce.agents.domain import (
    RESPONSE_CLARIFICATION,
    RESPONSE_ERROR,
    AgentDefinition,
    AgentRequest,
    AgentResponse,
)
from app.commerce.agents.manifest import AgentManifest
from app.commerce.agents.router.contract import SkillRoutingRequest
from app.commerce.agents.conversation.history import ConversationHistory
from app.commerce.agents.response.builder import ResponseBuilder


class ConversationManager:
    """Employee agent conversation orchestrator."""

    def __init__(self, agent_definition: AgentDefinition,
                 manifest: AgentManifest, binding_registry, skill_system,
                 router, response_builder=None, memory_port=None,
                 knowledge_port=None, knowledge_enabled=False,
                 execution_adapter=None):
        self.agent_definition = agent_definition
        self.manifest = manifest
        self.binding_registry = binding_registry
        self.skill_system = skill_system
        self.router = router
        self.response_builder = response_builder or ResponseBuilder()
        self.memory_port = memory_port
        self.knowledge_port = knowledge_port
        self.knowledge_enabled = knowledge_enabled
        self.execution_adapter = execution_adapter
        self.history = ConversationHistory()

    def handle(self, request: AgentRequest, trusted_context,
               fact_executor, agent_version=None) -> AgentResponse:
        if trusted_context is None or not trusted_context.tenant_id:
            return self._error(request, "missing trusted execution context")

        resolved_version = agent_version or self.agent_definition.version
        available = self.binding_registry.skill_ids(self.agent_definition.agent_id)
        memory_snippets = self._retrieve_memory(request)

        routing = self.router.route(SkillRoutingRequest(
            message=request.message, available_skills=available,
        ))
        if (routing.subject_tenant
                and trusted_context.tenant_id
                and routing.subject_tenant != trusted_context.tenant_id):
            from app.commerce.agents.errors import ResourceOwnershipError
            raise ResourceOwnershipError(
                f"resource owned by {routing.subject_tenant!r} is not accessible "
                f"to tenant {trusted_context.tenant_id!r}"
            )
        skill_id = routing.selected_skill or self.manifest.default_skill
        subject = routing.subject

        if not skill_id or subject is None:
            return self._clarification(request)

        execution_id = ""
        trace_id = request.trace_id or ""
        try:
            if self.execution_adapter is not None:
                from app.commerce.skills import SkillExecutionContext
                execution_context = SkillExecutionContext(
                    execution_id=uuid.uuid4().hex,
                    trace_id=trace_id or uuid.uuid4().hex,
                    tenant_id=trusted_context.tenant_id,
                    agent_id=self.agent_definition.agent_id,
                    agent_version=resolved_version,
                    principal_id=getattr(trusted_context, "principal_id", ""),
                )
                skill_result = self.execution_adapter.execute(
                    execution_context, skill_id, subject,
                    trusted_context=trusted_context,
                    fact_executor=fact_executor,
                )
                execution_id = execution_context.execution_id
                trace_id = execution_context.trace_id
            else:
                skill_result = self.skill_system.run(
                    skill_id, subject,
                    trusted_context=trusted_context,
                    fact_executor=fact_executor,
                )
        except Exception as error:  # noqa: BLE001 - surfaced as typed response
            return self._error(request, str(error))

        response = self.response_builder.build(
            skill_result.diagnostic_result, request=request,
            memory_snippets=memory_snippets,
        )

        if execution_id or trace_id:
            from dataclasses import replace
            response = replace(response, execution_id=execution_id,
                               trace_id=trace_id)

        if self.knowledge_enabled and self.knowledge_port is not None:
            response = self._attach_knowledge(response, request)

        self._submit_memory(request, response)
        self.history.append("user", request.message)
        self.history.append("agent", response.message)
        return response

    def _retrieve_memory(self, request):
        if self.memory_port is None:
            return []
        try:
            return list(self.memory_port.retrieve(request.message))
        except Exception:  # noqa: BLE001 - memory is context-only, never fatal
            return []

    def _attach_knowledge(self, response, request):
        try:
            snippets = list(self.knowledge_port.retrieve(request.message))
        except Exception:  # noqa: BLE001 - knowledge is optional context
            return response
        citations = tuple(snippets)
        from dataclasses import replace
        return replace(response, citations=tuple(citations))

    def _submit_memory(self, request, response):
        if self.memory_port is None:
            return
        summary = f"{request.message} -> {response.message}"
        try:
            self.memory_port.submit(summary)
        except Exception:  # noqa: BLE001 - async best-effort memory write
            pass

    def _clarification(self, request):
        return AgentResponse(
            response_id=uuid.uuid4().hex,
            session_id=request.session_id,
            response_type=RESPONSE_CLARIFICATION,
            message="请补充要分析的对象（如店铺 / 商品 / 广告）。",
        )

    def _error(self, request, reason):
        return AgentResponse(
            response_id=uuid.uuid4().hex,
            session_id=request.session_id,
            response_type=RESPONSE_ERROR,
            message=f"分析失败：{reason}",
        )


__all__ = ["ConversationManager"]
