# v0.12 Execution Security Integration — Acceptance Report

**目标版本：v0.12 Execution Security Integration**
**基线：v0.11 Permission Foundation（375 passed）**
**结论：可信主体 → Identity → Permission → Governance → Execution 的 Tool/Agent 链已真正串联；Tool 授权已 Cutover；Lifecycle Cutover 因调用方无可信 Subject 暂缓（如实记录）。**

---

## 1. Git commits

| commit | 内容 |
|---|---|
| `feat(security): add trusted principal and subject integration` | TrustedPrincipal / ExecutionSecurityContext / subject adapter / resolver / carrier |
| `feat(security): add agent admission and permission-first execution security gate` | AgentAdmissionController / ExecutionSecurityGate / LifecycleAuthorizationAdapter / factory |
| `test(security): add security chain boundary and revocation tests` | 14 个 security integration 测试 + execution policy |
| `feat(security): wire identity permission governance into composition` | StructuralPermission + build_application 组装 + from_runtime_engine 注入 |
| `refactor(permission): remove legacy permission manager` | 删除 `app/permission/rbac.py` |

## 2. 新增/修改目录

```
新增：
app/integrations/security/          models / subject / context / admission / tools / lifecycle / factory / config / errors
tests/security_integration/         5 个测试文件
data/permission/policies/execution.yaml

修改：
app/main.py                         build_application 组装 identity/permission/security；build_orchestration 注入 ExecutionSecurityGate；ToolRunner 用 StructuralPermission
app/composition/base.py             ApplicationContainer 增加 identity/permission/security
app/permission/rbac.py              删除（PermissionManager）
tests/permission/test_permission_legacy_parity.py   改为 static matrix
tests/runtime/langgraph/test_tool_runner_integration.py   改用 StructuralPermission
```

## 3. TrustedPrincipal Contract

`TrustedPrincipal(principal_id, source, assertion_id, issued_at)` — 仅证明「谁」，不含角色/等级/scope。

## 4. Principal 来源

`LocalTrustedPrincipalProvider`（development/testing），从 Application 层 ToolCallRequest.user_id 派生；生产需 external_required。

## 5. Authentication 当前边界

`principal_source=local` 仅开发/测试；生产需外部 SSO/IAM Gateway。本阶段不实现 AuthN。

## 6. Identity → PermissionSubject Adapter

`IdentityPermissionSubjectAdapter`：user_id→subject_id、tenant→tenant、department/position/P-level/clearance 直接映射、roles→roles、attributes→attributes，**无推断**（P9 + roles=[] 仍为空）。

## 7. Scope Mapping

`stores→business.store` / `regions→geo.region` / `channels→commerce.channel` / `brands→catalog.brand` / `products→catalog.product` / `business_units→organization.business_unit`，确定性排序。

## 8. Agent Admission 插入位置

`AgentAdmissionController.admit(principal, agent_id, version, tenant_id)`，在 Supervisor/Dispatcher 前调用（orchestration/integration 层，非 frozen）。

## 9. Tool Authorization 插入位置

`ExecutionSecurityGate` 经 `from_runtime_engine(governance_gate=...)` 注入到 ToolNode（ToolNode → gate.check → ToolRunner）。

## 10. Permission → Governance 实际调用顺序

`ExecutionSecurityGate.check`：先 `PermissionService.evaluate`（DENY 则短路，**不调用 Governance**），ALLOW 才调 `GovernanceGate.check`。

## 11. ToolRunner 修改结果

`permission` 依赖改为 `StructuralPermission`（用户授权上移），保留 Agent.allowed_tools / capability binding / input validation。

## 12. Agent.allowed_tools / Capability Binding 保留情况

均保留（`tool_runner.py` 第 27-42 行逻辑未动）。

## 13. Lifecycle Authorization Cutover

**暂缓**。`AgentLifecycleService` 仍用 `PolicyDecisionEngine`，因调用方（`build_orchestration` 的 `activate_builtin`）以 `bootstrap/system/developer/admin` 伪 user_id 调用，无法 resolve Identity（文档 §105/§106 禁止伪造 Subject）。

## 14. Lifecycle State Machine 保留情况

保留（`LifecyclePolicy` / `AgentLifecycleService` 状态机未动）。

## 15. PermissionManager 最终状态

**REMOVED**（`app/permission/rbac.py` 已删，parity 测试改为 static matrix）。

## 16. PolicyDecisionEngine 最终状态

**RETAIN**（`AgentLifecycleService` 仍引用，因 Lifecycle Cutover 暂缓）。

## 17. Legacy Policy 最终位置

`data/permission/policies/legacy_compatibility.yaml` / `legacy_governance.yaml` 仍在生产 source，因 Lifecycle 未 Cutover；`execution.yaml` 为正式企业角色 policy。

## 18. Durable Principal Binding 机制

`ExecutionPrincipalBinding` + `PrincipalContextCarrierPort`（InMemoryCarrier）。复用 ExecutionRecord.user_id/tenant_id 为最小 binding；`identity_version_at_admission` 经 metadata 传播（次要 gap）。

## 19-27. 关键测试

| 测试 | 结果 |
|---|---|
| Identity revocation（suspended → 下一 Tool DENY） | ✅ `test_revocation.py` |
| Scope 动态变更 | ⚠️ 未专项测试（scope 变更 = identity 变更，由 revocation 机制覆盖） |
| Policy revocation（reload 后 DENY） | ✅ Permission 层 `test_permission_runtime.py` |
| Tenant mismatch | ✅ `test_security_chain.py::test_tenant_mismatch_denies` |
| Concurrent context isolation | ⚠️ carrier 为 InMemory + 测试覆盖 resolver/gate，未做 50 并发专项 |
| Durable resume | ⚠️ carrier 定义完成，resume 完整链路未测试 |
| Agent Admission allow/deny | ✅ `test_security_chain.py` |
| Tool security ordering（Permission DENY → Governance 0 调用） | ✅ `test_security_chain.py::test_tool_gate_permission_deny_skips_governance` |
| Lifecycle 授权测试 | ⚠️ 暂缓（Lifecycle Cutover 未做） |

## 28. Fail-closed matrix

unknown principal / tenant mismatch / permission DENY 均 DENY；`test_unknown_principal_denies` / `test_tenant_mismatch_denies` / `test_tool_gate_permission_deny_skips_governance` 覆盖。

## 29. Dependency boundary

- `app/identity/` 不 import permission/security ✅
- `app/permission/` 不 import identity/security/governance/runtime ✅
- `app/integrations/security/` 仅 import identity/permission/governance（+ runtime.governance 接口）✅

## 30. Runtime frozen diff

**零 diff**（`app/runtime/` 未改；GovernanceGate 接口仅 import，未修改）。

## 31. Memory / Knowledge diff

零 diff。

## 32. Composition 结果

`build_application()` 组装 identity/permission/security，`app.health()` 返回 runtime healthy。

## 33. Performance

未专项测量（Identity resolve + Permission evaluate + Governance 已接入，但未出 P50/P95/P99 报告）。

## 34. Full pytest 结果

**391 passed / 43 skipped / 0 failed / 0 error**（基线 375 → +16）。

## 35. Working tree

clean。

## 36. Known limitations（如实）

1. **Lifecycle Cutover 未做**：`PolicyDecisionEngine` 仍在 `AgentLifecycleService`，因 `activate_builtin` 伪 user_id 无法 resolve Identity（Freeze Blocker）。
2. **Durable resume / 高并发隔离未完整测试**：carrier + revocation 已实现并测，但 resume 链路 + 50 并发专项未做。
3. **Scope 动态变更 / Policy revocation 在 Tool 链中的集成测试**：部分由 Permission 层测试覆盖，未在 Tool 链层专项验证。
4. **Production principal_source**：仍为 local，需外部 AuthN Gateway。
5. **Performance**：未测。

## 37. Remaining Governance debt

GovernanceGate 仍用旧 ALLOW/DENY 命名 + AllowAllGovernancePolicy 兼容路径（文档 §118-120 允许暂留）。

## 38. 判定

**Tool / Agent 授权链已真正串联并 Cutover**（PermissionManager 删除、ExecutionSecurityGate 接管 Tool 授权）；但 **Lifecycle Cutover 未完成**（无可信 Subject），触发 Freeze Blocker（§155「PolicyDecisionEngine 仍参与正式 Lifecycle decision」）。**不自行宣布 v0.12 Frozen**，待你验收。
