# v0.12 Execution Security Integration — Acceptance Report

**目标版本：v0.12 Execution Security Integration**
**基线：v0.11 Permission Foundation（375 passed）**
**结论：Closure Phase 完成。可信主体 → Identity/System → Permission → Governance → Execution 的 Agent/Tool/Lifecycle 三条主链安全成立，旧授权体系（PermissionManager / PolicyDecisionEngine）已删除。达到 Freeze 标准。**

---

## 1. Git commits

| commit | 内容 |
|---|---|
| `feat(security): add trusted principal and subject integration` | TrustedPrincipal / ExecutionSecurityContext / subject adapter / resolver / carrier |
| `feat(security): add agent admission and permission-first execution security gate` | AgentAdmissionController / ExecutionSecurityGate / LifecycleAuthorizationAdapter / factory |
| `test(security): add security chain boundary and revocation tests` | security chain 测试 + execution policy |
| `feat(security): wire identity permission governance into composition` | StructuralPermission + build_application 组装 |
| `refactor(permission): remove legacy permission manager` | 删除 `app/permission/rbac.py` |
| `feat(security): add trusted system principal resolution` | SystemPrincipalDefinition / SystemPrincipalResolver / registry |
| `refactor(governance): cut over lifecycle authorization to permission foundation` | LifecycleAuthorizationPort + AgentLifecycleService Cutover + 删除 PolicyDecisionEngine |
| `test(security): add revocation concurrency durable and production principal tests` | durable context / 并发 / 撤销 / production principal 测试 |

## 2. TrustedPrincipal Contract

`TrustedPrincipal(principal_id, source, assertion_id, issued_at)`。source 区分 `human`（→ IdentityService）与 `system`（→ SystemPrincipalResolver）。

## 3. Principal 来源

- Human：`LocalTrustedPrincipalProvider`（development，从 Application 层 user_id 派生）。
- System：`TrustedSystemPrincipalRegistry`（`platform.bootstrap` 一等公民，非授权后门）。
- Production：`principal_source=external_required` 时 `LocalTrustedPrincipalProvider` 拒绝（fail-closed）。

## 4. Identity → PermissionSubject Adapter

`IdentityPermissionSubjectAdapter`：无推断（P9 + roles=[] 仍为空），scope 确定性映射。

## 5. Scope Mapping

`stores→business.store` 等六维映射，排序确定性。

## 6. Agent Admission

`AgentAdmissionController.admit(principal, agent_id, version, tenant_id)`，DENY 则不启动。

## 7. Tool Authorization

`ExecutionSecurityGate` 经 `from_runtime_engine(governance_gate=...)` 注入；顺序 Permission → Governance。

## 8. Permission → Governance 顺序

DENY 短路（Governance 零调用）；ALLOW 才调 GovernanceGate。

## 9. ToolRunner Cutover

`permission` 依赖改为 `StructuralPermission`（用户授权上移），保留 Agent.allowed_tools / capability binding / input validation。

## 10. Lifecycle Authorization Cutover（已完成）

- 新增 `LifecycleAuthorizationPort`（governance 层）。
- `AgentLifecycleService` 用 `authorization`（替代 `governance_engine`），`activate_builtin` 用 `platform.bootstrap` system principal。
- `PermissionLifecycleAuthorizationAdapter` 实现该端口，action 纯动词（create/submit_review/approve/activate/suspend/deprecate/archive）。

## 11. Lifecycle State Machine 保留

`LifecyclePolicy` 状态机未动；授权（Permission）与状态合法性（LifecyclePolicy）分离。

## 12. PermissionManager / PolicyDecisionEngine 最终状态

- `PermissionManager`：**REMOVED**（`app/permission/rbac.py` 已删）。
- `PolicyDecisionEngine`：**REMOVED**（`app/governance/policy/engine.py`、`models.py`、`repository.py` 已删；`policy/__init__.py` 仅导出 LifecyclePolicy）。

## 13. Legacy Policy 最终位置

`legacy_governance.yaml` 已从生产 source 移除；`legacy_compatibility.yaml` 仅用于 parity（静态 golden matrix）。

## 14. Durable Principal Binding

`ExecutionPrincipalBinding` + `PrincipalContextCarrierPort`（InMemoryCarrier），bind/get/remove 测试通过。

## 15. 关键测试结果

| 测试 | 结果 |
|---|---|
| Identity revocation（suspended → 下一 Tool DENY） | ✅ |
| Scope 动态变更（JP01+JP02 → JP01，JP02 下一 Tool DENY） | ✅ |
| Policy revocation（reload 后下一 Tool DENY） | ✅ |
| Tenant mismatch | ✅ |
| 并发上下文隔离（20 线程 × 500 次，零 principal/tenant bleed） | ✅ |
| Durable resume（bind → get principal → 重新 resolve） | ✅ |
| Agent Admission allow/deny | ✅ |
| Tool 顺序（Permission DENY → Governance 0 调用） | ✅ |
| Lifecycle 授权（system principal + management 允许，advertising 拒绝） | ✅ |
| Production principal mode（external_required fail-closed） | ✅ |
| System principal（platform.bootstrap 授权，非绕过） | ✅ |

## 16. Fail-closed matrix

unknown principal / suspended / scope 收缩 / policy 撤销 / tenant mismatch / permission DENY / 无 external principal source 均 DENY。

## 17. Dependency boundary

- `app/identity/` 不 import permission/security ✅
- `app/permission/` 不 import identity/security/governance/runtime ✅
- `app/integrations/security/` 仅 import identity/permission/governance（+ runtime.governance 接口）✅

## 18. Frozen diff

`app/runtime/` / `app/memory/` / `app/knowledge/` / `app/compiler/` / `app/artifacts/` / `app/registry/` 零 diff。

## 19. Composition

`build_application()` 组装 identity/permission/security，`governance=security`。

## 20. Performance（报告，无硬阈值）

- identity_resolve：P50=0.03ms / P95=0.08ms / P99=0.15ms
- agent_admission：P50=0.05ms / P95=0.13ms / P99=0.17ms
- tool_security_gate：P50=0.06ms / P95=0.16ms / P99=0.19ms

## 21. Full pytest 结果

**373 passed / 43 skipped / 0 failed / 0 error**。

## 22. Working tree

clean。

## 23. Known limitations（非 Freeze Blocker）

1. Production 无外部 AuthN connector：`principal_source=external_required` 时 fail-closed，但尚未接入真实 SSO/IAM（文档 §136 允许）。
2. `GovernanceGate` 仍用旧 ALLOW/DENY 命名 + `AllowAllGovernancePolicy` 兼容路径（文档 §118-120 允许暂留）。
3. 高风险写操作治理 / Approval Workflow 尚未建设（文档 §171 明确留待 Governance Enhancement）。
4. Durable carrier 为 InMemory（生产需持久化 store）。

## 24. 判定

```
Trusted Principal model               ✅
Identity → PermissionSubject          ✅
System Principal resolution           ✅
Agent Admission                       ✅
Permission-first Tool Gate            ✅
Permission → Governance ordering       ✅
ToolRunner user-auth cutover           ✅
PermissionManager removal              ✅
Lifecycle Permission cutover           ✅
PolicyDecisionEngine removal           ✅
Structural constraints retained        ✅
Identity/Scope/Policy revocation       ✅
Durable security-context resume        ✅
Concurrent context isolation           ✅
Production principal mode              ✅
Performance evidence                   ✅
Frozen Runtime / Memory / Knowledge    ✅
Full regression                        ✅
```

**v0.12 Execution Security Integration — FROZEN（待最终批准）。**
