# Enterprise Agent Platform — Identity Foundation

**目标版本：v0.10 Identity Foundation**
**基线：Runtime / Memory / Knowledge Foundation 已完成并冻结**
**模块定位：企业身份上下文黑盒（Enterprise Identity Context Service）**

---

# 1. 文档目的

Identity Foundation 的目标不是建设 IAM、SSO 或登录系统，而是：

> 为整个 Enterprise Agent Platform 提供统一、可信、可替换来源的企业身份上下文。

Identity 只回答：

```text
Who is this user? 这个人是谁？
```

Identity 不回答：

```text
Can this user perform this action? 这个人能不能执行这个动作？
```

后者属于 Permission + Governance。

---

# 2. Identity 与其他模块的关系（永久冻结）

Identity / Knowledge / Memory / Permission / Governance / Runtime 都是独立领域。

- Identity 不知道 Knowledge 存在。
- Knowledge 不知道 Identity 存在。
- Identity 不直接调用 Knowledge / Memory / Tool / Agent / Governance。

Identity 唯一职责：

```text
External Identity Data → IdentityProviderPort → IdentityService → AccessContext → 结束
```

字段相似不代表领域依赖。`KnowledgeAccessContext` 是 Knowledge 自己的输入契约，与 Identity 的 `AccessContext` 完全无关。

---

# 3. 最终黑盒边界

```text
External Identity Source（Local Files / HR / IAM / LDAP / SSO）
        ↓
IdentityProviderPort
        ↓
IdentityService
        ↓
AccessContext
        ↓
Platform Caller
```

Identity 不 import 任何其他业务基础域。

---

# 4. Identity 明确不负责

- Authentication：登录、密码、JWT、OAuth、SSO、MFA。
- HR System：入职、考勤、薪资、绩效。
- Authorization Engine：不实现 RBAC/ABAC/Policy Engine（属于 app/permission、app/governance）。
- 不引入 Keycloak / Ory。
- 不在 Identity 中使用 Knowledge / Memory / Tool / Agent。

---

# 5. 核心设计原则

- **Principle 1**：Identity 是独立黑盒，唯一入口 `IdentityService`。
- **Principle 2**：Identity 只提供事实，不做授权决策。
- **Principle 3**：P 等级不是权限。P 等级是职业等级属性，权限由 Permission 层决定。
- **Principle 4**：Provider 可替换（LocalFile → 未来 LDAP/AzureAD/企业微信/飞书）。
- **Principle 5**：`AccessContext` 是 Identity 的最终产品。

---

# 6. 目录结构

```text
app/identity/
├── api/service.py              IdentityService
├── models/                     user / organization / department / position /
│                               level / role / scope / clearance / attributes
├── context/                    access_context.py + builder.py
├── ports/provider.py           IdentityProviderPort
├── providers/local_file.py     LocalFileIdentityProvider
├── validation/validator.py     fail-closed 校验
├── config.py / errors.py / runtime.py / factory.py
```

---

# 7. 领域模型

- `UserIdentity`：user_id / tenant_id / name / status / organization_id / department_id / position_id / professional_level_id / role_ids / scope_ids / security_clearance / attributes。
- `Organization` / `Department` / `Position` / `Role` / `BusinessScope`：**tenant-owned 实体，都带 `tenant_id`**。
- `ProfessionalLevel`（P1-P10）与 `SecurityClearance`（public/internal/confidential/restricted）：**平台级公共枚举**，不归属 tenant。

> SecurityClearance 是企业 Identity 自身存在的「人员安全密级」属性，独立于 P 等级。

---

# 8. AccessContext

```python
AccessContext
├── user_id, tenant_id, organization_id
├── department_id, position_id, professional_level
├── roles, business_scope, security_clearance, attributes
├── identity_version
└── issued_at
```

- `identity_version`：对全部身份事实做 canonical serialization（排序所有无序集合），SHA-256 生成；**排除 `issued_at` 等运行时字段**。任何身份事实变化，版本自动变化。
- `AccessContext` 不能由 Agent / LLM 创建，只能来自 `IdentityService`。

---

# 9. Provider 与 Service

`IdentityProviderPort`：

```python
get_user / get_organization / get_department / get_position / get_roles / get_scopes
```

`LocalFileIdentityProvider` 读取 `data/identity/*.yaml`，是第一个模拟实现。

`IdentityService`：

```python
get_identity(user_id) -> UserIdentity
build_access_context(user_id) -> AccessContext
```

---

# 10. 校验（fail-closed）

- unknown organization / department / position / level / role / scope → 拒绝。
- cross-tenant reference（user 引用其它 tenant 的实体）→ 拒绝。
- status 非 active（suspended / terminated）→ 拒绝。
- invalid clearance / level → 拒绝。

---

# 11. 数据

```text
data/identity/
├── users.yaml               8 个用户 U001–U008
├── organizations.yaml       company_A
├── departments.yaml         运营/广告/客服/财务/管理
├── positions.yaml           9 个职位
├── levels.yaml              P1–P10
├── roles.yaml               8 个角色
├── scopes.yaml              单店/多店/多区域 scope
└── security_clearances.yaml public/internal/confidential/restricted
```

---

# 12. 测试

```text
tests/identity/
├── test_identity_provider.py      Provider + AccessContext + multi-scope + 版本稳定性
├── test_identity_validation.py    suspended / invalid level / cross-tenant / unknown ref /
│                                  level 与 clearance 独立
└── test_identity_replacement.py   FakeProvider 替换 + dependency boundary
```

---

# 13. 验收标准

- `app/identity/` 独立存在，黑盒边界成立。
- Identity 不依赖 Knowledge / Memory / Tool / Agent / Permission / Governance。
- Provider 可替换（FakeProvider 替换 LocalFileProvider，Core 不改）。
- AccessContext 不由 Agent 创建。
- invalid reference / cross-tenant / suspended user fail-closed。
- P 等级与 Security Clearance 分离。
- `identity_version` 使用确定性 SHA-256，排除 `issued_at`。
- 无 password / token / secret。
- 全量 pytest 0 failed。

---

# 14. 后续演进

Identity Freeze 后，未来 Provider 可替换为 PostgreSQL / LDAP / Keycloak / AzureAD / 企业微信 / 飞书，不改 `IdentityService` / `AccessContext`。

未来单独评估 Permission Foundation Enhancement（RBAC + ABAC），届时才第一次把身份事实、资源、动作、策略组合起来。
