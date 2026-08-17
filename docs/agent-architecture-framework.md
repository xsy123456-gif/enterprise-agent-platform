# Enterprise Agent Platform — 完整 Agent 结构框架文档

> 版本：v1.0　·　状态：Phase 0–17 完成后冻结　·　目标：确定后续推进方向

---

## 1. 文档目的

本文件沉淀整个平台（Phase 0–17）的**分层架构框架**，明确每一层的职责、模块、数据流与边界约束，作为后续演进（Phase 18+）的路线图依据。

核心结论一句话：

> 平台已从「单业务域 Agent 应用平台」演进为「**企业 AI 自优化运营平台**」，
> 每一层都遵循「**职责分离 + 版本化 + 治理 + 可审计**」四条铁律。

---

## 2. 演进全景（Phase → 架构层）

| 阶段 | 交付 | 落位架构层 |
|------|------|-----------|
| Phase 0–5 | Runtime / Execution / Governance / Identity / Permission / Memory / Knowledge | **Foundation 内核** |
| Phase 6–10 | Commerce Canonical Model / Repository / Ingestion / Diagnostic Kernel / Plan / Skill / Tool | **Commerce Domain + Intelligence** |
| Phase 11 | ReviewInsight Intelligence Worker | Commerce Intelligence（证据层） |
| Phase 12 | Employee Agent Runtime | **Employee Agent 运行时** |
| Phase 12.9 | Real Commerce Integration（Amazon/TikTok + Credential） | Commerce Integration 边界 |
| Phase 13 | Agent Control Plane | **Agent OS 控制面** |
| Phase 14 | Multi-Agent Collaboration Runtime | **Agent OS 协作面** |
| Phase 15 | Production Platform（Observability/Reliability/Tenant/Cost/Knowledge/Marketplace） | **生产运营层** |
| Phase 16 | Business Expansion（Package/Workflow/Approval/Action/ERP-CRM/Subscription） | **业务执行层** |
| Phase 17 | Intelligence Optimization（Evaluation/Optimization/Experiment/Feedback/Governance） | **智能优化层** |

---

## 3. 六层架构总览

```
                         Enterprise User
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│  L7  智能优化层  intelligence/                                │
│      评估 → 优化建议 → 治理 → 审批 → 改进 → 实验 → 发布        │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│  L6  业务执行层  business/                                    │
│      Package / Workflow / Approval / Action / ERP-CRM / 订阅  │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│  L5  生产运营层  production/                                  │
│      Observability / Reliability / Tenant / Cost / Knowledge │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│  L4  Agent 操作系统  agent_control/ + agent_collaboration/    │
│      Registry / Lifecycle / Deployment / Governance / Router │
│      + Multi-Agent Orchestrator / Delegation / Aggregation   │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│  L3  员工 Agent 运行时  commerce/agents/                      │
│      Agent → Skill Router → Skill → Plan → Tool              │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│  L2  Commerce Domain + Intelligence                          │
│      Canonical / Repository / Diagnostic Kernel / Skill /    │
│      ReviewInsight / Integration                             │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│  L1  Foundation 内核（Platform Kernel）                       │
│      Runtime / Execution / Governance / Identity / Permission│
│      Memory / Knowledge / LLM / Tool / Registry              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. L1 — Foundation 内核（不可变底座）

**定位**：平台唯一可信的执行与安全内核。上层任何层都不得修改。

| 模块 | 职责 | 关键组件 |
|------|------|---------|
| `app/runtime/` | 执行运行时（LangGraph 后端、checkpoint、worker） | `ToolRunner`, `AsyncTraceConsumer` |
| `app/execution/` | 持久化执行 | 执行生命周期 |
| `app/governance/` | 治理内核（Gate、策略、approval） | `GovernanceGate`, `AllowAllGovernancePolicy` |
| `app/identity/` | 身份与租户 | `IdentityService` |
| `app/permission/` | 权限模型与策略 | `PermissionSubject`, `PermissionScope` |
| `app/memory/` | 记忆平台（读写流水线 + 向量） | `MemoryService`（retrieve/submit） |
| `app/knowledge/` | 知识平台（ACL/检索/引证） | `KnowledgeService` |
| `app/llm/` | LLM 抽象与 Provider | provider 适配 |
| `app/tools/` | 工具框架 | `BaseTool` |
| `app/registry/` | 全局注册中心 | `ToolRegistry`, `ToolBinding` |
| `app/events/` | 事件总线 | `EventBus` |
| `app/compiler/` | Agent 编译（manifest → IR） | `Compiler` |
| `app/composition/` | 组合根（dev/prod/test） | `build_composition` |

**边界**：上层（L2–L7）只能通过公开端口消费；禁止修改内核（`app/runtime`、`app/execution`、`app/governance`、`app/compiler`、`app/skills`、`app/diagnostics/kernel`、`app/tools` 已冻结）。

---

## 5. L2 — Commerce Domain + Intelligence

**定位**：业务唯一语言（Canonical Model）+ 确定性诊断智能。

### 5.1 Canonical Model（`app/commerce/domain/`）

`Store / Product / SKU / Listing / ListingItem / InventorySnapshot / Campaign / AdGroup / Ad / AdPromotedItem / Keyword / SearchTerm / Review / ReviewInsight / MetricSeries`

### 5.2 Repository（`app/commerce/repositories/`）

- `CommerceRepository` 端口（tenant 隔离、幂等 upsert、append-only 库存）
- `ExternalIdentityMap`（外部 ID ↔ canonical ID 唯一映射）
- InMemory + PostgreSQL（schema 版本化 + 迁移）

### 5.3 Ingestion（`app/commerce/ingestion/`）

`ConnectorPort → RawLanding → AdapterPort → CanonicalMutation → Staging → PublishManager → EventBus`，含 `SyncCoordinator`（fetch→map→stage→publish→watermark）。

### 5.4 Diagnostic Kernel（`app/commerce/diagnostics/`）

确定性诊断：`MetricEngine / AnomalyEngine / TrendEngine / ContributionEngine / ImpactEngine / RuleEngine / PriorityEngine`。产出 `Signal → Evidence → Cause → Impact → Priority`。**LLM 从不参与归因**。

### 5.5 Plan + Skill（`app/commerce/diagnostics/plans/` + `app/commerce/skills/`）

- `DiagnosticPlan`（编译为 IR，`PlanExecutor` 执行）
- `Skill`（版本化业务能力，绑定 Plan），`SkillSystem` 组合根

### 5.6 Tool（`app/commerce/tools/` + `app/commerce/platform/`）

7 个受控读工具（`store.get / catalog.query / metric.query / inventory.query / review.query / review_insight.query / advertising.query`），`Capability → ToolBinding → ToolRunner → Tool`，STRICT scope。

### 5.7 ReviewInsight（`app/commerce/review_insight/`）

事件驱动的 AI 证据层：`ReviewAvailableEvent → Worker → Extractor → Service → Repository`，自然键幂等（`tenant+review+extractor+version`），Provider 永不产出 `ReviewInsight`，`EvidenceAdapter` 只供证据不诊断。

### 5.8 Integration（`app/commerce/integration/`）

`Connector(transport) → Adapter(映射) → Canonical`；Credential 边界（`SecretReference`，无明文 token）；版本化 Connector/Adapter Registry；复用 Phase 7 `SyncCoordinator`。

---

## 6. L3 — Employee Agent Runtime（`app/commerce/agents/`）

**定位**：面向员工的单业务域 Agent。**Agent 是业务入口，不是执行引擎。**

```
User message → ConversationManager
    → Skill Router（Rule → Entity → LLM，LLM 仅输出候选 skill）
    → SkillSystem.run → Plan → Tool → DiagnosticResult
    → ResponseBuilder（LLM 仅润色，不重新归因）
    → Memory.submit（异步）
```

| 模块 | 职责 |
|------|------|
| `domain.py` | `AgentDefinition / AgentSession / AgentRequest / AgentResponse`（禁止 prompt/tools/permissions/身份字段） |
| `manifest.py` | `AgentManifest`（skills/default_skill/capabilities） |
| `registry.py` / `lifecycle.py` | 版本化 + 生命周期（DRAFT→VALIDATED→ACTIVE） |
| `binding.py` | `AgentSkillBinding`（Agent 只能经 binding 触达 Skill） |
| `router/` | 三层路由（Rule/Entity/LLM） |
| `conversation/` | `ConversationManager` + `History` |
| `response/` | `ResponseBuilder` |
| `context.py` | `AgentMemoryPort` / `AgentKnowledgePort` / `AgentContext` |

---

## 7. L4 — Agent Operating System

### 7.1 Control Plane（`app/platform/agent_control/`）

多 Agent 企业化：`AgentArtifact`（checksum 内容寻址）+ `AgentRegistry`（版本化生命周期）+ `DeploymentManager`（DEV/TEST/PROD）+ `AgentAccessPolicy`（user/role/department，fail-closed）+ `EnterpriseAgentRouter` + `AgentMessageProtocol`（协作契约）+ `AgentEvaluation` + 审计。

### 7.2 Collaboration Runtime（`app/platform/agent_collaboration/`）

```
Enterprise Router → Multi-Agent Orchestrator
    → AgentTaskGraph(DAG) → DelegationExecutor(治理+委派)
    → 各 Agent → ResultAggregator + ConflictResolver（证据优先）
```

`AgentContextEnvelope`（受控上下文，禁 tenant/permission/credential）、`CollaborationAccessControl`（source→target 策略）、`CollaborationEvaluation` + 审计。

---

## 8. L5 — Production Platform（`app/platform/production/`）

**定位**：生产运营，不改变 Agent 逻辑、不参与业务判断。

| 子模块 | 职责 |
|--------|------|
| `observability/` | `AgentTrace`+`ExecutionSpan`（agent/skill/plan/tool/llm）、`AgentMetricsCollector`、`AgentSLA`、`CostCollector`（禁 secret） |
| `reliability/` | `RetryPolicy`（可重试分类）、`run_with_timeout`、`CircuitBreaker`（CLOSED/OPEN/HALF_OPEN）、`RecoveryManager`（checkpoint/fallback/升级） |
| `tenant/` | `Tenant`（ACTIVE/SUSPENDED/DISABLED）、`TenantIsolation`（fail-closed）、`TenantQuota` |
| `governance/` | `AgentBudgetPolicy` + `BudgetManager`（daily/monthly 桶 + hard_stop） |
| `knowledge/` | `KnowledgeDocument`（checksum+版本）、`KnowledgeAccessControl`、`KnowledgeIngestionService` |
| `marketplace/` | `AgentCatalog` + `AgentPublisher`（SUBMITTED→REVIEW→APPROVED→PUBLISHED） |

---

## 9. L6 — Business Execution Layer（`app/platform/business/`）

**定位**：从「分析」到「执行」。**Analysis 与 Action 严格分离**。

| 子模块 | 职责 |
|--------|------|
| `package/` | `AgentPackage`（Agent+Skill+Plan+Knowledge+Workflow+Integration + checksum）、governed install |
| `approval/` | `ApprovalEngine`（分级审批 / auto-approve / fail-closed） |
| `action/` | `ActionProposal`（Agent 只建议）→ `BusinessActionRuntime`（validate→permission→approval→execute→audit） |
| `workflow/` | `BusinessWorkflow`（6 类 step）→ `WorkflowEngine`（DAG，复用 Runtime） |
| `integration/` | `Salesforce/SAP/NetSuite` connector（domain tag，领域隔离） |
| `commercial/` | `TenantSubscription`（FREE/PRO/ENTERPRISE）+ `EntitlementManager` + `UsageMetering` |

---

## 10. L7 — Intelligence Optimization Layer（`app/platform/intelligence/`）

**定位**：让 Agent 基于生产数据持续演进。**Agent 不自主修改自己**。

```
构建 → 运行 → 治理 → 执行 → 评估 → 优化 → 演进（闭环）
```

| 子模块 | 职责 |
|--------|------|
| `evaluation/` | `EvaluationEngine`（execution/business/user/safety 四类，数据驱动）+ 版本化 metric registry |
| `optimization/` | `PatternDetector`（性能/成本/反馈）+ `OptimizationGenerator`（LLM 仅出 candidate_change） |
| `improvement/` | `ImprovementLifecycle`（CREATED→…→RELEASED/ROLLED_BACK）+ 人工审批 |
| `experiment/` | `AgentExperiment`（SHADOW/AB_TEST/CANARY）+ `TrafficAssignment` + `ExperimentEvaluator` |
| `feedback/` | `FeedbackProcessor`（负反馈→优化信号） |
| `governance/` | `OptimizationGovernance`（LOW 自动 / MEDIUM 审批 / HIGH 禁止） |

---

## 11. 关键数据流

### 11.1 请求流（用户 → 响应）

```
User → L3 Router → Skill → Plan → L1 ToolRunner → L2 Tool → Repository
     → DiagnosticResult → ResponseBuilder → Employee Response
```

### 11.2 诊断归因流（确定性）

```
Tool facts → L2 Plan → Diagnostic Kernel（Signal→Evidence→Cause→Impact→Priority）
     （LLM 不参与归因）
```

### 11.3 业务执行流（受控）

```
Agent ActionProposal → L6 ActionRuntime → Approval → Connector → 外部系统 → Audit
```

### 11.4 协作流（多 Agent）

```
Enterprise Router → L4 Orchestrator → DAG → Delegation(治理) → 各 Agent
     → Aggregator(冲突证据优先) → 响应
```

### 11.5 优化闭环流

```
L5 Observability → L7 Evaluation → Optimization Proposal → Governance
     → Approval → Improvement → Experiment → Release → 重复
```

---

## 12. 跨层核心设计原则（铁律）

1. **职责分离** — 每层只做一件事；Agent≠引擎、Connector≠业务、Observability≠归因。
2. **Analysis / Action 分离** — Agent 只建议，Action Runtime 才执行。
3. **Agent 不自主修改自己** — 优化必须经评估→建议→治理→审批→版本→发布。
4. **LLM 边界** — LLM 只做理解/表达/建议文本，永不越权（工具/权限/数据库/计划/归因）。
5. **版本化一切** — Agent/Skill/Plan/Prompt/Knowledge/Connector 全版本化，可 replay。
6. **治理 fail-closed** — 无匹配策略即拒绝（权限/预算/知识/优化）。
7. **Tenant Isolation First** — 数据/资源/权限/成本四维隔离。
8. **Failure Must Be Visible** — 禁止 `except: pass`，失败必进审计/升级。
9. **数据驱动 > LLM 猜测** — 优化/评估基于 Trace/Metric/Feedback，而非「我觉得」。

---

## 13. 当前能力矩阵

| 能力 | 状态 | 落位 |
|------|------|------|
| 创建/管理/发布 Agent | ✅ | L4 |
| Agent 生命周期/版本/部署 | ✅ | L4 |
| 多 Agent 协作/委派/聚合 | ✅ | L4 |
| 确定性诊断（Signal/Cause/Impact/Priority） | ✅ | L2 |
| 受控读写工具（STRICT scope） | ✅ | L2 |
| 外部系统接入（Amazon/TikTok/ERP/CRM） | ✅ | L2/L6 |
| 生产可观测/可靠/计费/隔离 | ✅ | L5 |
| 业务执行（Workflow/Approval/Action） | ✅ | L6 |
| 持续评估/优化/实验/反馈 | ✅ | L7 |

---

## 14. 后续推进方向（Phase 18+ 候选路线）

按「补短板 → 深场景 → 扩生态」排序：

### 方向 A：领域横向扩展（多业务域）
- 将 Commerce 的成功复制到 **Sales / Finance / CRM / HR** 域，建立 Finance Domain、CRM Domain（Phase 16.5 已预留领域隔离）。
- 落地「领域 Agent 通过 Collaboration 通信」的多域联邦。

### 方向 B：真实连接器落地（当前多为 fake/stub）
- Amazon SP-API / TikTok Shop / Shopify / Salesforce / SAP 的**真实 HTTP + 认证 + 分页 + 限流**实现。
- Credential 对接真实 Secret Provider（Vault/AWS SM/KMS）。

### 方向 C：生产基建深化
- 可观测性接 OpenTelemetry；PostgreSQL 迁移补全（当前 15 个 Postgres 集成测试覆盖 Commerce，可扩展到 Control Plane/Production 的持久化）。
- 真正的 SaaS 多租户路由/计费/配额记账。

### 方向 D：智能优化闭环做实
- 将 L7 的评估/实验接入 L5 的 Trace/Metrics（真实执行数据回流），形成在线 A/B + 自动回滚。
- Feedback 采集 UI + 人工修正标注闭环。

### 方向 E：治理与安全补强
- Agent 级最小权限（least privilege）与执行隔离沙箱。
- 跨租户审计与合规（SOC2/GDPR 痕迹）。

### 方向 F：开发者体验与生态
- Agent/Skill/Package 的 manifest 脚手架与 CLI。
- Marketplace 发布/安装的真实运行时（当前为状态机骨架）。

**建议优先级**：B（真实连接）→ C（生产基建）→ A（多域）→ D（优化闭环）→ E/F。

---

## 附：模块速查索引

- 内核：`app/runtime app/execution app/governance app/identity app/permission app/memory app/knowledge app/llm app/tools app/events app/compiler`
- 业务+智能：`app/commerce/domain app/commerce/repositories app/commerce/ingestion app/commerce/diagnostics app/commerce/skills app/commerce/tools app/commerce/review_insight app/commerce/integration`
- Agent 运行时：`app/commerce/agents`
- Agent OS：`app/platform/agent_control app/platform/agent_collaboration`
- 生产运营：`app/platform/production`
- 业务执行：`app/platform/business`
- 智能优化：`app/platform/intelligence`

累计 196 commits，全量回归 1099 passed / 58 skipped / 0 failed，Commerce PostgreSQL 集成 15 passed。
