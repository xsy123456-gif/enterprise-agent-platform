# Enterprise Agent Platform

企业级 Agent 运行时平台。目标是一个可长期承载企业 Agent 的基础设施底座：受治理的 Runtime、持久化执行、Memory、Knowledge、身份与权限。

## 架构总览

```
Agent / Skill / Tool（能力层，逐步建设）
        │
ApplicationContainer（组合根 app/main.py + app/composition/）
        │
┌───────┼───────────────────────────────────────────┐
│  Orchestration   Runtime Kernel   Knowledge Core  │
│  Planner         RuntimeDispatcher KnowledgeService│
│  Supervisor      LangGraph Runtime Haystack Adapter│
│                  ExecutionManager                  │
│                  Governance Gate                   │
└───────┼───────────────────────────────────────────┘
        │
Memory · Governance · Artifact · Audit/Trace · Permission
        │
PostgreSQL(pgvector) · Redis · Qdrant
```

## 已完成的基础层

| 模块 | 位置 | 说明 |
|---|---|---|
| Runtime Foundation | `app/runtime/` | LangGraph Durable Runtime，checkpoint 持久化 + 崩溃恢复 + 审批续跑（v0.8.10 冻结） |
| Durable Execution | `app/runtime/execution/` | `execution_id → thread_id → checkpoint → PostgreSQL` |
| Memory | `app/memory/` | 读写双管道 + PostgreSQL + pgvector + 外部 embedding |
| Knowledge | `app/knowledge/` | 黑盒知识服务：ACL 前置、Hybrid 检索、Audit/Evidence、企业文件（PDF/DOCX）接入 |
| Governance | `app/governance/` | Agent 生命周期 + 策略引擎 + 审批 + GovernanceGate |
| Tool 边界 | `app/tools/` + `app/runtime/tool_runner.py` | 统一经 ToolRunner（权限→审计→治理→执行） |
| Audit / Trace | `app/audit/` + `app/runtime/trace/` | 审计与执行追踪 |

## 黑盒边界

- **Knowledge**：Agent 只看到 `KnowledgeService.retrieve()`；Haystack / Qdrant / fastembed / jieba 只存在于 `app/integrations/knowledge/haystack/`，Knowledge Core 零第三方 RAG 依赖，可整体替换。
- **Memory**：仅 `retrieve()` / `submit()`，禁止直接访问 Postgres。
- **Tool**：统一经 `ToolRunner`，Agent 不直接调用工具。
- **Planner**：只依赖注入的 `BaseLLM` 端口，不依赖具体 LLM Provider。

## 基础设施

| 组件 | 技术 | 端口 |
|---|---|---|
| 关系存储 + 向量 | PostgreSQL 16 + pgvector | 5433 |
| 缓存 / 事件 | Redis 7 | 6379 |
| 向量检索 | Qdrant | 6333 |

```bash
docker compose up -d
```

## 快速开始

```bash
cp .env.example .env
docker compose up -d
python -m pip install -e '.[production]'
pytest -q
```

## 目录结构

```
app/
├── main.py              组合根（build_runtime / build_orchestration / build_application）
├── composition/         环境化应用容器（development/testing/production）
├── orchestration/       编排层（Planner / Supervisor / Scheduler）
├── runtime/             Runtime Kernel + LangGraph Durable Runtime + Execution
├── knowledge/           Knowledge 黑盒 Core（ACL / Ingestion / Source / Audit）
├── integrations/knowledge/haystack/   Haystack Adapter（唯一第三方 RAG 依赖处）
├── memory/              Memory 子系统（读写双管道）
├── governance/          Agent 生命周期 / 策略 / 审批
├── compiler/            Manifest → IR → Backend Artifact
├── registry/ capabilities/ agents/    Agent 注册 / 能力目录 / Agent 定义
├── tools/ permission/ audit/          工具 / RBAC / 审计
├── llm/ prompts/ sources/ artifacts/  LLM Provider / 提示词 / 来源 / 工件
├── infrastructure/      Postgres / Redis / Qdrant Provider
└── storage/ events/     存储端口 / 事件总线

data/
├── knowledge/sources/   企业知识源（PDF/DOCX + sidecar 元数据）
└── identity/            身份数据（规划中）
```

## Memory 配置

生产 Memory 引擎需要 PostgreSQL 16+ 与 pgvector。在 `.env` 中配置 `MEMORY_DATABASE_URL`、`MEMORY_DATABASE_INITIALIZE`、`MEMORY_EMBEDDING_DIMENSION`（见 `.env.example`）。

`MEMORY_DATABASE_INITIALIZE=true` 启用幂等 schema 创建与启动校验；embedding 维度必须与所选 embedding provider 匹配，不匹配时启动失败而非创建无效向量索引。

语义 Memory 使用 provider 隔离的 embedding 服务，当前期望 BGE-M3 运行在 Windows Ollama 并通过 HTTP 调用（WSL 侧不加载模型权重）。配置 `EMBEDDING_PROVIDER`、`EMBEDDING_MODEL`、`EMBEDDING_ENDPOINT`、`EMBEDDING_VERSION`。

显式验证真实 provider 连接：

```bash
EMBEDDING_INTEGRATION_TEST=true \
python -m unittest tests.memory.test_embedding.OllamaEmbeddingIntegrationTest -v
```

对独立数据库跑数据库集成测试：

```bash
MEMORY_TEST_DATABASE_URL=postgresql://user:password@localhost:5433/agentdb \
python -m unittest tests.memory.test_postgres -v
```

## 测试

```bash
pytest -q
```

覆盖：编排、Runtime E2E、Composition、Memory、Knowledge（ACL / Audit / Source→Retrieval 全流程）、Governance、Tool、LLM Provider 解耦等。

## 路线图

已完成：Runtime / Durable Execution / Memory / Knowledge / Governance / Audit-Trace / Tool 边界 / 基础设施。

规划中（能力层）：

- Identity Foundation（设计完成，待实现）
- Agent Worker
- Skill Framework
- Tool Ecosystem / Connector
- Workflow
- Business Agent
