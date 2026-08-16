"""Unified enterprise composition root (Phase 18.1).

One standard entrypoint that composes ALL subsystems (Foundation + Commerce +
Employee Agent + Control Plane + Collaboration + Production + Business +
Intelligence) into a single ``EnterpriseApplication``.  This is *composition
only* — it adds no new platform layer and no new execution engine.
"""

import os
from dataclasses import dataclass, field
from types import SimpleNamespace

from app.main import build_application


@dataclass
class EnterpriseApplication:
    foundation: object = None
    commerce: object = None
    agents: object = None
    control_plane: object = None
    collaboration: object = None
    production: object = None
    business: object = None
    intelligence: object = None
    environment: str = "development"

    def start(self):
        self.foundation.start()
        return self

    def stop(self, timeout=None):
        self.foundation.stop(timeout)
        return self

    @property
    def started(self):
        return self.foundation.started

    def health(self):
        return self.foundation.health()


def _build_commerce(environment, execution_manager=None):
    from app.commerce.query.service import CommerceQueryService
    from app.commerce.repositories.factory import (
        build_identity_map,
        build_repository,
    )
    from app.commerce.diagnostics import build_core_metric_registry
    from app.commerce.platform import build_commerce_tool_surface
    from app.commerce.skills import (
        DiagnosticSkillExecutionAdapter,
        build_skill_system,
    )

    url = os.getenv("COMMERCE_DATABASE_URL")
    repository = build_repository(url, initialize=bool(url))
    identity_map = build_identity_map(url)
    query_service = CommerceQueryService(repository, identity_map=identity_map)
    metric_registry = build_core_metric_registry()
    skill_system = build_skill_system()
    tool_surface = build_commerce_tool_surface(
        query_service, metric_registry=metric_registry,
    )
    skill_execution = DiagnosticSkillExecutionAdapter(
        skill_system, execution_manager=execution_manager,
    )
    return SimpleNamespace(
        repository=repository,
        identity_map=identity_map,
        query_service=query_service,
        metric_registry=metric_registry,
        skill_system=skill_system,
        tool_surface=tool_surface,
        skill_execution=skill_execution,
        execution_manager=execution_manager,
    )


def _build_employee_agents(skill_system):
    from app.commerce.agents import (
        AgentDefinition,
        AgentManifest,
        AgentSkillBinding,
        build_employee_agent_runtime,
    )
    from app.commerce.contracts.subject import SUBJECT_STORE, SubjectRef

    manifest = AgentManifest(
        agent_id="commerce_operations_agent", version="1.0",
        description="AI assistant for ecommerce operators",
        skills=(
            "store_performance_diagnosis", "product_performance_diagnosis",
            "advertising_performance_diagnosis", "inventory_risk_diagnosis",
            "review_issue_diagnosis", "product_360_diagnosis",
            "daily_operations_triage",
        ),
        default_skill="daily_operations_triage",
        required_capabilities=(
            "commerce.store.read", "commerce.catalog.read",
            "commerce.metrics.read", "commerce.inventory.read",
            "commerce.review.read", "commerce.review_insight.read",
            "commerce.advertising.read",
        ),
    )
    definition = AgentDefinition(
        agent_id="commerce_operations_agent", version="1.0",
        name="Commerce Operations Employee", description="电商运营智能员工",
        domain="commerce",
    )
    bindings = [
        AgentSkillBinding(
            agent_id="commerce_operations_agent", skill_id="store_performance_diagnosis",
            skill_version="1.0", priority=80,
            routing_examples=("销量", "GMV", "转化率", "巡检")),
        AgentSkillBinding(
            agent_id="commerce_operations_agent",
            skill_id="advertising_performance_diagnosis", skill_version="1.0",
            priority=90, routing_examples=("广告", "ROAS", "ACOS")),
        AgentSkillBinding(
            agent_id="commerce_operations_agent", skill_id="inventory_risk_diagnosis",
            skill_version="1.0", priority=70,
            routing_examples=("库存", "缺货", "滞销")),
        AgentSkillBinding(
            agent_id="commerce_operations_agent", skill_id="review_issue_diagnosis",
            skill_version="1.0", priority=60,
            routing_examples=("评价", "评分", "差评")),
        AgentSkillBinding(
            agent_id="commerce_operations_agent", skill_id="product_360_diagnosis",
            skill_version="1.0", priority=50,
            routing_examples=("商品360", "综合分析")),
        AgentSkillBinding(
            agent_id="commerce_operations_agent", skill_id="product_performance_diagnosis",
            skill_version="1.0", priority=65,
            routing_examples=("商品", "SKU")),
        AgentSkillBinding(
            agent_id="commerce_operations_agent", skill_id="daily_operations_triage",
            skill_version="1.0", priority=100,
            routing_examples=("日报", "今日", "待办")),
    ]
    runtime = build_employee_agent_runtime(
        definition, manifest, skill_system, bindings,
        known_subjects={"JP01": SubjectRef(SUBJECT_STORE, "JP01")},
    )
    return SimpleNamespace(definition=definition, manifest=manifest,
                           bindings=tuple(bindings), runtime=runtime)


def _build_control_plane():
    from app.platform.agent_control import (
        AgentAccessControl,
        AgentRegistry,
        DeploymentManager,
        EnterpriseAgentRouter,
        RuleRouter,
    )
    registry = AgentRegistry()
    deployment = DeploymentManager(registry)
    access_control = AgentAccessControl()
    router = EnterpriseAgentRouter(rule_router=RuleRouter())
    return SimpleNamespace(registry=registry, deployment=deployment,
                           access_control=access_control, router=router)


def _build_collaboration():
    from app.platform.agent_collaboration import (
        AgentResultAggregator,
        CollaborationAccessControl,
        DelegationExecutor,
        GraphValidator,
        MultiAgentOrchestrator,
    )
    access_control = CollaborationAccessControl()
    delegator = DelegationExecutor(agent_runner=lambda a, g, c: {},
                                   access_control=access_control)
    orchestrator = MultiAgentOrchestrator(delegator)
    aggregator = AgentResultAggregator()
    validator = GraphValidator()
    return SimpleNamespace(access_control=access_control, delegator=delegator,
                           orchestrator=orchestrator, aggregator=aggregator,
                           graph_validator=validator)


def _build_production():
    from app.platform.production import (
        AgentMetricsCollector,
        BudgetManager,
        CostCollector,
        KnowledgeIngestionService,
        QuotaManager,
        TenantIsolation,
        TraceCollector,
    )
    return SimpleNamespace(
        trace=TraceCollector(),
        metrics=AgentMetricsCollector(),
        cost=CostCollector(),
        budget=BudgetManager(),
        quota=QuotaManager(),
        tenant_isolation=TenantIsolation(),
        knowledge=KnowledgeIngestionService(),
    )


def _build_business():
    from app.platform.business import (
        ApprovalEngine,
        BusinessActionRuntime,
        PackageRegistry,
        WorkflowEngine,
    )
    return SimpleNamespace(
        packages=PackageRegistry(),
        approval=ApprovalEngine(),
        action_runtime=BusinessActionRuntime(),
        workflow_engine=WorkflowEngine(),
    )


def _build_intelligence():
    from app.platform.intelligence import (
        EvaluationEngine,
        ExperimentEvaluator,
        FeedbackProcessor,
        ImprovementLifecycle,
        OptimizationGenerator,
        OptimizationGovernance,
        PatternDetector,
    )
    return SimpleNamespace(
        evaluation=EvaluationEngine(),
        detector=PatternDetector(),
        generator=OptimizationGenerator(),
        lifecycle=ImprovementLifecycle(),
        experiment_evaluator=ExperimentEvaluator(),
        feedback=FeedbackProcessor(),
        governance=OptimizationGovernance(),
    )


def build_enterprise_application(environment=None, **overrides):
    environment = (environment or os.getenv("APP_ENV", "development")).lower()
    foundation = build_application(environment=environment, **overrides)
    if environment == "production":
        _validate_production_security(foundation)
    execution_manager = foundation.execution or _inmemory_execution_manager(
        foundation.event_bus,
    )
    commerce = _build_commerce(environment, execution_manager=execution_manager)
    skill_system = commerce.skill_system
    return EnterpriseApplication(
        foundation=foundation,
        commerce=commerce,
        agents=_build_employee_agents(skill_system),
        control_plane=_build_control_plane(),
        collaboration=_build_collaboration(),
        production=_build_production(),
        business=_build_business(),
        intelligence=_build_intelligence(),
        environment=environment,
    )


def _validate_production_security(foundation):
    from app.composition.security import (
        PRINCIPAL_LOCAL,
        SecurityConfigValidator,
    )
    governance = getattr(foundation, "governance", None)
    gate = getattr(governance, "tool_gate", None)
    policy = getattr(gate, "policy", None)
    memory = getattr(foundation, "memory", None)
    memory_auth = getattr(memory, "authorization_provider", None)
    SecurityConfigValidator(
        environment="production",
        governance_policy=policy,
        memory_authorization=memory_auth,
        principal_source=PRINCIPAL_LOCAL,
    ).assert_secure()


def _inmemory_execution_manager(event_bus=None):
    from app.runtime.execution import ExecutionManager, InMemoryExecutionStore
    return ExecutionManager(InMemoryExecutionStore(), event_bus=event_bus)


__all__ = ["EnterpriseApplication", "build_enterprise_application"]
