# Enterprise Agent Platform — Knowledge / RAG Foundation 设计文档

**目标版本：Knowledge Foundation**
**基线：v0.8.10 Runtime Foundation Freeze**
**RAG Framework：Haystack**
**Vector Store：Qdrant**
**核心原则：Black-box Knowledge Service / Retrieval-only Agent Boundary**

---

# 1. 文档目的

本文档定义 Enterprise Agent Platform 的企业级 Knowledge / RAG 子系统。

Knowledge 子系统必须满足：

- 与现有 Runtime Foundation 解耦
- 不修改已经冻结的 Runtime 核心
- Haystack 作为第三方内部实现，不进入平台公共契约
- 不修改 Haystack 源码
- Agent 不知道 Haystack、Qdrant、Embedding、Retriever 的存在
- Agent 侧只暴露一个知识读取入口
- Knowledge 写入完全属于平台控制面
- Knowledge 权限在真正检索前完成
- 所有知识来源可追踪
- 所有检索行为可审计
- 可完整替换 Haystack，而不影响 Agent / Runtime
- 支持企业多租户、部门、店铺、区域等数据隔离
- 为未来领导层、员工层、用户层共享知识能力提供统一底座

---

# 2. Knowledge 子系统定位

Knowledge 与 Memory 必须是两个不同的系统。

```text
Memory
= Agent / User / Task 运行过程中沉淀的信息

Knowledge
= 企业经过管理、授权、索引的知识资产
```

例如：

## Knowledge

```text
商品说明
商品卖点
FAQ
售后政策
平台规则
企业制度
广告投放规范
运营 SOP
品牌规范
培训资料
活动规则
客服知识库
```

## Memory

```text
用户偏好
历史交互
Agent执行历史
用户曾经提出的问题
正在进行的任务
长期用户事实
```

两者都可以参与 Agent Context，但生命周期、治理方式和数据来源完全不同。

---

# 3. 明确排除的业务数据

Knowledge / RAG **不得成为实时业务数据事实源**。

以下数据禁止依赖 RAG 获取最终事实：

```text
实时商品价格
实时库存
实时销量
广告实时消耗
实时 ROAS
订单状态
物流状态
退款状态
实时店铺流量
员工实时绩效
实时活动库存
```

这些数据未来必须来自：

```text
Agent
 ↓
Tool
 ↓
Connector
 ↓
ERP / CRM / 电商平台 / 广告平台
```

原因：

> RAG 数据存在索引、同步、更新延迟，因此不能承担实时业务事实查询职责。

Knowledge 的定位始终是：

> **稳定知识 Evidence Provider。**

---

# 4. 总体架构

```text
                         Enterprise Agent Platform
                                  │
                         Agent / Skill Layer
                                  │
                                  ▼
                      KnowledgeService.retrieve()
                                  │
                  ┌───────────────┴───────────────┐
                  │                               │
                  ▼                               ▼
           Access / Scope                    Audit / Trace
              Resolver
                  │
                  ▼
          Mandatory ACL Filter
                  │
                  ▼
         KnowledgeRetrieverPort
                  │
                  ▼
          HaystackRetrieverAdapter
                  │
                  ▼
           Haystack Query Pipeline
                  │
          ┌───────┴────────┐
          │                │
          ▼                ▼
    Dense Retrieval    Sparse Retrieval
          │                │
          └───────┬────────┘
                  ▼
            Hybrid Fusion
                  │
                  ▼
               Rerank
                  │
                  ▼
               Qdrant
                  │
                  ▼
          Evidence Documents
                  │
                  ▼
              Mapper
                  │
                  ▼
      KnowledgeRetrieveResult
```

Knowledge 的写入为完全不同的控制面：

```text
External Knowledge Sources

PDF / DOCX / FAQ / CMS / Product System / SOP / API
                       │
                       ▼
          KnowledgeIngestionService
                       │
                       ▼
              Source Validation
                       │
                       ▼
             Access Metadata
                       │
                       ▼
              Parse / Convert
                       │
                       ▼
                 Cleaning
                       │
                       ▼
                 Chunking
                       │
                       ▼
                Embedding
                       │
                       ▼
                 Qdrant
```

---

# 5. 核心架构原则

## 5.1 Haystack 永远不是平台公共 API

禁止：

```text
Agent
 ↓
Haystack Pipeline
```

禁止：

```text
Runtime
 ↓
QdrantRetriever
```

禁止：

```text
Skill
 ↓
Qdrant.search()
```

唯一合法路径：

```text
Consumer
 ↓
KnowledgeService
 ↓
KnowledgeRetrieverPort
 ↓
Adapter
 ↓
Haystack
```

---

# 6. Haystack 使用边界

Haystack 官方 Pipeline 支持独立构建 indexing 和 query pipeline，因此可以只使用它的 RAG 组件，而不使用 Agent Runtime。

本平台允许使用：

```text
Pipeline
Document
Converter
Cleaner
Splitter
Document Embedder
Text Embedder
Retriever
Metadata Filter
Ranker
DocumentWriter
QdrantDocumentStore
```

Haystack 的 `DocumentWriter` 本身适用于 indexing pipeline 最终写入 Document Store，`DocumentSplitter` 则负责把长文档拆分为较小 Document。

禁止将下列 Haystack 能力发展成平台依赖：

```text
Haystack Agent
Haystack Tool Framework
Haystack Agent Runtime
Haystack Business Workflow
Haystack Memory
```

平台已有：

```text
Agent
Runtime
Tool
Memory
Governance
Execution
```

不能形成第二套控制体系。

---

# 7. 第三方源码原则

Haystack 必须作为标准 Python dependency 使用。

原则：

```text
pip dependency
+
Adapter
+
Configuration
```

禁止：

```text
Fork Haystack 后长期维护
```

禁止：

```text
复制 Haystack 源码进入 app/
```

禁止：

```text
直接修改 site-packages
```

禁止：

```text
Monkey Patch Haystack 内部实现
```

如果 Haystack 缺失某项能力：

优先：

```text
平台 Adapter 扩展
```

其次：

```text
自建 Haystack Component
```

仍然不修改 Haystack 本体。

---

# 8. Knowledge Service 公共边界

Agent 只能看到：

```python
KnowledgeService.retrieve()
```

逻辑接口：

```python
class KnowledgeService:
    async def retrieve(
        self,
        request: KnowledgeRetrieveRequest,
        access_context: KnowledgeAccessContext,
    ) -> KnowledgeRetrieveResult:
        ...
```

这里存在两个完全不同的信任来源。

---

# 9. KnowledgeRetrieveRequest

`KnowledgeRetrieveRequest` 表示：

> Consumer 想查询什么。

建议模型：

```text
KnowledgeRetrieveRequest

query
knowledge_types
business_filters
requested_top_k
language
context_hint
trace_id
```

---

## 9.1 query

必填。

例如：

```text
日本站商品退货期限是多少？
```

---

## 9.2 knowledge_types

允许调用方缩小业务知识范围。

例如：

```text
after_sales_policy
product_knowledge
faq
platform_policy
operation_sop
```

但不能扩大授权范围。

---

## 9.3 business_filters

调用方可以提出业务过滤条件，例如：

```text
region = JP
brand = ABC
product_category = electronics
```

这些只是：

> Requested Filter

不是：

> Authorization Filter

---

## 9.4 requested_top_k

调用方可以表达希望返回多少结果。

但 Knowledge Service 必须配置：

```text
MIN_TOP_K
DEFAULT_TOP_K
MAX_TOP_K
```

例如 Agent 请求：

```text
top_k = 10000
```

平台不能直接执行。

---

# 10. KnowledgeAccessContext

这是整个安全体系最重要的模型之一。

`KnowledgeAccessContext` 不允许 Agent 创建。

来源必须是可信的平台身份 / Permission 上下文。

建议包含：

```text
user_id
tenant_id
role
department_id
authorized_store_ids
authorized_regions
authorized_knowledge_scopes
security_clearance
permissions
session_id
execution_id
trace_id
```

---

# 11. 权限信任边界

必须遵循：

```text
Agent Request
≠
Authorization
```

例如 Agent 请求：

```text
store_ids:
- JP01
- JP02
- JP99
```

真正授权：

```text
authorized_store_ids:
- JP01
- JP02
```

最终：

```text
effective_store_ids:
- JP01
- JP02
```

JP99 不得参与检索。

---

# 12. Effective Filter

Knowledge Service 内部必须生成：

```text
EffectiveFilter
```

算法：

```text
Requested Business Filter
           ∩
Authorized Scope
           ∩
System Policy
           =
Effective Retrieval Filter
```

例如：

```text
tenant_id = tenant_A

AND

store_id IN [JP01, JP02]

AND

region = JP

AND

knowledge_type IN [
    product_knowledge,
    after_sales_policy
]

AND

security_level <= user_clearance
```

---

# 13. ACL 必须在 Retrieval 前发生

禁止：

```text
Qdrant
 ↓
召回100条
 ↓
ACL过滤
 ↓
剩下5条
```

这代表未经授权的数据已经进入应用候选集。

正确：

```text
AccessContext
 ↓
ACL Resolver
 ↓
Metadata Filter
 ↓
Qdrant Query
 ↓
Authorized Candidate Set
```

Haystack Retriever 支持查询时传递 metadata filters，Qdrant 本身也支持基于 payload 的过滤，因此这一安全模型可以在检索层真正执行，而不是结果返回后再过滤。

---

# 14. KnowledgeRetrieverPort

平台真正依赖的是自己的 Port。

```python
class KnowledgeRetrieverPort:
    async def retrieve(
        self,
        query: KnowledgeQuery,
    ) -> KnowledgeRetrieval:
        ...
```

这里的 `KnowledgeQuery` 已经是经过：

```text
Validation
+
Access Resolution
+
Policy
+
Query Normalization
```

后的可信内部请求。

Port 不知道：

```text
Agent
Skill
领导
员工
客服
```

它只接受平台标准查询。

---

# 15. Haystack Adapter

建议：

```text
app/integrations/knowledge/haystack/
```

结构：

```text
haystack/

├── adapter.py
├── config.py
├── document_store.py
├── query_pipeline.py
├── indexing_pipeline.py
├── mapper.py
├── filters.py
├── exceptions.py
└── health.py
```

---

# 16. HaystackAdapter 职责

只负责：

```text
平台模型
    ↓
Haystack模型

Haystack结果
    ↓
平台模型
```

不能负责：

```text
用户权限决策
Agent调度
业务流程
审批
Memory
最终回答生成
```

---

# 17. Query Pipeline

第一版标准 Query Pipeline：

```text
Query
 ↓
Normalization
 ↓
Dense Query Embedding
 ↓
Sparse Query Embedding
 ↓
QdrantHybridRetriever
 ↓
Fusion
 ↓
Rerank
 ↓
Top K
 ↓
Mapper
```

Haystack 官方 Qdrant 集成当前提供：

- `QdrantEmbeddingRetriever`
- `QdrantSparseEmbeddingRetriever`
- `QdrantHybridRetriever`

其中 Hybrid Retriever 同时使用 dense 和 sparse embeddings，并通过融合产生最终结果。

因此第一版不需要自己发明 Hybrid Retrieval 框架。

---

# 18. Retrieval Strategy 不允许 Agent 控制

禁止 Agent 传：

```text
retriever=dense
```

禁止：

```text
fusion=rrf
```

禁止：

```text
embedding_model=xxx
```

禁止：

```text
reranker=xxx
```

这些全部属于：

```text
Knowledge Internal Strategy
```

可以通过平台配置调整，但不能暴露给 Agent。

---

# 19. KnowledgeRetrieveResult

建议：

```text
KnowledgeRetrieveResult

retrieval_id

items[]

query_metadata

timing

evidence

warnings
```

---

# 20. KnowledgeItem

每个结果：

```text
KnowledgeItem

knowledge_id

document_id

chunk_id

content

knowledge_type

source

citation

score

metadata

content_hash

document_version
```

---

# 21. Citation

Citation 必须是一等公民。

建议：

```text
Citation

source_id
source_type
source_name
document_id
document_version
page
section
uri_reference
```

例如：

```text
document:
JP_AfterSales_Policy.pdf

version:
2026.08

page:
17

section:
3.2 Returns
```

不能只有：

```text
source = "RAG"
```

这种 Citation 没有企业价值。

---

# 22. Knowledge = Evidence

Knowledge Service 返回：

```text
证据
```

不返回：

```text
业务结论
```

例如返回：

```text
日本站退货政策第3.2条：
消费者可以在……
```

而不是：

```text
所以应该立即退款。
```

最终解释和业务决策属于：

```text
Agent / LLM
```

因此永久边界：

```text
Knowledge
=
Evidence

Agent
=
Reasoning
```

---

# 23. Knowledge Ingestion Control Plane

Agent 永远不能访问 Knowledge 写入 API。

Knowledge 写入属于：

```text
Knowledge Control Plane
```

内部接口可以存在：

```text
ingest()

update()

delete()

reindex()

sync()

set_acl()
```

但这些不是 Agent Runtime API。

---

# 24. Knowledge Source 类型

第一阶段至少支持：

```text
manual_document
product_catalog
faq
policy
sop
platform_rule
brand_document
training_material
cms
external_api
```

---

# 25. 人工知识上传

用于：

```text
PDF
DOCX
Markdown
HTML
TXT
```

典型内容：

```text
企业制度
平台规则
运营 SOP
商品说明书
品牌规范
培训资料
```

必须由 Control Plane 执行。

---

# 26. 自动知识同步

例如：

```text
PIM
 ↓
Product Connector
 ↓
Knowledge Ingestion

FAQ CMS
 ↓
FAQ Connector
 ↓
Knowledge Ingestion
```

外部系统不允许直接写 Qdrant。

---

# 27. SourceDocument

进入 Knowledge Ingestion 的第一层对象应该统一。

建议：

```text
SourceDocument

source_system

external_id

tenant_id

document_type

title

content

source_version

source_updated_at

language

metadata

access_policy
```

---

# 28. Document Identity

必须保证同一个外部业务文档存在稳定身份。

例如：

```text
source_system:
product_pim

external_id:
SKU-12345
```

可以生成稳定：

```text
document_id
```

不能每次同步都创建新知识。

---

# 29. Version

Knowledge 必须有版本。

例如：

```text
document_id:
POLICY-JP-RETURN

version:
2026.08
```

新版本进入后：

```text
旧版本
→ inactive / superseded

新版本
→ active
```

正常检索默认只能搜索 active 版本。

---

# 30. 更新策略

知识更新必须支持：

```text
Source Update
 ↓
Detect Version
 ↓
Compare Hash
 ↓
Changed?
 ├─ No → Skip
 └─ Yes
      ↓
   Reprocess
      ↓
   Replace Index
```

必须具备幂等性。

同一个版本重复同步不能产生无限重复 Chunk。

---

# 31. 删除策略

删除不能只删除数据库记录。

必须同时处理：

```text
Document Metadata
Chunk
Dense Vector
Sparse Vector
Index
Retrieval Visibility
```

推荐先：

```text
tombstone / inactive
```

再异步物理删除。

这样方便：

```text
Audit
Recovery
Investigation
```

---

# 32. Metadata Schema

每个 Chunk 至少必须携带：

```text
tenant_id
document_id
chunk_id
document_version
knowledge_type
source_system
external_id
region
language
security_level
status
created_at
updated_at
```

根据业务可以存在：

```text
department_id
store_id
brand_id
category_id
product_id
sku_id
```

---

# 33. ACL Metadata

ACL Metadata 和普通业务 Metadata 必须逻辑区分。

例如：

```text
_acl.tenant_id
_acl.allowed_departments
_acl.allowed_stores
_acl.security_level
```

业务 metadata：

```text
region
brand
category
product_id
```

这样可以避免业务过滤条件和权限过滤条件混淆。

---

# 34. Qdrant Collection Strategy

当前建议：

> **不要一个 tenant 建一个 collection。**

Qdrant 官方通常建议多租户场景优先使用共享 collection + payload-based partitioning，并通过 tenant/user metadata 进行隔离；对于过滤字段还应建立 payload index。

因此第一阶段建议：

```text
knowledge_documents
```

作为主要逻辑 Collection。

依靠：

```text
tenant_id
knowledge_type
store_id
security_level
```

等 Payload 过滤。

---

# 35. 大型租户预留

不能把单 Collection 写死成永远方案。

未来极大型企业可以：

```text
shared collection
```

升级为：

```text
shard-based tenant isolation
```

Qdrant 当前同时支持 payload-based 和 shard-based multitenancy，因此 Port 层不应该暴露 collection 结构。

---

# 36. Chunking

禁止全平台统一：

```text
chunk_size = 500
```

这种硬编码策略。

Chunk Strategy 必须根据文档类型变化。

例如：

## FAQ

```text
Question + Answer
=
一个逻辑 Chunk
```

## Product Knowledge

```text
基本信息
卖点
规格
使用说明
注意事项
```

按语义区域拆分。

## Policy

优先按照：

```text
Chapter
Section
Article
```

拆分。

## SOP

按照：

```text
流程
步骤
注意事项
异常处理
```

拆分。

Haystack 提供普通、递归以及层级式文档拆分组件，因此这些策略可以通过组件配置完成，而不是修改框架本体。

---

# 37. Embedding

Embedding 必须是 Knowledge 内部策略。

平台公共契约不能出现：

```text
bge-m3
OpenAI
Cohere
SentenceTransformers
```

这些属于：

```text
KnowledgeEmbeddingProvider
```

必须可配置。

---

# 38. Sparse Embedding

因为目标采用 Hybrid Retrieval：

Index Pipeline 必须同时考虑：

```text
Dense Embedding
+
Sparse Embedding
```

Haystack 当前的 Qdrant 集成已经支持 sparse embedding retrieval，并通过专门的 sparse document/query embedder 产生需要的数据。

---

# 39. Reranker

第一阶段必须预留 Ranker。

流程：

```text
Retrieve Top 30
 ↓
Rerank
 ↓
Return Top 8
```

而不是直接：

```text
Vector Score Top 8
→ Agent
```

Ranker Provider 同样必须内部可替换。

禁止 Agent 指定 Ranker。

---

# 40. Empty Result

当检索不到可靠知识：

Knowledge Service 必须返回：

```text
items = []
```

以及：

```text
reason = no_relevant_evidence
```

不能：

```text
LLM自动编一个答案
```

Knowledge Service 没有生成答案职责。

---

# 41. Score Threshold

必须存在平台级：

```text
minimum_relevance_threshold
```

低于阈值的结果不应该进入 Agent Context。

避免：

```text
“为了返回 Top 8”
```

强行返回 8 条无关内容。

---

# 42. Audit

Knowledge Audit 必须知道：

```text
谁
什么时候
为什么
查询了什么范围
最终访问了哪些知识
是否被权限限制
```

但不默认保存完整 Chunk 内容。

---

# 43. Knowledge Retrieval Audit Record

建议：

```text
retrieval_id
execution_id
trace_id
user_id
tenant_id
query_hash
requested_scope
effective_scope
document_ids
chunk_ids
result_count
decision
timestamp
```

---

# 44. RetrievalEvidence

Memory 与 Knowledge 建议最终共享一种抽象：

```text
RetrievalEvidence
```

建议：

```text
retrieval_id
source_type
source_ids
document_ids
chunk_ids
scope
scores
content_hashes
execution_id
trace_id
timestamp
```

其中：

```text
source_type = memory
```

或者：

```text
source_type = knowledge
```

---

# 45. Audit 不保存完整内容

普通 Audit：

```text
IDs
Metadata
Scope
Hash
Decision
```

Knowledge Store：

```text
真正内容
```

调查时：

```text
Audit
 ↓
chunk_id
 ↓
Knowledge Repository
 ↓
原始证据
```

---

# 46. EventBus

EventBus 只传：

```text
knowledge.retrieval.started
knowledge.retrieval.completed
knowledge.retrieval.denied
knowledge.ingestion.started
knowledge.ingestion.completed
knowledge.document.updated
knowledge.document.deleted
```

Event Payload 主要包含：

```text
retrieval_id
document_id
trace_id
status
metadata
```

禁止把几十 KB 的 Chunk 文本放进 EventBus。

---

# 47. Trace

Trace 应该比 Audit 更关注：

```text
执行过程
```

例如：

```text
knowledge.retrieve

ACL      3ms
embedding 23ms
dense     18ms
sparse    14ms
fusion     2ms
rerank    45ms
total    105ms
```

这样以后可以分析 Knowledge 性能。

---

# 48. Governance

Knowledge Retrieval 属于：

```text
Light Governance
```

默认：

```text
Identity
+
ACL
+
Scope
+
Policy
+
Audit
```

通常不需要：

```text
Human Approval
```

除非未来存在极特殊的机密知识读取政策。

---

# 49. Agent 接入方式

Knowledge 黑盒完成后，Agent 有两种使用模式。

---

## 49.1 Automatic Context Retrieval

适合：

```text
客服 Agent
商品咨询
制度查询
FAQ
SOP
```

流程：

```text
User
 ↓
Agent Context Construction
 ↓
Knowledge.retrieve()
 ↓
Evidence
 ↓
Agent Context
 ↓
LLM
```

---

# 50. Explicit Knowledge Retrieval

复杂 Agent 可以主动请求：

```text
knowledge.retrieve
```

但是从 Agent 看来它仍然只是：

```text
Knowledge Capability
```

不能暴露：

```text
Haystack
Qdrant
Retriever
Embedding
Pipeline
```

---

# 51. Runtime 集成原则

`app/runtime/` 已冻结。

因此禁止为了 RAG：

```text
修改 RuntimeDispatcher
修改 RuntimeSelector
修改 ExecutionManager
修改 GraphRuntime Contract
```

Knowledge 通过：

```text
Composition Root
+
Integration Adapter
```

注入应用。

原则：

> Runtime 依赖 Knowledge Port，不依赖 Haystack。

如果当前 Runtime Extension Boundary 不需要修改核心即可接入，则直接组合。

如确实需要扩展：

必须通过新的 Adapter / Provider，而不是让 Haystack 代码进入 Runtime Kernel。

---

# 52. Composition

建议最终：

```text
build_application()

├── build_runtime()
├── build_memory()
├── build_governance()
└── build_knowledge()
```

Knowledge 由 Composition Root 负责组装。

---

# 53. Knowledge 生命周期

Knowledge System 至少提供：

```text
start()
stop()
health()
```

ApplicationContainer 可以检查：

```text
knowledge:
  healthy
qdrant:
  healthy
embedding:
  healthy
```

---

# 54. Failure Isolation

Knowledge 故障不能导致整个 Runtime 无法启动。

理想行为：

```text
Runtime          healthy
Memory           healthy
Knowledge        degraded
```

Knowledge-dependent Agent 请求可以失败或降级。

但整个 Agent Platform 不应该 Crash。

---

# 55. Qdrant Failure

Qdrant 不可用：

```text
KnowledgeUnavailableError
```

禁止把 Qdrant 原生 exception 暴露给 Agent。

---

# 56. Embedding Failure

Embedding Provider 故障：

```text
KnowledgeEmbeddingError
```

内部记录 Provider error。

外部只返回平台异常。

---

# 57. Timeout

Knowledge Retrieval 必须有：

```text
timeout
```

不能无限等待。

超时：

```text
KnowledgeTimeoutError
```

并进入 Trace / Metrics。

---

# 58. Circuit Breaker

生产级 Knowledge Adapter 应预留：

```text
circuit breaker
```

避免 Qdrant / Embedding Provider 故障时：

```text
大量Agent
→ 无限重试
→ 放大故障
```

---

# 59. Retry

只允许对：

```text
明确可重试错误
```

进行有限重试。

禁止无脑 retry。

---

# 60. Observability

至少需要指标：

```text
knowledge_retrieval_total
knowledge_retrieval_success_total
knowledge_retrieval_denied_total
knowledge_retrieval_empty_total
knowledge_retrieval_error_total
knowledge_retrieval_latency
knowledge_embedding_latency
knowledge_rerank_latency
knowledge_result_count
knowledge_ingestion_total
knowledge_ingestion_error_total
```

---

# 61. RAG Quality Evaluation

“接口能返回结果”不代表 RAG 完成。

至少要评估：

```text
Recall
Precision
MRR / Ranking Quality
Citation Correctness
ACL Leakage Rate
Empty Retrieval Accuracy
Latency
```

最重要的企业级安全指标：

```text
Unauthorized Retrieval Rate
=
0
```

---

# 62. 电商测试知识集

建议创建固定测试集：

```text
商品资料
FAQ
日本站售后规则
广告投放 SOP
员工内部运营规则
跨店铺私有文档
企业级公共文档
```

---

# 63. ACL 测试

必须测试：

```text
Tenant A
不能查 Tenant B

Store JP01
不能查 Store JP02

普通员工
不能查 Manager-only Knowledge

用户层客服 Agent
不能检索内部员工制度

领导层
只能查其组织范围
```

---

# 64. Prompt Injection / Knowledge Poisoning

Knowledge 文档必须被视为：

```text
Untrusted Data
```

即使文件由企业内部上传，也不能允许 Chunk 中的文本：

```text
“忽略系统指令”
```

成为 Agent 系统指令。

Knowledge Content 只能作为：

```text
Evidence
```

不能进入 System Instruction 层。

---

# 65. Sensitive Metadata

不得把：

```text
DB credentials
internal secrets
API key
authorization token
```

作为 Qdrant metadata。

Knowledge Ingestion 必须有敏感字段过滤。

---

# 66. Repository Structure

建议：

```text
app/

└── knowledge/

    ├── api/
    │   └── service.py
    │
    ├── models/
    │   ├── request.py
    │   ├── result.py
    │   ├── evidence.py
    │   ├── access.py
    │   └── document.py
    │
    ├── ports/
    │   ├── retriever.py
    │   ├── ingestion.py
    │   └── repository.py
    │
    ├── access/
    │   ├── resolver.py
    │   └── filters.py
    │
    ├── ingestion/
    │   ├── service.py
    │   ├── validator.py
    │   ├── normalizer.py
    │   ├── versioning.py
    │   └── lifecycle.py
    │
    ├── audit/
    │   └── evidence.py
    │
    ├── events/
    │   └── models.py
    │
    ├── errors.py
    ├── config.py
    ├── runtime.py
    └── factory.py


app/integrations/

└── knowledge/

    └── haystack/

        ├── adapter.py
        ├── query_pipeline.py
        ├── indexing_pipeline.py
        ├── document_store.py
        ├── mapper.py
        ├── filters.py
        ├── config.py
        ├── health.py
        └── exceptions.py
```

---

# 67. 依赖方向

允许：

```text
knowledge
 ↓
knowledge ports
```

允许：

```text
haystack adapter
 ↓
knowledge ports
```

禁止：

```text
knowledge core
 ↓
haystack
```

禁止：

```text
runtime core
 ↓
haystack
```

禁止：

```text
agent
 ↓
qdrant
```

---

# 68. 可替换性测试

这是最终必须存在的架构测试。

例如：

```text
HaystackRetrieverAdapter
```

替换成：

```text
FakeRetrieverAdapter
```

整个：

```text
KnowledgeService
Agent
Runtime
```

必须仍然工作。

进一步：

```text
HaystackRetrieverAdapter
 ↓ 删除

LlamaIndexRetrieverAdapter
 ↓ 接入
```

不允许修改：

```text
Agent
Skill
Runtime
Governance
Memory
```

如果做不到：

> Knowledge 黑盒封装失败。

---

# 69. Haystack 升级原则

平台锁定依赖版本。

升级：

```text
Old Haystack
 ↓
Adapter Contract Tests
 ↓
Retrieval Regression Tests
 ↓
ACL Tests
 ↓
Quality Evaluation
 ↓
Upgrade
```

不能：

```text
pip install -U
→ 直接生产运行
```

---

# 70. 配置原则

所有实现策略配置化：

```text
KNOWLEDGE_BACKEND
KNOWLEDGE_QDRANT_URL
KNOWLEDGE_COLLECTION
KNOWLEDGE_DENSE_MODEL
KNOWLEDGE_SPARSE_MODEL
KNOWLEDGE_RERANKER
KNOWLEDGE_DEFAULT_TOP_K
KNOWLEDGE_MAX_TOP_K
KNOWLEDGE_SCORE_THRESHOLD
KNOWLEDGE_TIMEOUT
```

但不要让配置名字泄漏进平台公共接口。

---

# 71. 禁止硬编码

禁止：

```python
if user.role == "manager":
    stores = [...]
```

禁止：

```python
if agent_id == "customer_agent":
    knowledge_type = ...
```

禁止：

```python
if tenant == "company_a":
    collection = ...
```

所有权限必须来自：

```text
Identity
Policy
Resource Metadata
Scope Resolution
```

---

# 72. 测试体系

至少分：

```text
Unit
Contract
Integration
Security
Quality
Failure
Performance
```

---

# 73. Unit Tests

覆盖：

```text
Request validation
Access resolution
Filter intersection
Result mapping
Citation mapping
Version resolution
Dedup
Error mapping
```

---

# 74. Contract Tests

重点验证：

```text
KnowledgeRetrieverPort
```

任意 Adapter 都必须通过同一套 Contract Tests。

---

# 75. Integration Tests

真实：

```text
Haystack
+
Qdrant
+
Embedding
```

进行测试。

不能只有 Fake Store。

---

# 76. Security Tests

必须包括恶意查询：

```text
查询其他tenant知识
查询未授权store
伪造tenant_id
伪造role
绕过metadata filter
top_k异常
恶意filter
prompt injection document
```

---

# 77. Failure Tests

必须主动模拟：

```text
Qdrant down
Embedding down
Reranker down
Timeout
Malformed Document
Corrupted Metadata
Duplicate Document
Version Conflict
Delete Failure
```

---

# 78. Performance Tests

至少记录：

```text
P50
P95
P99
```

并区分：

```text
embedding latency
retrieval latency
reranking latency
total latency
```

---

# 79. Knowledge Foundation 验收条件

必须全部满足才允许标记完成。

## Architecture

- [ ] Agent 不依赖 Haystack
- [ ] Runtime 不依赖 Haystack
- [ ] Knowledge Core 不依赖 Qdrant SDK
- [ ] Haystack 只存在于 Adapter
- [ ] Haystack 源码零修改
- [ ] KnowledgeRetrieverPort 可替换

## Retrieval

- [ ] Dense Retrieval
- [ ] Sparse Retrieval
- [ ] Hybrid Retrieval
- [ ] Metadata Filter
- [ ] Rerank
- [ ] Threshold
- [ ] Citation
- [ ] Empty Result

## Security

- [ ] Tenant isolation
- [ ] Department isolation
- [ ] Store isolation
- [ ] Knowledge scope
- [ ] Security level
- [ ] ACL pre-filter
- [ ] Unauthorized Candidate = 0

## Ingestion

- [ ] Manual document ingestion
- [ ] Versioning
- [ ] Update
- [ ] Delete
- [ ] Idempotency
- [ ] Metadata
- [ ] ACL Metadata
- [ ] Chunking
- [ ] Embedding
- [ ] Qdrant write

## Governance

- [ ] Retrieval Audit
- [ ] Retrieval Evidence
- [ ] Trace
- [ ] Event
- [ ] No full sensitive content in standard Audit/EventBus

## Reliability

- [ ] Timeout
- [ ] Retry policy
- [ ] Error isolation
- [ ] Health
- [ ] Startup / shutdown
- [ ] Qdrant failure test
- [ ] Embedding failure test

## Evaluation

- [ ] Retrieval benchmark
- [ ] Ranking benchmark
- [ ] Citation validation
- [ ] ACL leakage test
- [ ] Latency benchmark

---

# 80. 最终冻结架构

Knowledge Foundation 完成后应形成：

```text
                      Agent Platform
                           │
                           ▼
                  KnowledgeService
                           │
                 retrieve(request,
                      access_context)
                           │
            ┌──────────────┴──────────────┐
            │                             │
            ▼                             ▼
       Scope / ACL                 Audit / Evidence
            │
            ▼
   KnowledgeRetrieverPort
            │
            ▼
    HaystackAdapter
            │
            ▼
     Retrieval Pipeline
            │
       Hybrid + Rerank
            │
            ▼
          Qdrant
```

写入：

```text
Knowledge Sources
       │
       ▼
KnowledgeIngestionService
       │
       ▼
Parse / Clean / Chunk
       │
       ▼
ACL Metadata
       │
       ▼
Dense + Sparse Embedding
       │
       ▼
Qdrant
```

---

# 81. 最终架构原则

Knowledge Foundation 必须永久遵守以下原则：

### Principle 1

```text
Agent only knows retrieve()
```

### Principle 2

```text
Haystack is an implementation,
not a platform contract.
```

### Principle 3

```text
Knowledge = Evidence
Agent = Reasoning
```

### Principle 4

```text
ACL before retrieval,
never after retrieval.
```

### Principle 5

```text
Agent cannot write Knowledge.
```

### Principle 6

```text
Realtime business facts
come from Tools / Connectors,
not RAG.
```

### Principle 7

```text
Audit stores references,
not duplicated sensitive knowledge.
```

### Principle 8

```text
Haystack can be removed
without changing Agent or Runtime.
```

---

# 82. 结论

Enterprise Agent Platform 的 Knowledge / RAG 不建设第二套 Agent 平台。

最终定位为：

> **一个受企业权限、审计、生命周期和数据隔离控制的 Knowledge Evidence Service。**

内部使用：

```text
Haystack
+
Qdrant
```

Haystack 负责：

```text
Document processing
Embedding
Retrieval
Hybrid Retrieval
Reranking
Pipeline composition
```

平台负责：

```text
Knowledge Contract
Identity
ACL
Tenant isolation
Store scope
Knowledge lifecycle
Versioning
Audit
Trace
Evidence
Failure isolation
Agent integration
```

Agent 最终只能看到：

```python
KnowledgeService.retrieve(...)
```

达到：

> **Haystack 内部可以非常复杂，但对于整个 Enterprise Agent Platform 而言，Knowledge 永远只是一个稳定、可治理、可审计、可替换的黑盒。**

这应作为 Knowledge / RAG Foundation 的正式设计基线。
