# v0.11 Permission Foundation — Acceptance Report

**版本：v0.11 Permission Foundation**
**基线：v0.10 Identity Foundation Frozen**
**结论：Permission 黑盒本体完整可靠，语义迁移 + parity 达标；按 §150 Freeze Blocker，不自行宣布 Frozen，待最终验收。**

---

## 1. Git commits

| commit | 内容 |
|---|---|
| `feat(permission): add permission contracts and policy models` | models + policy（parser/canonical/snapshot） |
| `feat(permission): add policy validation and deterministic native evaluator` | validation + evaluation（四态）+ runtime + errors + config |
| `feat(permission): add local policy provider and permission service` | providers + ports + api/service + factory |
| `test(permission): add enterprise RBAC and ABAC policy fixtures` | `data/permission/policies/*.yaml` |
| `test(permission): add fail-closed determinism and legacy parity suite` | 5 个测试文件 |
| `test(permission): add runtime lifecycle and governance parity conformance` | runtime 测试 + governance parity |

## 2. 新增/修改目录

```
app/permission/
├── api/service.py              PermissionService.evaluate()
├── models/                     subject/scope/resource/environment/request/decision/
│                               condition/policy/snapshot
├── policy/                     parser / canonical / snapshot
├── ports/                      policy_provider / evaluator
├── providers/local_file.py     LocalFilePolicyProvider
├── evaluation/                 native / field_resolver / operators / combiner
├── validation/                 request_validator / policy_validator
├── config.py / errors.py / runtime.py / factory.py
data/permission/policies/       platform/operations/advertising/management/
                                legacy_compatibility/legacy_governance
tests/permission/               7 个测试文件
```

## 3. Permission Contract（已冻结）

- `PermissionSubject`：subject_id / tenant_id / roles / department_id / position_id / professional_level / security_clearance / scopes / attributes。
- `PermissionScope = ScopeGrant[]`（dimension + values，不绑定业务维度）。
- `PermissionResource`：resource_type / resource_id / tenant_id / attributes（resource_type 为 opaque 标识符）。
- `PermissionRequest`：request_id / subject / resource / action / environment（immutable fact snapshot）。
- `PermissionDecision`：decision(ALLOW|DENY) / decision_id / request_id / reason_code / matched_policy_refs / policy_set_version。
- `PolicyReference`：policy_id + version。

## 4. Policy Schema

- `PermissionPolicy`：policy_id / version / status(active|disabled) / scope(platform|tenant) / effect(allow|deny) / target / condition。
- `PolicyTarget`：resource_types + resource_match(any|ids) + actions。
- Condition AST：AtomicCondition + all/any/not。

## 5. Operator List

`equals not_equals in not_in contains contains_any contains_all gt gte lt lte gte_level lte_level exists not_exists scope_contains`（16 个）。

## 6. 四态 Semantics

- 四态：TRUE / FALSE / UNKNOWN / ERROR。
- Missing Fact（None / MISSING）→ UNKNOWN，不产生错误 ALLOW。
- `NOT UNKNOWN = UNKNOWN`、`NOT ERROR = ERROR`。
- `ALL`：ERROR > FALSE > UNKNOWN > TRUE；`ANY`：ERROR > TRUE > UNKNOWN > FALSE。
- 不短路隐藏 ERROR。

## 7. Effect Combination

`ERROR > explicit DENY > indeterminate DENY > explicit ALLOW > indeterminate ALLOW(→DENY) > no match`。

## 8. Tenant Isolation

`subject.tenant_id ≠ resource.tenant_id` → `DENY_TENANT_MISMATCH`，在普通 Policy 评估前短路。

## 9. Policy Snapshot 生命周期（核验项）

| 项 | 结果 | 测试 |
|---|---|---|
| atomic reload | ✅ `reload()` 成功才替换 snapshot | `test_permission_runtime.py::test_atomic_reload_replaces_snapshot` |
| invalid reload 保留 last valid + degraded | ✅ 失败保留旧 snapshot，health=degraded | `test_invalid_reload_keeps_last_valid_snapshot` |
| 并发 evaluate/reload 一致性 | ✅ 每个 evaluate 用完整 snapshot 版本 | `test_concurrent_evaluation_and_reload_snapshot_consistency` |
| health 三态 | ✅ unhealthy / healthy / degraded | `test_health_states` |

## 10. policy_set_version 确定性（核验项）

| 项 | 结果 | 测试 |
|---|---|---|
| policy 加载顺序无关 | ✅ | `test_policy_set_version_independent_of_load_order` |
| YAML key 顺序无关 | ✅ | `test_policy_set_version_independent_of_yaml_key_order` |
| file 顺序无关 | ✅（provider 排序加载 + snapshot 排序） | `LocalFilePolicyProvider.load_policies` 排序 + 上述测试 |

计算方式：对每个 policy 做 canonical serialization（排序无序集合），`json.dumps(sort_keys=True)` → SHA-256。

## 11. Runtime reload 行为

`start()` = `reload()`；`reload()` 解析 + 校验 + 构建新 snapshot，成功才原子替换，失败保留旧 snapshot 并记录 error。

## 12. Health 行为

`unhealthy`（无 snapshot）/ `healthy` / `degraded`（有 snapshot 但最近 reload 失败），含 `snapshot_loaded` / `policy_set_version` / `error`。

## 13. Local Policy Source

`LocalFilePolicyProvider` 读 `data/permission/policies/*.yaml`，排序加载。

## 14-18. 示例 Policy

- RBAC：`advertising.report.read`（`subject.roles contains advertising_operator`）。
- ABAC：`operations.campaign.update`（`department_id in [...] AND professional_level gte P3`）。
- Scope：`advertising.campaign.own_scope`（`scope_contains business.store`）。
- Explicit DENY：`platform.business_freeze.deny`。
- Indeterminate DENY：`platform.contractor.deny`（employment_type missing → DENY_INDETERMINATE）。

## 19. Determinism 测试

`test_permission_safety.py::test_deterministic_evaluation`：同 request 两次 evaluate，decision/reason/matched/version 相同，decision_id 允许不同。

## 20. Concurrency / Snapshot 测试

`test_permission_runtime.py::test_concurrent_evaluation_and_reload_snapshot_consistency`：4 读线程 + 1 写线程并发，无异常，版本完整。

## 21. Legacy PermissionManager migration

| 项 | 状态 |
|---|---|
| 旧规则语义迁入 | ✅ `legacy_compatibility.yaml`（sales/manager/admin → tool） |
| Parity | ✅ 100%（16 组合，`test_permission_legacy_parity.py`） |
| Cutover | 未做（ToolRunner 无可信 Subject，不伪造） |
| 删除 | 未删（保留 `app/permission/rbac.py`） |

## 22. Legacy Governance PolicyDecisionEngine migration

| 项 | 状态 |
|---|---|
| 旧规则语义迁入 | ✅ `legacy_governance.yaml`（system/developer/admin → agent action） |
| Parity | ✅ 100%（28 组合，`test_permission_governance_parity.py`） |
| Cutover | 未做（AgentLifecycleService 无可信 Subject） |
| 删除 | 未删（保留 `app/governance/policy/`） |

## 23. Parity 结果

- PermissionManager：16/16 组合一致。
- PolicyDecisionEngine：28/28 组合一致。

## 24. Legacy component migration states

- `PermissionManager`：**PARITY_VERIFIED**（未 CUTOVER）
- `PolicyDecisionEngine`：**PARITY_VERIFIED**（未 CUTOVER）
- `GovernanceGate`：**RETAIN**（§118-120 暂留）
- `MemoryAuthorizationProvider`：**OUT_OF_SCOPE**

## 25. Governance boundary 状态

Permission = Authorization；Governance = Operational Enforcement。未做 Governance 全量重写（§111-117 记录为后续）。

## 26. Frozen module diff

**零 diff**。未修改 `app/runtime/ app/memory/ app/knowledge/ app/compiler/ app/artifacts/ app/registry/`。

## 27. Dependency boundary scan

`app/permission/` 不 import `app.identity/ knowledge/ memory/ tools/ agents/ governance/ runtime`（`test_permission_safety.py::test_permission_does_not_import_other_domains` 通过）。

## 28. Full pytest 结果

**375 passed / 43 skipped / 0 failed / 0 error**（基线 302 → +73 permission 测试）。

## 29. Working tree 状态

clean。

## 30. 未完成项 / Known limitations（如实记录，非阻塞）

1. Identity `AccessContext` 尚未接入 `PermissionSubject`（上层 Application 转换，v0.11 不要求）。
2. Runtime Enforcement Cutover 未做（Tool/Agent 链路仍走旧权限）。
3. 未引入 PyCasbin（NativeEvaluator 为默认 + Reference）。
4. 未建设 PostgreSQL Policy Store / 管理后台。
5. `GovernanceGate` 仍用旧 ALLOW/DENY 命名 + `AllowAllGovernancePolicy` 兼容路径（§118-120 允许暂留）。

## 31. Remaining runtime integration debt

Tool 链权限顺序（`ToolNode → GovernanceGate → ToolRunner → PermissionManager`）待「Execution Security Integration」阶段调整，未在本轮处理。

## 32. Legacy removal conditions

- `PermissionManager` 删除条件：全部规则迁移 + parity 100% + ToolRunner 不再引用 + zero-reference + regression 0 failed。
- `PolicyDecisionEngine` 删除条件：同上，且 AgentLifecycleService 不再引用。
