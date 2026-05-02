# OpenClaw Knowledge Evidence Engine Subsystem Plan

> 中文名称：子系统 A：知识接入、索引与证据引擎  
> 英文名称：OpenClaw Knowledge Evidence Engine  
> 适合负责角色：开发者 A  
> 并行开发定位：先独立完成数据、索引、证据、Action Item 抽取和评测底座，再通过标准 API 向子系统 B 提供证据服务。

## 1. 文档目标

本项目基于前一版 Team Knowledge Pulse Agent 方案继续拆分与增强。项目主方向为飞书 OpenClaw 赛道的“会议与项目的全链路伴侣”，同时融合“周期性智能总结与洞察”和“团队待办中枢与进展自动对账”。最终作品不是一个普通聊天 Bot，而是一个能够主动读取飞书 Docs、Minutes、消息、任务、日历和多维表格，并把分散信息转化为可引用、可追踪、可推送、可执行知识产物的办公 Agent。

本文件只描述子系统 A。子系统 A 的核心职责是把飞书生态中的原始办公数据转化为可信证据和可分发知识原子。它不负责最终卡片样式、不负责飞书群推送、不负责创建任务的写入动作，也不负责最终 Demo 的交互页面。它的交付结果应该像一个“证据 API 服务”：任何上层 Agent 想生成卡片、创建任务、写周报，都必须先向它索取可追溯证据。

## 2. 子系统 A 的边界

### 2.1 负责内容

- 飞书 Docs、Minutes、消息、任务、日历、多维表格等数据的只读接入与本地模拟数据加载。
- 权限与租户隔离校验，确保只返回授权范围内的数据。
- 文档、会议纪要、群聊线程和任务快照的结构化解析。
- PageIndex 树索引、节点摘要、文档描述和知识原子抽取。
- Evidence Graph 构建，记录事实、决议、风险、待办、阻塞和来源之间的关系。
- 多源检索、证据相关性判断、时效性判断、冲突判断和引用支持判断。
- 会前上下文包、Action Item 列表、周报素材包的 API 输出。
- 准确性评测、引用评测、待办抽取评测和效率对比数据生成。

### 2.2 不负责内容

- 不负责飞书卡片视觉样式。
- 不负责将卡片推送到飞书群。
- 不负责真正创建飞书任务或更新多维表格。
- 不负责 OpenClaw 对话入口和 Demo Dashboard。
- 不负责点击率、确认率等用户交互埋点采集，但需要提供 evidence_id 方便子系统 B 回传效果数据。

## 3. 场景定义文档：子系统 A 视角

子系统 A 服务于“会议与项目协作知识流转”场景。目标用户包括项目经理、产品经理、研发、测试、运营和团队负责人。它解决的不是“生成漂亮文字”，而是保证所有知识产物都有可信依据。比如会前卡片中的“测试环境权限导致联调延期”不能来自模型猜测，而必须来自任务评论、群聊讨论或会议纪要中的可点击来源。

通用搜索无法满足该场景，因为用户往往不知道应该搜索哪个关键词，也不知道哪条消息是最终结论。普通问答也不够，因为它只能回答用户主动提出的问题，不能自动为即将发生的会议准备背景证据，也不能主动发现任务延期风险。子系统 A 的核心价值是将原始飞书数据加工成高密度、可引用、可验证、可被上层主动分发的知识单元。

## 4. 总体架构

子系统 A 建议采用 FastAPI + 本地 JSON/SQLite + 可替换向量索引 + LLM 调用管理器的结构。比赛阶段可以先用本地 JSON fixtures 模拟飞书数据，保证没有真实飞书权限时仍能完成 Demo。后续接入 OpenClaw 或飞书 CLI 时，只需要替换 A01 数据读取适配器，不影响后续索引和检索模块。

数据流如下：

1. A01 读取飞书对象或本地 fixture。
2. A02 根据用户、群、空间、文档权限过滤数据。
3. A03 将文档、会议、消息、任务解析为统一结构。
4. A04 构建 PageIndex 树、节点摘要和文档描述。
5. A05 抽取知识原子，绑定 evidence_id。
6. A06 构建 Evidence Graph。
7. A07 根据场景查询进行多源检索。
8. A08 过滤、打分、冲突检测和引用支持判断。
9. A09/A10/A11 输出会前上下文、行动项和周报素材。
10. A12 为效果验证报告输出评测指标。

## 5. API 合约

### A-API-01 证据检索接口

- 路径：`/evidence/v1/query`
- 说明：供 B 端生成会前卡片、周报和风险预警前获取证据。

请求示例：

```json
{
  "trace_id": "trace_demo_001",
  "project_id": "alpha_report_platform",
  "query": "Alpha 项目周会需要关注哪些延期风险？",
  "source_scope": [
    "docs",
    "minutes",
    "messages",
    "tasks"
  ],
  "top_k": 8
}
```

响应示例：

```json
{
  "code": 200,
  "data": {
    "verified_evidence": [
      {
        "evidence_id": "ev_001",
        "summary": "接口联调延期 2 天，原因是测试环境权限未开通。",
        "support_level": "high",
        "confidence": 0.92
      }
    ]
  }
}
```

### A-API-02 会议上下文包接口

- 路径：`/evidence/v1/meeting/context-package`
- 说明：供 B 端会前背景卡片调用。

请求示例：

```json
{
  "meeting_id": "meeting_alpha_weekly",
  "lookback_days": 14,
  "include_unfinished_tasks": true
}
```

响应示例：

```json
{
  "code": 200,
  "data": {
    "background_facts": [
      "本周需求文档新增权限校验章节。"
    ],
    "last_decisions": [
      "接口字段暂不下线。"
    ],
    "open_risks": [
      "测试环境权限未开通。"
    ],
    "evidence_ids": [
      "ev_doc_001",
      "ev_task_003"
    ]
  }
}
```

### A-API-03 Action Item 抽取接口

- 路径：`/evidence/v1/minutes/action-items`
- 说明：供 B 端会后任务创建预览调用。

请求示例：

```json
{
  "minutes_id": "minutes_alpha_review",
  "need_owner_inference": true,
  "need_deadline_inference": true
}
```

响应示例：

```json
{
  "code": 200,
  "data": {
    "action_items": [
      {
        "item_id": "ai_001",
        "title": "补充接口压测报告",
        "owner": "user_rd",
        "deadline": "2026-04-27",
        "evidence_id": "ev_min_011",
        "confidence": 0.88
      }
    ]
  }
}
```

### A-API-04 周报窗口聚合接口

- 路径：`/evidence/v1/weekly/window-summary`
- 说明：供 B 端生成每周洞察卡片和飞书文档。

请求示例：

```json
{
  "project_id": "alpha_report_platform",
  "week_start": "2026-04-20",
  "week_end": "2026-04-24"
}
```

响应示例：

```json
{
  "code": 200,
  "data": {
    "weekly_atoms": [
      "change_doc_permission",
      "risk_env_delay"
    ],
    "progress_summary": "本周重点集中在接口联调和测试环境准备。",
    "risk_summary": "主要风险为测试环境权限和接口字段确认时间。",
    "evidence_ids": [
      "ev_001",
      "ev_002"
    ]
  }
}
```


## 6. 数据模型

### 6.1 KnowledgeSource

```json
{
  "source_id": "doc_alpha_prd",
  "source_type": "docs",
  "title": "Alpha 智能报表平台 PRD",
  "url": "https://example.feishu.cn/docx/xxx",
  "tenant_id": "demo_tenant",
  "project_id": "alpha_report_platform",
  "permission_scope": ["project_alpha_group"],
  "updated_at": "2026-04-24T09:00:00+08:00"
}
```

### 6.2 KnowledgeAtom

```json
{
  "atom_id": "atom_risk_001",
  "atom_type": "Risk",
  "summary": "测试环境权限未开通导致接口联调延期。",
  "owner_candidates": ["user_qa", "user_rd"],
  "deadline": "2026-04-27",
  "confidence": 0.91,
  "evidence_ids": ["ev_task_003", "ev_msg_007"]
}
```

## 7. 模块详细设计

### A01 飞书只读数据接入适配器

**模块目标：** 封装飞书 Docs、Minutes、消息、任务、日历、多维表格的只读读取能力，并支持本地 fixture 模式。

**输入：**
- tenant_id、user_id、project_id
- source_id 或 fixture_path
- 同步模式 full / incremental / demo

**输出：**
- raw_source_object
- source_manifest.json
- read_trace.json

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 读取 6 类本地 fixture 成功
- 权限失败返回标准错误
- 分页读取 source_count 正确

### A02 权限与租户隔离守卫

**模块目标：** 在所有数据读取和检索前执行租户、用户、群、空间、文档权限过滤，防止跨范围检索和推送。

**输入：**
- user_context
- source_manifest
- permission_policy.yaml

**输出：**
- allowed_source_list
- blocked_source_list
- permission_audit_log

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 跨租户文档被拒绝
- 私聊消息不能进入群推送证据
- 缺失 tenant_id 时拒绝执行

### A03 办公文档与会议解析器

**模块目标：** 将飞书文档、附件、会议纪要和多维表格解析为统一结构化文本，保留标题、表格、评论、发言人和时间戳。

**输入：**
- raw_source_object
- source_type
- parse_config

**输出：**
- structured_document
- structured_minutes
- structured_table

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- PRD 标题层级不丢失
- 会议纪要能抽取议题和结论
- 表格字段能映射为 key-value

### A04 PageIndex 树索引构建器

**模块目标：** 为长文档、长会议纪要和长讨论线程构建 PageIndex 树索引，支持自顶向下检索。

**输入：**
- structured_source
- chunk_size
- overlap_ratio
- max_depth

**输出：**
- pageindex_tree
- node_summary_list
- doc_description

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 叶子 chunk 控制在 500-1000 字
- 摘要不添加原文不存在事实
- 重复构建结果稳定

### A05 知识原子抽取器

**模块目标：** 抽取 Fact、Decision、ActionItem、Risk、Blocker、Change、Question、Insight 等高密度知识原子。

**输入：**
- structured_source
- pageindex_tree
- atom_schema

**输出：**
- knowledge_atom_list
- atom_evidence_map
- atom_confidence_score

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 每个 atom 绑定 evidence_id
- ActionItem 尽量补齐负责人和截止时间
- Risk 必须有风险原因和等级

### A06 Evidence Graph 构建器

**模块目标：** 建立项目、文档、会议、任务、负责人、风险、知识原子之间的关系，支持 B 端生成上下文卡片。

**输入：**
- knowledge_atom_list
- source_manifest
- task_snapshot

**输出：**
- evidence_graph
- entity_relation_list
- project_context_index

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 同一任务在会议和任务系统中能合并
- 同一风险多次出现时能累积证据
- 图谱可 JSON 序列化

### A07 多源检索与证据召回器

**模块目标：** 在 PageIndex 树、知识原子库、任务快照和消息线程中检索与场景相关的证据。

**输入：**
- retrieval_job
- source_scope
- time_window
- top_k

**输出：**
- evidence_chunk_list
- retrieval_trace
- candidate_source_ranking

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 会前问题能检索到上次会议决议
- 风险问题能检索到延期任务和阻塞讨论
- 空结果返回 NO_RELEVANT_EVIDENCE

### A08 相关性与证据质量判断器

**模块目标：** 对检索结果进行相关性、时效性、冲突性、来源可靠性和引用支持判断。

**输入：**
- evidence_chunk_list
- query
- scenario_type

**输出：**
- verified_evidence_list
- conflict_report
- evidence_quality_score

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 无来源结论不得进入 verified_evidence
- 过期证据标记 stale
- 冲突事实进入 conflict_report

### A09 会前上下文包生成器

**模块目标：** 围绕一个会议事件聚合历史会议、相关文档、未完成任务、最近风险和待确认问题。

**输入：**
- meeting_id
- calendar_event
- attendee_list
- lookback_days

**输出：**
- meeting_context_package
- background_facts
- open_risks
- pending_questions

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 能识别会议主题关联文档
- 能提取上次会议未关闭事项
- 输出 3-5 条高密度背景

### A10 Action Item 抽取与字段补齐器

**模块目标：** 从会议纪要和群聊中识别待办事项，补齐负责人、截止时间、优先级、来源链接和置信度。

**输入：**
- minutes_id
- message_thread
- owner_dict
- project_calendar

**输出：**
- action_item_list
- missing_field_report
- duplicate_candidate_list

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- Action Item Precision 目标 >= 85%
- 没有负责人时标记需要确认
- 相似任务提示可能重复

### A11 周报时间窗口聚合器

**模块目标：** 以一周为窗口聚合文档变化、会议结论、任务进度、风险点和群聊讨论，生成 B 端可消费的周报素材。

**输入：**
- project_id
- week_start
- week_end
- source_scope

**输出：**
- weekly_atom_list
- progress_summary
- risk_summary
- evidence_ids

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 区分本周新增与历史遗留
- 任务延期信息必须有来源
- 每个 insight 不超过 120 字

### A12 评测数据与指标引擎

**模块目标：** 为效果验证报告提供准确性、引用支持、待办抽取和效率对比指标。

**输入：**
- golden_dataset
- agent_outputs
- human_baseline_log

**输出：**
- evaluation_report_json
- metric_table
- case_analysis

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- Citation Accuracy 可计算
- Action Item Precision/Recall 可计算
- Time Saving 可与人工基线对比


## 8. 可运行 Demo：子系统 A 独立演示

子系统 A 的 Demo 不以卡片推送为主，而是展示“证据引擎可以独立工作”。建议提供以下 CLI：

```bash
make seed-demo-data
make build-index
python -m tkp_a query --q "Alpha 项目周会需要关注哪些延期风险？"
python -m tkp_a meeting-context --meeting-id meeting_alpha_weekly
python -m tkp_a extract-actions --minutes-id minutes_alpha_review
python -m tkp_a weekly-window --project alpha_report_platform --week 2026-W17
python -m tkp_a evaluate --dataset demo_alpha
```

主动触发方式采用“事件触发式入库”。当 `fixtures/events/minutes_created.json` 出现会议纪要创建事件时，子系统 A 自动读取纪要、解析结构、抽取 Action Items、更新证据图谱，并在 `outputs/events/` 生成可被子系统 B 订阅的 `action_items_ready` 事件。

## 9. 测试方案

### 9.1 单元测试

- A01：读取本地 fixture，校验 source_count、source_type、updated_at。
- A02：模拟无权限文档、跨群文档、私聊消息，确认过滤正确。
- A03：解析 PRD、会议纪要和多维表格，确认结构字段完整。
- A04：构建 PageIndex 树，确认 node_count、tree_depth、summary 不为空。
- A05：抽取知识原子，确认 atom_type、evidence_ids、confidence 不为空。
- A08：输入无关证据，确认被过滤；输入冲突证据，确认 conflict_report 生成。

### 9.2 合约测试

- 使用 `tests/contracts/b_to_a_query_request.json` 测试 `/evidence/v1/query`。
- 使用 `tests/contracts/premeeting_context_request.json` 测试会议上下文包。
- 使用 `tests/contracts/minutes_action_items_request.json` 测试 Action Item 抽取。
- 使用 `tests/contracts/weekly_window_request.json` 测试周报素材聚合。

### 9.3 效果评测

- Citation Accuracy：目标 >= 90%。
- Evidence Coverage：目标 >= 85%。
- Action Item Precision：目标 >= 85%。
- Action Item Recall：目标 >= 85%。
- Hallucination Rate：目标 <= 5%。

## 交付物要求落地说明

### 1. 场景定义文档

场景定义文档需要说明选择的知识场景、目标用户、核心价值，以及为什么通用搜索或普通问答无法满足。本文档要求在开发阶段就把场景定义拆到每个模块和每条测试链路中，而不是等 Demo 完成后再补材料。最终文档必须明确：本项目主方向是方向 B，会前、会中、会后围绕会议与项目协作做全链路知识服务；方向 A 是周期性周报和风险洞察增强；方向 D 是任务自动对账和推进表增强。

验收标准：
- 明确目标用户：项目经理、产品经理、研发、测试、运营和团队负责人。
- 明确核心价值：知识主动到达、事实可追溯、任务可闭环、风险可预警。
- 明确普通搜索不足：搜索要求用户知道关键词，但会议与项目协作中的关键知识经常是用户“不知道自己应该知道什么”。
- 明确普通问答不足：问答需要用户主动提问，不能在会前自动推送背景，不能在会后自动创建任务，也不能周期性发现风险。

### 2. 可运行 Demo

Demo 必须基于 OpenClaw/CLI 或飞书生态能力实现主动知识服务，至少包含一种主动触发方式。推荐保留三类触发：定时触发、事件触发和阈值触发。所有写操作必须优先进入 dry-run 预览，避免误写真实飞书空间。

验收标准：
- 能通过 CLI 或 OpenClaw 指令启动会前背景卡片 Demo。
- 能通过会议纪要事件触发会后 Action Items 任务预览。
- 能通过定时任务生成每周风险洞察和重点事项推进结果。
- 卡片、任务、周报中的关键事实必须携带 evidence_id 或 source_url。
- Demo 过程必须保存 trace_id，便于答辩时解释 Agent 决策链路。

### 3. 效果验证报告

效果验证报告需要自证知识产物的准确性、用户接受度和效率提升。准确性来自证据支持率、幻觉率、Action Item Precision/Recall；用户接受度来自卡片点击率、任务确认率、用户评分；效率提升来自人工整理耗时与 Agent 自动生成耗时对比。

验收标准：
- 至少定义人工搜索、普通 LLM 摘要、本项目方案三种对照。
- 至少包含 Citation Accuracy、Hallucination Rate、Action Item Precision、Action Item Recall、Card Click Rate、Task Confirmation Rate、Time Saving 七项指标。
- 至少包含三个案例分析：会前背景、会后任务、周报风险。
- 报告必须说明失败样例和下一步优化方向。

## 10. 与子系统 B 的合并联调准备

- 在 `contracts/` 目录中冻结 API 请求和响应样例。
- 每个响应都携带 trace_id，B 端推送卡片后必须回传 card_id 和 feedback_event。
- A 端提供 mock server，B 端不需要等待 A 端真实接入飞书即可开发。
- A 端提供 `outputs/demo/*.json`，B 端可以直接作为本地输入。
- 联调第一阶段只做 dry-run，不写入真实飞书。
- 联调第二阶段只允许写入测试群、测试任务和测试多维表格。

## 11. 推荐目录结构

```text
openclaw-knowledge-evidence-engine/
  app/
    main.py
    connectors/
    ingestion/
    indexing/
    atoms/
    graph/
    retrieval/
    evaluation/
    security/
  contracts/
  fixtures/
  outputs/
  tests/
  README.md
  Makefile
```

## 12. 阶段计划

- P0：完成 fixtures、A01-A04、索引构建和基础检索。
- P1：完成知识原子、证据图谱、Action Item 抽取。
- P2：完成会前上下文包、周报窗口聚合和证据质量判断。
- P3：完成评测脚本、mock server、合约测试和联调文档。

## 13. 最终验收标准

子系统 A 可以在没有子系统 B 的情况下独立运行，并输出可被人工检查的证据、知识原子、行动项和评测报告。它也可以在没有真实飞书权限的情况下，通过 fixtures 完成全流程 Demo。只要 B 端按照接口调用，就能直接获得可用于卡片、任务和周报的证据材料。
