# OpenClaw Knowledge Evidence Engine — 代码全览

> 子系统 A：知识接入、索引与证据引擎  
> 项目路径：`openclaw-knowledge-evidence-engine/`  
> 运行环境：`omni-desk` conda env（Python 3.10）  
> LLM：豆包 `doubao-seed-2-0-pro-260215`，通过火山引擎 ARK API 接入

---

## 一、项目定位

本项目是"会议与项目全链路伴侣"的**证据底座**，负责把飞书 Docs、会议纪要、群聊、任务、日历等原始数据转化为可引用、可追踪的知识产物，以标准 HTTP API 形式向上层（子系统 B）提供服务。

子系统 A **不负责**：飞书卡片样式、群消息推送、真实任务写入、Demo 界面交互。

---

## 二、目录结构

```
openclaw-knowledge-evidence-engine/
├── app/
│   ├── config.py               # 全局配置（API Key、路径）
│   ├── llm_client.py           # LLM 调用封装（限速 + 自动重试）
│   ├── models.py               # 核心数据模型
│   ├── engine.py               # 中央引擎（增量构建 + 磁盘缓存）
│   ├── main.py                 # FastAPI 应用（4 个 API 端点）
│   ├── cli.py                  # Click CLI（6 个命令）
│   ├── __main__.py             # CLI 入口（含 Windows UTF-8 修复）
│   ├── connectors/
│   │   └── feishu_adapter.py   # A01：飞书只读数据适配器
│   ├── security/
│   │   └── permission_guard.py # A02：权限与租户隔离守卫
│   ├── ingestion/
│   │   ├── document_parser.py  # A03：文档与会议解析器
│   │   ├── meeting_context.py  # A09：会前上下文包生成器
│   │   └── weekly_aggregator.py# A11：周报时间窗口聚合器
│   ├── indexing/
│   │   ├── page_index_builder.py # A04：PageIndex 树索引构建器
│   │   └── vector_index.py       # 向量索引（嵌入 + 余弦检索）
│   ├── atoms/
│   │   ├── atom_extractor.py   # A05：知识原子抽取器
│   │   └── action_item_extractor.py # A10：Action Item 抽取与字段补齐
│   ├── graph/
│   │   └── evidence_graph.py   # A06：Evidence Graph 构建器
│   ├── retrieval/
│   │   ├── evidence_retriever.py    # A07：多源检索与证据召回
│   │   └── evidence_quality_judge.py# A08：相关性与证据质量判断
│   └── evaluation/
│       └── metrics_engine.py   # A12：评测数据与指标引擎
├── fixtures/                   # 本地模拟飞书数据
│   ├── docs/alpha_prd.json
│   ├── minutes/alpha_weekly_review.json
│   ├── messages/alpha_group_thread.json
│   ├── tasks/alpha_tasks.json
│   ├── calendar/alpha_meetings.json
│   ├── events/minutes_created.json
│   └── permissions/permission_policy.yaml
├── contracts/                  # A↔B 接口合约样例（冻结）
├── outputs/
│   ├── cache/                  # 磁盘缓存（索引、原子、图谱）
│   ├── demo/                   # 构建摘要、评测报告
│   └── events/                 # 读取追踪日志
├── tests/                      # 单元测试 + 合约测试（21 个）
├── requirements.txt
└── Makefile
```

---

## 三、核心数据模型（`app/models.py`）

| 模型 | 字段 | 说明 |
|---|---|---|
| `KnowledgeSource` | source_id, source_type, title, url, tenant_id, project_id, permission_scope, updated_at, content | 原始数据源元信息 |
| `KnowledgeAtom` | atom_id, atom_type, summary, source_id, evidence_ids, confidence, owner_candidates, deadline, risk_level, risk_reason | 知识原子，类型包括 Fact/Decision/ActionItem/Risk/Blocker/Change/Question/Insight |
| `Evidence` | evidence_id, summary, source_id, source_type, source_url, chunk_text, timestamp, support_level, confidence, is_stale | 可引用证据单元，support_level: high/medium/low/unverified |
| `ActionItem` | item_id, title, evidence_id, confidence, owner, deadline, priority, source_url, needs_confirmation | 行动项，缺少字段时标记 needs_confirmation=True |

---

## 四、模块详解

### A01 飞书只读数据适配器（`connectors/feishu_adapter.py`）

**职责**：封装数据读取，当前为 fixture 模式（本地 JSON），后续只需替换此模块即可对接真实飞书 API。

**核心函数**：
- `load_source(source_type, source_id, tenant_id, project_id)` — 按类型加载原始数据，写入 `outputs/events/read_trace_*.json`
- `load_manifest(tenant_id, project_id)` — 返回所有 source 的轻量元信息列表

**支持类型**：docs / minutes / messages / tasks / calendar / bitable

---

### A02 权限与租户隔离守卫（`security/permission_guard.py`）

**职责**：在所有检索前执行权限过滤，防止跨租户或越权访问。

**核心函数**：
- `filter_sources(manifest, user_id, tenant_id)` — 返回 (allowed, blocked, audit_log)，tenant_id 为空时抛 PermissionError
- `assert_source_allowed(source_id, user_id, tenant_id)` — 快速单源权限判断

**权限策略**：从 `fixtures/permissions/permission_policy.yaml` 加载，定义用户→组→source 的访问映射。

---

### A03 办公文档与会议解析器（`ingestion/document_parser.py`）

**职责**：将各类原始数据统一解析为结构化对象。

**解析结果类型**：
- `ParsedDocument` — docs：保留 sections（含 heading + level + content）、comments
- `ParsedMinutes` — minutes：保留 transcript、decisions、action_items_raw、attendees
- `ParsedMessages` — messages：保留每条消息的 sender/timestamp/text
- `ParsedTasks` — tasks：保留任务列表及评论

**`full_text(parsed)`**：将任意解析结果展平为纯文本，用于后续索引。

---

### A04 PageIndex 树索引构建器（`indexing/page_index_builder.py`）

**职责**：对长文档构建树形索引，每个叶子节点是 500-600 字的文本块，每个节点有 LLM 生成的摘要。

**数据结构**：
```
PageIndex
  └── root: PageNode (depth=0, summary=doc_description)
        └── section nodes (depth=1)
              └── chunk nodes (depth=2, chunk=原文片段)
```

**LLM 调用**：
- `_summarize(chunk)` — 对每个 chunk 生成 30 字以内摘要
- `_describe_doc(title, summaries)` — 对整篇文档生成 60 字以内描述

**分块参数**：CHUNK_SIZE=600，OVERLAP=80

---

### A05 知识原子抽取器（`atoms/atom_extractor.py`）

**职责**：从 PageIndex 的每个叶子 chunk 中抽取结构化知识原子。

**抽取类型**：Fact、Decision、ActionItem、Risk、Blocker、Change、Question、Insight

**规则**：
- confidence < 0.5 的原子丢弃
- Risk 必须有 risk_reason 和 risk_level
- 每个原子绑定 evidence_id（格式：`ev_{source_id}_{序号}`）

**当前索引结果**：
- doc_alpha_prd → 21 atoms
- minutes_alpha_review → 16 atoms
- msg_alpha_group → 16 atoms
- 合计 **53 atoms**

---

### A06 Evidence Graph 构建器（`graph/evidence_graph.py`）

**职责**：建立 source、atom、person、task 之间的关系图。

**节点类型**：source / atom / person / task

**边类型**：
- `contains`：source → atom
- `assigned_to`：atom/task → person
- `references`：source/task → related source

**`evidence_store`**：字典，key=evidence_id，value=Evidence 对象，是检索的核心数据结构。

**当前图规模**：73 节点，若干边

---

### A07 多源检索与证据召回（`retrieval/evidence_retriever.py`）

**职责**：从 PageIndex + evidence_store 中检索与 query 相关的证据，采用 BM25 + 语义向量双路检索，通过 RRF 融合排序。

**检索流程（五步）**：

1. **BM25 检索**：对 query 分词后，在所有 chunk 和 evidence_store 中打分
2. **语义检索**：将 query 嵌入为向量，在 VectorIndex 中做余弦相似度检索（top 50）
3. **RRF 融合**：Reciprocal Rank Fusion 合并两路排名（k=60），取并集后按 RRF 分排序
4. **内容相似度去重**：基于字符 bigram Jaccard 相似度（阈值 0.65），过滤跨 source 的重复表达
5. **Graph 扩展**：对检索到的 source，自动补充同 source 下尚未召回的 Risk/Decision/ActionItem 原子

**分词**：优先使用 `jieba` 词语级分词，fallback 到正则双字符匹配。

**向量索引**：`VectorIndex`（`indexing/vector_index.py`），嵌入模型优先使用火山 ARK `doubao-embedding-large`，不可用时自动降级到本地 `paraphrase-multilingual-MiniLM-L12-v2`。

**无结果时**：返回 `[{"result": "NO_RELEVANT_EVIDENCE"}]`

---

### A08 相关性与证据质量判断（`retrieval/evidence_quality_judge.py`）

**职责**：对检索结果进行 LLM 二次评估，过滤低相关证据，标记过期和冲突。

**判断维度**：relevance（0-1）、is_stale、conflict_with、final_support_level

**规则**：
- relevance < 0.4 的证据不进入最终结果
- 有 source_id 的证据最低为 `low`（不标 unverified）
- 冲突证据进入 conflict_report，不过滤（由上层决策）

**LLM 失败时 fallback**：所有证据以 relevance=0.7、support_level=medium 通过

---

### A09 会前上下文包生成器（`ingestion/meeting_context.py`）

**职责**：围绕一个会议 ID 生成背景包，供 B 端生成会前卡片。

**生成内容**：background_facts（3-5条）、last_decisions、open_risks、pending_questions

**关键设计**：在 LLM prompt 中直接注入 Risk/Blocker 类型原子（而非仅靠检索），确保 Open Risks 描述具体，不出现"存在若干风险"这类模糊表达。

**输出**：包含 evidence_ids 和 conflict_report，供 B 端回传效果数据。

---

### A10 Action Item 抽取与字段补齐（`atoms/action_item_extractor.py`）

**职责**：从会议纪要或群聊中识别行动项，补齐负责人、截止日期、优先级。

**字段补全策略**：
1. LLM 从 transcript 文本抽取
2. **deadline 兜底**：LLM 漏抓时，按标题相似度（字符集合 Jaccard > 0.3）匹配 `action_items_raw` 原始数据补齐
3. 负责人缺失时 needs_confirmation=True

**重复检测**：标题字符集合重叠 > 0.6 时提示可能重复。

**当前 minutes_alpha_review 结果**（5条）：

| 序号 | 待办 | 负责人 | 截止 |
|---|---|---|---|
| 001 | 完成测试环境权限开通 | user_ops | 2026-04-24 |
| 002 | 权限开通后验证环境可用 | user_qa | 2026-04-24 |
| 003 | 完成 P0 接口联调 | user_rd | 2026-04-28 |
| 004 | 提交接口压测报告 | user_qa | 2026-04-30 |
| 005 | 更新里程碑文档 | user_pm | 2026-04-22（兜底补全）|

---

### A11 周报时间窗口聚合器（`ingestion/weekly_aggregator.py`）

**职责**：以一周为窗口聚合进展、风险、洞察。

**输出**：progress_summary、risk_summary、key_insights（每条 ≤120 字）、evidence_ids

**周计算**：使用 `datetime.fromisocalendar()` 保证 ISO 8601 标准周（如 2026-W17 = 04-20 ~ 04-26）。

**区分**：本周新增 vs 历史遗留（通过 evidence timestamp 过滤）。

---

### A12 评测数据与指标引擎（`evaluation/metrics_engine.py`）

**职责**：计算效果验证指标，输出评测报告。

**指标与目标**：

| 指标 | 目标阈值 |
|---|---|
| Citation Accuracy | ≥ 90% |
| Evidence Coverage | ≥ 85% |
| Action Item Precision | ≥ 85% |
| Action Item Recall | ≥ 85% |
| Hallucination Rate | ≤ 5% |

**黄金数据集**：默认从 `fixtures/golden/demo_alpha.json` 加载，含 5 条标准 Action Item 和 3 个案例分析。

**报告输出**：`outputs/demo/eval_report_{timestamp}.json`

---

## 五、中央引擎（`app/engine.py`）

**职责**：编排 A01→A06 的完整构建流程，管理磁盘缓存，供 API 和 CLI 复用。

### 增量构建流程

```
build(incremental=True)
  ├── 加载 manifest（所有 source 元信息）
  ├── 对每个 source：
  │   ├── 若 updated_at 未变 → 从缓存加载，跳过 LLM 调用
  │   └── 若 updated_at 变化 → 重新 parse → build_index → extract_atoms
  ├── build_graph（全量重建，因为图依赖所有原子）
  ├── build_vector_index（嵌入 evidence_store 所有证据，保存 vectors.npy）
  ├── 保存缓存（atoms.json, indexes.json, graph.json, evidence_store.json）
  └── 保存 source_timestamps.json（用于下次增量判断）
```

### 磁盘缓存（`outputs/cache/`）

| 文件 | 内容 |
|---|---|
| `meta.json` | tenant_id, project_id |
| `manifest.json` | source 元信息列表 |
| `atoms.json` | 所有知识原子 |
| `evidence_store.json` | evidence_id → Evidence 对象 |
| `indexes.json` | 各 source 的叶子节点（summary + chunk）|
| `graph.json` | 图节点和边（不含 evidence_store）|
| `source_timestamps.json` | source_id → updated_at（增量判断用）|
| `vectors/vectors.npy` | 所有证据的嵌入向量（float32，L2 归一化）|
| `vectors/vector_evidence_ids.json` | 向量行与 evidence_id 的对应关系 |

**`get_engine()`**：单例模式，优先从磁盘缓存加载，避免重复 LLM 调用。

---

## 六、LLM 客户端（`app/llm_client.py`）

**模型**：豆包 `doubao-seed-2-0-pro-260215`  
**端点**：`ep-20260423222827-6lcn6`  
**Base URL**：`https://ark.cn-beijing.volces.com/api/v3`

**限速策略**：
- 每次调用间隔 ≥ 1.5 秒（`_MIN_INTERVAL`）
- 遇到 429 自动退避重试，退避时间 5s → 10s → 20s → 40s（上限 60s），最多重试 5 次

**使用日志**：每次调用记录 prompt_name、model、token 用量、耗时、重试次数。

---

## 七、HTTP API（`app/main.py`）

FastAPI 应用，启动时自动加载缓存。

### A-API-01 证据检索
```
POST /evidence/v1/query
```
```json
{
  "trace_id": "trace_demo_001",
  "project_id": "alpha_report_platform",
  "query": "Alpha 项目周会需要关注哪些延期风险？",
  "source_scope": ["docs", "minutes", "messages", "tasks"],
  "top_k": 8
}
```
返回 verified_evidence 列表，含 evidence_id、summary、support_level、confidence、source_url、is_stale。

### A-API-02 会议上下文包
```
POST /evidence/v1/meeting/context-package
```
```json
{"meeting_id": "meeting_alpha_weekly_next", "lookback_days": 14, "include_unfinished_tasks": true}
```
返回 background_facts、last_decisions、open_risks、pending_questions、evidence_ids。

### A-API-03 Action Item 抽取
```
POST /evidence/v1/minutes/action-items
```
```json
{"minutes_id": "minutes_alpha_review", "need_owner_inference": true, "need_deadline_inference": true}
```
返回 action_items 列表（含 owner、deadline、priority、confidence）和 missing_field_report。

### A-API-04 周报聚合
```
POST /evidence/v1/weekly/window-summary
```
```json
{"project_id": "alpha_report_platform", "week_start": "2026-04-20", "week_end": "2026-04-26"}
```
返回 weekly_atoms、progress_summary、risk_summary、key_insights、evidence_ids。

### 其他
- `GET /health` — 健康检查，返回引擎构建状态
- `GET /docs` — FastAPI 自动生成的 Swagger UI

---

## 八、CLI 命令（`app/cli.py`）

运行方式：`python -m app <command>`

| 命令 | 说明 |
|---|---|
| `seed-demo-data` | 列出所有 fixture source，验证数据就绪 |
| `build-index` | 构建/增量更新索引、原子、图谱，保存缓存 |
| `query --q <查询>` | 检索证据并打印结果 |
| `meeting-context --meeting-id <id>` | 生成会前上下文包 |
| `extract-actions --minutes-id <id>` | 从会议纪要抽取 Action Items |
| `weekly-window --week <2026-W17>` | 聚合指定周的知识窗口 |
| `evaluate [--dataset <path>]` | 运行评测指标 |

**Windows 编码**：`__main__.py` 在 win32 下将 stdout/stderr 强制设为 UTF-8，避免 GBK 报错。

---

## 九、Fixture 数据（`fixtures/`）

场景背景：**Alpha 智能报表平台**，处于 P0 联调阶段（2026-04-20 ~ 2026-04-28）。

| 文件 | 内容摘要 |
|---|---|
| `docs/alpha_prd.json` | PRD v2.3，含项目背景、功能需求、权限模块、接口设计、里程碑、风险说明 |
| `minutes/alpha_weekly_review.json` | 2026-04-21 周会纪要，含议题、逐字发言、2条决议、5条 Action Item |
| `messages/alpha_group_thread.json` | 群聊 12 条消息，记录权限问题跟进和 Action Item 确认过程 |
| `tasks/alpha_tasks.json` | 6 个任务，含状态、负责人、截止日期、评论、延期原因 |
| `calendar/alpha_meetings.json` | 2 个会议事件（本次周会 + 下次周会） |
| `permissions/permission_policy.yaml` | 5 个用户、6 个 source 的权限策略 |
| `events/minutes_created.json` | 会议纪要创建事件（用于事件触发式入库演示）|

**核心业务场景**：测试环境权限未开通 → 接口联调延期 2 天 → P0 里程碑受影响，这条因果链贯穿所有 fixture。

---

## 十、接口合约（`contracts/`）

B 端调用 A 端前须参照这里的请求样例，确保字段一致：

| 文件 | 对应接口 |
|---|---|
| `b_to_a_query_request.json` | `/evidence/v1/query` |
| `premeeting_context_request.json` | `/evidence/v1/meeting/context-package` |
| `minutes_action_items_request.json` | `/evidence/v1/minutes/action-items` |
| `weekly_window_request.json` | `/evidence/v1/weekly/window-summary` |

---

## 十一、测试（`tests/`）

共 **21 个测试**，全部通过。

| 文件 | 测试内容 |
|---|---|
| `test_a01_adapter.py` (6) | fixture 读取、跨租户拦截、manifest 字段完整性 |
| `test_a02_permission.py` (6) | 权限过滤、跨租户拦截、缺 tenant_id 异常、外部用户拦截 |
| `test_a03_parser.py` (5) | PRD 标题层级、会议纪要议题/决议、任务解析、full_text 覆盖关键词 |
| `test_contracts.py` (4) | 合约文件字段完整性、日期格式有效性 |

运行：`pytest tests/ -v`

---

## 十二、依赖（`requirements.txt`）

```
openai>=1.0.0       # 调用豆包 API（OpenAI 兼容接口）
fastapi>=0.110.0    # HTTP API 框架
uvicorn[standard]   # ASGI 服务器
pydantic>=2.0.0     # 数据校验
pyyaml>=6.0         # 权限策略解析
click>=8.1.0        # CLI 框架
httpx>=0.27.0       # HTTP 客户端
pytest>=8.0.0       # 测试框架
jieba>=0.42.1       # 中文分词（BM25 检索质量提升）
sentence-transformers>=2.7.0  # 本地嵌入模型（语义检索 fallback）
numpy>=1.24.0       # 向量运算（RRF 融合、余弦相似度）
```

---

## 十三、快速启动

```powershell
# 进入项目目录
cd C:\Users\Sun06\Desktop\omni-desk\openclaw-knowledge-evidence-engine

# 安装依赖（已完成）
pip install -r requirements.txt

# 验证数据
python -m app seed-demo-data

# 构建索引（首次需要，后续增量）
python -m app build-index

# 运行 CLI 命令
python -m app query --q "Alpha 项目有哪些延期风险？"
python -m app meeting-context --meeting-id meeting_alpha_weekly_next
python -m app extract-actions --minutes-id minutes_alpha_review
python -m app weekly-window --week 2026-W17
python -m app evaluate

# 启动 API 服务（访问 http://localhost:8000/docs）
uvicorn app.main:app --reload --port 8000

# 运行测试
pytest tests/ -v
```

---

## 十四、已知局限

1. **无真实飞书 API 接入**：A01 仅支持 fixture 模式，对接真实飞书需实现 `load_source` 的网络请求版本。
2. **无 OpenClaw 插件**：未注册 OpenClaw webhook，无法作为飞书内置智能体触发。
3. **无子系统 B**：卡片推送、任务创建预览、Dashboard 不在本子系统范围内。
4. **TPM 限制**：`build-index` 受豆包接入点 TPM 上限影响，已有限速+重试机制，但大规模数据仍需关注。
5. **嵌入模型**：火山 ARK `doubao-embedding-large` 当前 404（接入点未开通嵌入权限），已自动降级为本地 `paraphrase-multilingual-MiniLM-L12-v2`，语义检索功能正常，但首次构建需下载 ~471MB 模型文件。
