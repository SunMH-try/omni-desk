# OpenClaw AB Subsystem API Specification

> 项目英文名：**Team Knowledge Pulse Agent**
> 中文名称：**知脉 Agent / 团队知识脉冲助手**
> 文档用途：双人并行开发、接口联调、OpenClaw/CLI Demo 接入、比赛交付物验证、后续合并测试。
> 版本：**V1.0**
> 适用范围：飞书 OpenClaw 赛道 - 企业办公知识整合与分发 Agent。
> 本接口文档按照“算法端接口文档 v1.0”的服务拆分、统一响应、异步任务、SSE 事件流和前后端解耦思路扩展而来。原接口文档中服务 A 负责入库，服务 B 负责智能体对话；本项目进一步拆分为 A：Knowledge Evidence Engine 与 B：Proactive Distribution Agent。

## 0. 文档结论与开发分工
本项目建议保持两个算法服务独立部署、独立测试、独立 mock、独立日志，但共享同一套 `tenant_id / workspace_id / project_id / source_id / evidence_id / trace_id` 追踪字段。这样两名开发者可以并行推进：一名负责子系统 A 的数据接入、知识原子、证据检索与评测底座；另一名负责子系统 B 的主动触发、卡片生成、任务闭环、OpenClaw/CLI Demo 与用户反馈。

### 0.1 子系统边界
| 子系统 | 服务名 | 建议端口 | 主要职责 | 可独立测试目标 |
|---|---|---:|---|---|
| A | Knowledge Evidence Engine | 8100 | 飞书多源同步、文档/纪要/消息/任务结构化、PageIndex 树索引、Knowledge Atom 抽取、Evidence Graph、证据检索、引用校验、评测集导出 | 给定飞书模拟数据或本地 JSON，能返回可引用证据和知识原子 |
| B | Proactive Distribution Agent | 8200 | OpenClaw/CLI 对话入口、主动触发器、会前卡片、会后 Action Items、周报洞察、风险预警、飞书卡片/任务/多维表格写入、SSE 推送 | 给定 A 的 mock 证据接口，能生成预览卡片、任务创建预览、SSE Demo 流 |
| C | Integration & Evaluation Layer | 8300（可选） | 联调监控、效果验证、指标看板、回放测试、评测报告生成 | 非必须独立服务，也可作为 A/B 的内部模块 |

### 0.2 为什么不是继续沿用原来的 A/B 命名
原算法端接口文档的 A/B 划分是“知识库入库服务 + Agent 智能体服务”，适合私有文档问答与报告生成。本比赛项目的核心是企业办公知识整合与分发，因此需要把 A 扩展成“证据引擎”，不仅处理文档，还处理飞书 Docs、Minutes、群聊、任务、日历、多维表格；把 B 扩展成“主动分发 Agent”，不仅回答问题，还要定时、事件、阈值触发主动服务。

### 0.3 接口文档增强点
- 把原有文档入库接口扩展为飞书多源同步接口，支持 docs/minutes/messages/tasks/calendar/bitable/file 六类 source_type。
- 把原有 PageIndex 结果扩展为 Evidence Chunk、Knowledge Atom、Evidence Graph 三层对象，支持后续卡片引用和效果评测。
- 把原有 B1 对话 SSE 扩展为场景驱动 SSE，支持 pre_meeting_brief、post_meeting_action_items、weekly_insight、risk_alert、todo_reconciliation、knowledge_qa。
- 新增分发类接口：卡片预览、卡片推送、任务创建预览、任务写入、多维表格更新、飞书文档沉淀。
- 新增主动触发接口：定时触发、事件触发、阈值触发、手动 CLI 触发，并统一进入 trigger_context。
- 新增效果验证接口：引用准确率、Action Item 召回率、点击率、确认率、任务完成率、人工节省时间。
- 所有写操作必须支持 dry_run=true；真实写飞书前必须有人审或显式确认。
- 所有生成结论必须支持 evidence_id 追溯，不允许无证据事实直接进入卡片。

## 1. 总体架构与调用关系
本接口方案采用“后端/CLI/OpenClaw 只做状态转发，算法端完成场景理解与执行规划”的设计原则。后端不判断用户意图，只把前端状态、飞书事件、日历事件、任务事件或 CLI 命令如实传入 B；B 判断场景后调用 A 获取证据，生成知识产物，再由 B 调用飞书写入工具或返回 dry_run 预览。

### 1.1 推荐服务拓扑
```text

[Feishu Docs / Minutes / Messages / Tasks / Calendar / Bitable]
                 │
                 ▼
[Backend or CLI or OpenClaw Runtime]
                 │
                 ├── sync/import ─────▶ Service A: Knowledge Evidence Engine :8100
                 │                         ├─ Source Sync
                 │                         ├─ PageIndex / ThreadIndex / TaskSnapshot
                 │                         ├─ Knowledge Atom Extractor
                 │                         ├─ Evidence Graph
                 │                         └─ Evidence Retrieval & Validation
                 │
                 └── chat/trigger ────▶ Service B: Proactive Distribution Agent :8200
                                           ├─ Scenario Router
                                           ├─ Trigger Engine
                                           ├─ Card / Report / Task Generator
                                           ├─ Human Review & Confirmation
                                           ├─ Feishu Push / Task / Bitable Writer
                                           └─ SSE Stream / Feedback / Effect Metrics

```

### 1.2 A/B 服务内部依赖
- B 不直接读取 PostgreSQL，不直接遍历 PageIndex 树，而是通过 A 的 `/evidence/v1/retrieval/search`、`/evidence/v1/atoms/query`、`/evidence/v1/references/validate` 获取证据。
- A 不负责飞书卡片样式、不创建飞书任务、不决定推送对象；这些由 B 的分发策略和写入接口处理。
- A 可以在本地无飞书环境时使用 `local_mock` 数据源独立测试；B 可以在 A 未完成时使用 `mock_evidence=true` 独立测试。
- A/B 之间所有对象通过 JSON 传递，不依赖 Python 内存对象，便于后续 Docker Compose 或远程部署。

## 2. 通用协议约定
### 2.1 请求头
| Header | 必填 | 示例 | 说明 |
|---|---|---|---|
| Content-Type | 是 | `application/json` | 所有 JSON 接口统一使用。 |
| Accept | 否 | `application/json 或 text/event-stream` | SSE 接口建议显式声明 text/event-stream。 |
| X-Api-Key | 否/P1 必填 | `svc_xxx` | 服务间鉴权。比赛 Demo 可关闭，正式联调应启用。 |
| X-Request-Id | 否 | `req_20260424_xxx` | 调用方生成，便于前后端、A/B、飞书回调串联日志。 |
| X-Dry-Run | 否 | `true` | 写操作默认 dry_run=true，可与请求体 dry_run 双重控制。 |

### 2.2 通用响应结构
```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "request_id": "req_xxx",
  "trace_id": "trace_xxx"
}
```
通用响应结构继承原接口文档的 `code/message/data` 思路，但新增 `request_id` 和 `trace_id`。`request_id` 代表一次 HTTP 调用，`trace_id` 代表一次完整业务链路，例如一次会前背景卡片从触发到检索到推送的全过程。

### 2.3 通用错误码
| code | error_type | 含义 | 是否可重试 | 处理建议 |
|---:|---|---|---|---|
| 200 | `success` | 成功 | 否 | 继续下游流程 |
| 202 | `accepted` | 异步任务已受理 | 否 | 轮询 status 或等待 callback |
| 400 | `bad_request` | 参数错误或字段缺失 | 否 | 调用方修正请求体 |
| 401 | `unauthorized` | 鉴权失败 | 否 | 检查 X-Api-Key 或飞书授权 |
| 403 | `permission_denied` | 权限不足或越权访问 | 否 | 检查 tenant/workspace/project 权限 |
| 404 | `not_found` | 资源不存在 | 否 | 检查 source_id / session_id / trigger_id |
| 409 | `conflict` | 重复提交或状态冲突 | 视情况 | 幂等处理或等待任务完成 |
| 422 | `validation_failed` | 业务校验失败 | 否 | 检查 evidence 支持、字段枚举、写入权限 |
| 429 | `rate_limited` | 飞书或模型调用限流 | 是 | 指数退避重试 |
| 500 | `internal_error` | 服务内部错误 | 是 | 查看 trace 日志 |
| 503 | `service_unavailable` | 模型、数据库、飞书工具不可用 | 是 | 降级为本地缓存或稍后重试 |

### 2.4 全局字段约定
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 飞书租户 ID 或比赛 Demo 模拟租户 ID，用于数据隔离。 |
| `workspace_id` | string | 是 | 项目空间或知识空间 ID。 |
| `project_id` | string | 建议 | 项目 ID，如 alpha_report_project，用于多项目隔离。 |
| `user_id` | string | 写操作必填 | 触发用户或执行用户 ID。 |
| `session_id` | string | 对话/临时数据必填 | OpenClaw/CLI/前端会话 ID。 |
| `trace_id` | string | 否 | 调用链追踪 ID；不传由服务端生成。 |
| `dry_run` | boolean | 写操作建议必填 | true 表示只生成预览，不真实写飞书。 |
| `created_at` | string | 服务端生成 | ISO 8601 时间。 |

### 2.5 幂等与任务状态
所有异步或写操作接口应支持幂等。调用方可传入 `idempotency_key`，服务端将其与 `tenant_id + workspace_id + operation_type` 组合生成唯一键。重复提交时，如果原任务仍在执行，返回 409；如果原任务已完成，返回原结果摘要。
任务状态统一枚举：`queued / running / waiting_review / waiting_confirm / completed / partial / failed / cancelled / expired`。其中 `waiting_review` 表示已生成预览但等待人工审核，`waiting_confirm` 表示写操作已准备好但未确认执行。

## 3. 共享数据结构 Schema
本章定义 A/B 两个子系统之间必须稳定传递的核心对象。开发时建议直接在 `schemas/shared.py` 中实现这些 Pydantic Model，并由 A/B 两个服务共同引用，避免字段漂移。
### 3.1 EvidenceReference
```json
{
  "evidence_id": "ev_01HXYZ",
  "source_id": "src_doc_prd_001",
  "source_type": "doc",
  "source_name": "Alpha 项目 PRD",
  "node_id": "node_12",
  "node_path": [
    "Alpha 项目 PRD",
    "三、接口设计",
    "3.2 字段变更"
  ],
  "content": "接口 v2 将新增 risk_level 字段，并保留 legacy_status 到下一版本。",
  "summary": "说明接口字段变更和旧字段保留策略。",
  "page_num": 12,
  "message_ts": null,
  "speaker": null,
  "score": 0.91,
  "updated_at": "2026-04-24T09:00:00Z",
  "permission_level": "project_member"
}
```

### 3.2 KnowledgeAtom
```json
{
  "atom_id": "atom_decision_001",
  "atom_type": "Decision",
  "title": "接口 v2 字段保留策略已确认",
  "summary": "本期先保留 legacy_status 字段，下一期再下线。",
  "entities": [
    "接口 v2",
    "legacy_status"
  ],
  "owner_user_ids": [
    "ou_xxx"
  ],
  "due_at": null,
  "confidence": 0.88,
  "valid_until": "2026-06-30T23:59:59Z",
  "evidence_ids": [
    "ev_01HXYZ",
    "ev_01HABC"
  ],
  "suggested_scenarios": [
    "pre_meeting_brief",
    "weekly_insight"
  ]
}
```

### 3.3 TriggerContext
```json
{
  "trigger_id": "trg_weekly_20260424",
  "trigger_type": "scheduled",
  "scenario_type": "weekly_insight",
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "time_window": {
    "start_at": "2026-04-20T00:00:00Z",
    "end_at": "2026-04-24T17:00:00Z"
  },
  "actor_user_id": "ou_pm_001",
  "target_chat_id": "oc_alpha_project",
  "dry_run": true
}
```

### 3.4 DistributionPlan
```json
{
  "plan_id": "dist_001",
  "scenario_type": "pre_meeting_brief",
  "audience": {
    "chat_ids": [
      "oc_alpha_project"
    ],
    "user_ids": [
      "ou_pm_001",
      "ou_rd_002"
    ]
  },
  "channels": [
    "feishu_card",
    "feishu_doc"
  ],
  "urgency": "normal",
  "requires_review": true,
  "reason": "会议将在 30 分钟后开始，存在未闭环任务和接口字段变更。"
}
```

### 3.5 EvaluationMetricRecord
```json
{
  "metric_id": "metric_citation_accuracy_001",
  "scenario_type": "post_meeting_action_items",
  "sample_id": "sample_001",
  "metric_name": "citation_accuracy",
  "score": 0.93,
  "judge_method": "manual_review",
  "notes": "13 条结论中 12 条引用完全支持。"
}
```

## 4. 子系统 A：Knowledge Evidence Engine 接口总览
子系统 A 是整个项目的证据底座，对外暴露飞书多源数据同步、结构化处理、知识原子抽取、证据检索、引用校验、评测集导出等接口。它必须可以在没有子系统 B 的情况下独立运行：开发者只需要准备本地 mock 数据，就能完整验证 source sync、atom extract、retrieval search、reference validate。

**Base URL：** `http://{algo_host}:8100/evidence/v1`

### 4.1 A 接口列表
| 编号 | 方法 | 路径 | 类型 | 说明 |
|---|---|---|---|---|
| A0 | GET | `/health` | 同步 | 健康检查与版本信息 |
| A1 | POST | `/sources/sync` | 异步 | 飞书多源数据同步任务创建 |
| A2 | GET | `/sources/sync/{task_id}/status` | 同步 | 同步/入库任务进度查询 |
| A3 | POST | `/sources/temp-ingest` | 异步 | 会话级临时数据快速入库 |
| A4 | DELETE | `/sources/{source_id}` | 同步 | 删除指定数据源及其索引 |
| A5 | POST | `/index/build` | 异步 | 对已同步数据构建 PageIndex/ThreadIndex/TaskSnapshot |
| A6 | GET | `/index/{source_id}/status` | 同步 | 索引构建状态查询 |
| A7 | POST | `/atoms/extract` | 异步 | 知识原子抽取任务 |
| A8 | POST | `/atoms/query` | 同步 | 按场景查询知识原子 |
| A9 | POST | `/retrieval/search` | 同步 | 多源证据检索 |
| A10 | POST | `/references/validate` | 同步 | 生成结论与引用证据一致性校验 |
| A11 | GET | `/graph/{project_id}` | 同步 | 项目证据图谱查询 |
| A12 | POST | `/eval/dataset/export` | 异步 | 导出效果验证数据集 |
| A13 | GET | `/metrics` | 同步 | 服务指标与调试信息 |

### A0. 健康检查与版本信息
**接口：** `GET /evidence/v1/health`
**调用模式：** 同步接口
**接口职责：** 用于部署、联调、CI 和 Demo 开始前确认服务 A 是否可用，并返回当前模型、数据库、飞书工具、索引版本。
**典型触发：** 后端健康检查、Docker Compose readiness、演示脚本启动前检查。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `service` | string | 服务名称 |
| `version` | string | 接口版本 |
| `status` | string | ok/degraded/down |
| `dependencies` | object | PostgreSQL/Redis/LLM/Feishu CLI 状态 |

#### 请求示例
```bash
curl -X GET http://{algo_host}:8100/evidence/v1/health
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "service": "knowledge-evidence-engine",
    "version": "1.0.0",
    "status": "ok",
    "dependencies": {
      "postgres": "ok",
      "redis": "ok",
      "llm": "ok",
      "feishu_cli": "mock_mode"
    }
  },
  "request_id": "req_health",
  "trace_id": "trace_health"
}
```

#### 测试与验收
- 断开数据库时应返回 degraded 而不是 500。
- 在 mock_mode 下 feishu_cli 可以显示 mock_mode，但接口仍为 200。
- CI 可以使用该接口作为服务启动后的第一条 smoke test。

#### 实现说明
- health 不应触发任何 LLM 调用。
- 建议在响应中返回 git_commit 和 build_time，便于答辩现场追踪版本。

### A1. 飞书多源数据同步任务创建
**接口：** `POST /evidence/v1/sources/sync`
**调用模式：** 异步接口，立即返回 task_id
**接口职责：** 从飞书 Docs、Minutes、Messages、Tasks、Calendar、Bitable 或本地 Mock 文件中同步原始数据，并写入 source_raw 表或本地 JSON 缓存。
**典型触发：** 定时同步、会前背景卡片、周报生成、手动 CLI 导入、比赛 Demo 初始化。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `source_type` | string | 是 | docs/minutes/messages/tasks/calendar/bitable/file/local_mock |
| `source_ids` | array[string] | 否 | 明确指定的数据源 ID；不传时按 filter 拉取 |
| `filter` | object | 否 | 时间窗口、群聊、日历、任务状态等筛选条件 |
| `sync_mode` | string | 否 | full/incremental，默认 incremental |
| `callback_url` | string | 否 | 同步完成回调 |
| `idempotency_key` | string | 否 | 幂等键 |
| `config` | object | 否 | 分页大小、最大条数、是否抓取评论等配置 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 异步任务 ID |
| `status` | string | queued |
| `accepted_source_count` | integer | 已接受的 source 数量 |
| `estimated_seconds` | integer | 预估耗时 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "source_type": "minutes",
  "source_ids": [
    "mins_alpha_review_001"
  ],
  "filter": {
    "start_at": "2026-04-20T00:00:00Z",
    "end_at": "2026-04-24T23:59:59Z",
    "include_comments": true
  },
  "sync_mode": "incremental",
  "callback_url": "http://backend:9000/callbacks/evidence-sync",
  "idempotency_key": "sync_minutes_alpha_20260424",
  "config": {
    "page_size": 50,
    "max_items": 500,
    "store_raw_payload": true
  }
}
```

#### 响应示例
```json
{
  "code": 202,
  "message": "source sync task accepted",
  "data": {
    "task_id": "sync_01HX",
    "status": "queued",
    "accepted_source_count": 1,
    "estimated_seconds": 15
  },
  "request_id": "req_001",
  "trace_id": "trace_001"
}
```

#### 测试与验收
- source_type=local_mock 时必须不依赖飞书授权，便于独立测试。
- 同一个 idempotency_key 重复提交应返回 409 或原 task_id。
- 同步完成后应能在 A2 中看到 processed_items、failed_items 和 source_summary。

#### 实现说明
- 原接口文档 A1 只处理文档入库，本接口把文档扩展为办公多源。
- 同步阶段只负责拉取和保存 raw data，不直接生成最终卡片。

### A2. 同步/入库任务进度查询
**接口：** `GET /evidence/v1/sources/sync/{task_id}/status`
**调用模式：** 同步接口
**接口职责：** 查询 A1/A3 创建的同步任务或临时入库任务状态，供后端轮询或 B 在触发流程中等待。
**典型触发：** 后端轮询、OpenClaw 进度展示、Demo Dashboard 状态栏。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | path string | 是 | 同步任务 ID |
| `include_errors` | query boolean | 否 | 是否返回失败条目明细 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 任务 ID |
| `status` | string | queued/running/completed/partial/failed |
| `progress` | integer | 0-100 |
| `current_step` | string | 当前阶段 |
| `processed_items` | integer | 已处理条目数 |
| `failed_items` | integer | 失败条目数 |
| `sources` | array | 同步出的 source 对象摘要 |

#### 请求示例
```bash
curl -X GET http://{algo_host}:8100/evidence/v1/sources/sync/{task_id}/status
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "sync_01HX",
    "status": "running",
    "progress": 62,
    "current_step": "正在同步会议纪要附件和发言时间戳",
    "processed_items": 31,
    "failed_items": 0,
    "sources": [
      {
        "source_id": "src_mins_001",
        "source_type": "minutes",
        "source_name": "Alpha 需求评审纪要",
        "status": "synced"
      }
    ]
  },
  "request_id": "req_002",
  "trace_id": "trace_001"
}
```

#### 测试与验收
- 处理中必须返回非空 current_step，便于前端显示。
- partial 状态下必须返回 failed_items 和 error_samples。
- 任务完成后 sources 中必须包含 source_id，后续 A5/A7 依赖该字段。

#### 实现说明
- 查询间隔建议 2-5 秒。对于 Demo 可在后台主动推 SSE，但 A 仍需提供轮询接口。

### A3. 会话级临时数据快速入库
**接口：** `POST /evidence/v1/sources/temp-ingest`
**调用模式：** 异步高优先级接口
**接口职责：** 处理用户在 OpenClaw 对话、飞书群或 CLI 中临时上传的文件、粘贴的会议纪要或本地 mock 数据，绑定 session_id，随会话清理。
**典型触发：** 比赛 Demo 临时拖入 PRD、临时导入会议纪要、CLI 指定本地 JSON 数据集。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `session_id` | string | 是 | 会话 ID |
| `temp_source_id` | string | 是 | 临时数据源 ID，由调用方或服务端生成 |
| `source_type` | string | 是 | file/text/minutes/messages/local_mock |
| `payload` | object | 否 | 文本或本地 mock 数据 |
| `file_url` | string | 否 | 文件 URL，与 payload 二选一 |
| `ttl_seconds` | integer | 否 | 临时数据生存时间，默认 86400 |
| `config` | object | 否 | 快速模式配置 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 异步任务 ID |
| `temp_source_id` | string | 临时数据源 ID |
| `status` | string | queued |
| `estimated_seconds` | integer | 预估耗时 |
| `expires_at` | string | 过期时间 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "session_id": "sess_demo_001",
  "temp_source_id": "tmp_minutes_001",
  "source_type": "text",
  "payload": {
    "text": "会议结论：本周先完成接口联调，张三负责测试数据，周五前给出压测报告。"
  },
  "ttl_seconds": 7200,
  "config": {
    "fast_mode": true,
    "summary_enabled": false
  }
}
```

#### 响应示例
```json
{
  "code": 202,
  "message": "temporary source accepted",
  "data": {
    "task_id": "tmp_ingest_01",
    "temp_source_id": "tmp_minutes_001",
    "status": "queued",
    "estimated_seconds": 5,
    "expires_at": "2026-04-24T12:00:00Z"
  },
  "request_id": "req_tmp_001",
  "trace_id": "trace_tmp_001"
}
```

#### 测试与验收
- fast_mode=true 时不应执行耗时的全量文档描述生成。
- session 清理后临时 source 必须不可检索。
- payload 和 file_url 至少有一个非空。

#### 实现说明
- 继承原文档临时入库的高优先级思想，但支持文本、会议和消息数据。

### A4. 删除指定数据源及其索引
**接口：** `DELETE /evidence/v1/sources/{source_id}`
**调用模式：** 同步接口
**接口职责：** 删除 source_raw、PageIndex/ThreadIndex、Knowledge Atom、Evidence Graph 边和评测样本中的关联数据。
**典型触发：** 用户删除文档、session 销毁、Demo 数据重置、重新入库前清理。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `source_id` | path string | 是 | 数据源 ID |
| `tenant_id` | query string | 是 | 租户 ID |
| `workspace_id` | query string | 是 | 工作空间 ID |
| `is_temp` | query boolean | 否 | 是否临时数据 |
| `cascade` | query boolean | 否 | 是否级联删除 atom/graph/eval 数据，默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `source_id` | string | 删除的数据源 ID |
| `deleted_raw_records` | integer | 删除 raw 记录数 |
| `deleted_index_nodes` | integer | 删除索引节点数 |
| `deleted_atoms` | integer | 删除知识原子数 |
| `deleted_graph_edges` | integer | 删除图谱关系数 |

#### 请求示例
```bash
curl -X DELETE http://{algo_host}:8100/evidence/v1/sources/{source_id}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "source deleted",
  "data": {
    "source_id": "src_mins_001",
    "deleted_raw_records": 1,
    "deleted_index_nodes": 38,
    "deleted_atoms": 12,
    "deleted_graph_edges": 25
  },
  "request_id": "req_del_001",
  "trace_id": "trace_del_001"
}
```

#### 测试与验收
- 删除不存在的 source_id 返回 404。
- cascade=false 时只删 raw 与索引，不删人工标注评测结果。
- 重复删除应返回 404 或 deleted=0，不能导致服务异常。

#### 实现说明
- 相当于原文档 A4 文档删除的多源增强版。

### A5. 构建索引
**接口：** `POST /evidence/v1/index/build`
**调用模式：** 异步接口
**接口职责：** 对已同步 source 构建不同索引：文档走 PageIndex，群聊走 ThreadIndex，任务走 TaskSnapshot，会议纪要同时构建 PageIndex 与 ActionItem 候选结构。
**典型触发：** 同步任务完成后自动触发，也可由开发者手动重建索引。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `source_ids` | array[string] | 是 | 待构建索引的数据源 |
| `index_types` | array[string] | 否 | pageindex/threadindex/task_snapshot/calendar_index，默认自动判断 |
| `config` | object | 否 | chunk_size、overlap、max_tree_depth、summary_model 等 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 索引任务 ID |
| `status` | string | queued |
| `source_count` | integer | 数据源数量 |
| `estimated_seconds` | integer | 预估耗时 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "source_ids": [
    "src_doc_prd_001",
    "src_mins_001",
    "src_chat_001"
  ],
  "index_types": [
    "pageindex",
    "threadindex"
  ],
  "config": {
    "max_tree_depth": 4,
    "chunk_size": 800,
    "chunk_overlap": 120,
    "summary_enabled": true,
    "summary_model": "fast-mini"
  }
}
```

#### 响应示例
```json
{
  "code": 202,
  "message": "index build task accepted",
  "data": {
    "task_id": "idx_01",
    "status": "queued",
    "source_count": 3,
    "estimated_seconds": 35
  },
  "request_id": "req_idx_001",
  "trace_id": "trace_idx_001"
}
```

#### 测试与验收
- 不同 source_type 应走不同索引策略。
- PageIndex 每个节点必须包含 node_path 和 summary。
- ThreadIndex 必须把同一话题的群聊消息合并为线程。

#### 实现说明
- 如果 A1 sync 已设置 auto_index=true，可在同步完成后自动触发。

### A6. 索引构建状态查询
**接口：** `GET /evidence/v1/index/{source_id}/status`
**调用模式：** 同步接口
**接口职责：** 查询单个 source 的索引状态、节点数量、摘要数量、可检索状态和最近一次构建错误。
**典型触发：** B 在调用 A9 前可检查目标数据源是否 ready。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `source_id` | path string | 是 | 数据源 ID |
| `tenant_id` | query string | 是 | 租户 ID |
| `workspace_id` | query string | 是 | 工作空间 ID |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `source_id` | string | 数据源 ID |
| `index_status` | string | not_started/running/ready/failed |
| `index_types` | array | 已构建索引类型 |
| `node_count` | integer | 节点数量 |
| `summary_count` | integer | 摘要数量 |
| `last_error` | string|null | 失败原因 |

#### 请求示例
```bash
curl -X GET http://{algo_host}:8100/evidence/v1/index/{source_id}/status
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "source_id": "src_doc_prd_001",
    "index_status": "ready",
    "index_types": [
      "pageindex"
    ],
    "node_count": 126,
    "summary_count": 58,
    "last_error": null
  },
  "request_id": "req_idx_status",
  "trace_id": "trace_idx_001"
}
```

#### 测试与验收
- ready 状态下 node_count 必须大于 0。
- failed 状态必须返回 last_error。
- 不存在 source 返回 404。

#### 实现说明
- 该接口是 A/B 联调时最常用的排障入口之一。

### A7. 知识原子抽取任务
**接口：** `POST /evidence/v1/atoms/extract`
**调用模式：** 异步接口
**接口职责：** 从已索引的文档、会议、群聊、任务中抽取 Fact、Decision、ActionItem、Risk、Blocker、Change、Question、Insight、FAQ 等知识原子。
**典型触发：** 会前背景包、会后任务闭环、周报风险洞察、重点事项对账前置步骤。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `source_ids` | array[string] | 否 | 指定来源 |
| `time_window` | object | 否 | 时间窗口 |
| `atom_types` | array[string] | 否 | 抽取类型，不传则全类型 |
| `config` | object | 否 | 模型、置信度阈值、是否合并重复 atom |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 任务 ID |
| `status` | string | queued |
| `estimated_atoms` | integer | 预估原子数量 |
| `estimated_seconds` | integer | 预估耗时 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "source_ids": [
    "src_mins_001",
    "src_chat_001",
    "src_tasks_001"
  ],
  "atom_types": [
    "Decision",
    "ActionItem",
    "Risk",
    "Blocker",
    "Change"
  ],
  "config": {
    "min_confidence": 0.65,
    "merge_duplicates": true,
    "bind_evidence": true
  }
}
```

#### 响应示例
```json
{
  "code": 202,
  "message": "atom extraction task accepted",
  "data": {
    "task_id": "atom_task_001",
    "status": "queued",
    "estimated_atoms": 35,
    "estimated_seconds": 20
  },
  "request_id": "req_atom_001",
  "trace_id": "trace_atom_001"
}
```

#### 测试与验收
- 每个 atom 至少绑定一个 evidence_id。
- ActionItem 类型必须尝试抽取 owner、deadline、status、source_sentence。
- Risk 类型必须返回 risk_level 和 risk_reason。

#### 实现说明
- 建议将抽取结果保存后再由 B 查询，而不是每次 B 场景触发都重新抽取。

### A8. 按场景查询知识原子
**接口：** `POST /evidence/v1/atoms/query`
**调用模式：** 同步接口
**接口职责：** 根据项目、时间窗口、场景类型和实体条件查询知识原子，为 B 生成卡片提供结构化素材。
**典型触发：** B 生成会前卡片、周报洞察、风险预警、Action Item 表格时调用。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `scenario_type` | string | 否 | pre_meeting_brief/post_meeting_action_items/weekly_insight/risk_alert/todo_reconciliation |
| `atom_types` | array[string] | 否 | 筛选类型 |
| `time_window` | object | 否 | 时间窗口 |
| `entity_filters` | object | 否 | 按模块、负责人、任务、会议筛选 |
| `limit` | integer | 否 | 返回条数，默认 50 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `atoms` | array[KnowledgeAtom] | 知识原子列表 |
| `total` | integer | 总数 |
| `query_summary` | string | 查询解释 |
| `coverage` | object | 按来源统计覆盖情况 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "scenario_type": "weekly_insight",
  "atom_types": [
    "Decision",
    "ActionItem",
    "Risk",
    "Change"
  ],
  "time_window": {
    "start_at": "2026-04-20T00:00:00Z",
    "end_at": "2026-04-24T17:00:00Z"
  },
  "entity_filters": {
    "owner_user_ids": [
      "ou_pm_001"
    ]
  },
  "limit": 20
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "atoms": [
      {
        "atom_id": "atom_risk_001",
        "atom_type": "Risk",
        "title": "接口联调存在延期风险",
        "summary": "测试环境权限未开通，可能影响周五联调。",
        "confidence": 0.87,
        "evidence_ids": [
          "ev_chat_001",
          "ev_task_002"
        ],
        "owner_user_ids": [
          "ou_rd_002"
        ],
        "due_at": "2026-04-25T10:00:00Z"
      }
    ],
    "total": 1,
    "query_summary": "返回本周与 PM 相关的风险和变更",
    "coverage": {
      "minutes": 2,
      "messages": 5,
      "tasks": 3
    }
  },
  "request_id": "req_atom_query",
  "trace_id": "trace_weekly_001"
}
```

#### 测试与验收
- scenario_type=weekly_insight 时应优先返回本周更新或状态变化的 atom。
- 返回 atom 必须包含 evidence_ids。
- limit 超过 100 时应被服务端截断。

#### 实现说明
- B 不需要知道 atom 是从文档、消息还是任务抽取来的，只使用 atom_type 和 evidence_ids。

### A9. 多源证据检索
**接口：** `POST /evidence/v1/retrieval/search`
**调用模式：** 同步核心接口
**接口职责：** 根据自然语言 query、场景上下文和过滤条件，在 PageIndex、ThreadIndex、TaskSnapshot、Knowledge Atom 中检索证据，返回可引用片段。
**典型触发：** B 生成任何事实性卡片、回答、报告、任务建议前必须调用。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `query` | string | 是 | 检索问题或场景描述 |
| `scenario_type` | string | 否 | 用于检索策略路由 |
| `source_types` | array[string] | 否 | 限定 docs/minutes/messages/tasks/calendar/bitable |
| `source_ids` | array[string] | 否 | 限定来源 |
| `time_window` | object | 否 | 时间窗口 |
| `retrieval_config` | object | 否 | top_k/search_mode/rerank/branch_limit 等 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `query_rewritten` | string | 改写后的检索 query |
| `evidence` | array[EvidenceReference] | 证据列表 |
| `atoms` | array[KnowledgeAtom] | 可选返回相关知识原子 |
| `empty_reason` | string|null | 无结果原因 |
| `latency_ms` | integer | 耗时 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "query": "Alpha 项目周会前需要提醒哪些风险、未完成任务和近期变更？",
  "scenario_type": "pre_meeting_brief",
  "source_types": [
    "docs",
    "minutes",
    "messages",
    "tasks"
  ],
  "time_window": {
    "start_at": "2026-04-17T00:00:00Z",
    "end_at": "2026-04-24T10:00:00Z"
  },
  "retrieval_config": {
    "top_k": 8,
    "search_mode": "hybrid",
    "rerank": true,
    "branch_limit": 3,
    "include_atoms": true
  }
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "query_rewritten": "Alpha 项目周会 会前 风险 未完成任务 近期变更",
    "evidence": [
      {
        "evidence_id": "ev_task_002",
        "source_id": "src_tasks_001",
        "source_type": "tasks",
        "source_name": "Alpha 任务列表",
        "node_path": [
          "接口联调",
          "测试环境权限"
        ],
        "content": "测试环境权限仍未开通，任务已延期 2 天。",
        "score": 0.95,
        "updated_at": "2026-04-24T09:30:00Z"
      }
    ],
    "atoms": [
      {
        "atom_id": "atom_risk_001",
        "atom_type": "Risk",
        "title": "接口联调存在延期风险",
        "summary": "测试环境权限未开通，可能影响周五联调。",
        "evidence_ids": [
          "ev_task_002"
        ]
      }
    ],
    "empty_reason": null,
    "latency_ms": 1840
  },
  "request_id": "req_retrieval",
  "trace_id": "trace_pre_meeting"
}
```

#### 测试与验收
- 任何 evidence.content 都必须能回溯到 source_raw 或索引节点。
- 当无结果时不能返回伪造 evidence，应返回 empty_reason。
- 检索 top_k=8 时延迟建议小于 3 秒，便于 Demo 体验。

#### 实现说明
- 这是 A/B 最重要的集成接口。B 的所有生成链路都应优先依赖它。

### A10. 生成结论与引用证据一致性校验
**接口：** `POST /evidence/v1/references/validate`
**调用模式：** 同步接口
**接口职责：** 检查 B 生成的卡片结论、Action Item、风险描述是否被对应证据支持，输出 supported/unsupported/conflict/unclear。
**典型触发：** 卡片推送前、任务创建前、效果验证报告计算 Citation Accuracy 前。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `claims` | array | 是 | 待校验结论列表 |
| `strict_mode` | boolean | 否 | 严格模式，不允许通用知识补充 |
| `config` | object | 否 | 模型、阈值、是否检测冲突 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `validation_results` | array | 逐条校验结果 |
| `overall_status` | string | passed/needs_review/failed |
| `unsupported_count` | integer | 无证据支持数量 |
| `conflict_count` | integer | 冲突数量 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "claims": [
    {
      "claim_id": "c1",
      "text": "接口联调风险来自测试环境权限未开通。",
      "evidence_ids": [
        "ev_task_002",
        "ev_chat_001"
      ]
    },
    {
      "claim_id": "c2",
      "text": "所有后端接口已经完成压测。",
      "evidence_ids": [
        "ev_task_003"
      ]
    }
  ],
  "strict_mode": true,
  "config": {
    "detect_conflict": true,
    "min_support_score": 0.75
  }
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "validation_results": [
      {
        "claim_id": "c1",
        "status": "supported",
        "support_score": 0.91,
        "reason": "证据明确提到测试环境权限未开通导致联调风险。"
      },
      {
        "claim_id": "c2",
        "status": "unsupported",
        "support_score": 0.22,
        "reason": "证据只显示压测报告待补充，不能支持已完成压测。"
      }
    ],
    "overall_status": "needs_review",
    "unsupported_count": 1,
    "conflict_count": 0
  },
  "request_id": "req_validate",
  "trace_id": "trace_pre_push"
}
```

#### 测试与验收
- unsupported 结论不得进入最终推送卡片，除非人工确认并标记为待确认。
- strict_mode=true 时不允许基于常识补全事实。
- 验证结果应进入效果验证指标。

#### 实现说明
- 该接口是控制幻觉和比赛答辩自证准确性的关键。

### A11. 项目证据图谱查询
**接口：** `GET /evidence/v1/graph/{project_id}`
**调用模式：** 同步接口
**接口职责：** 返回项目中的实体、文档、会议、任务、人员、风险、决议之间的关系，用于生成会前背景和答辩展示。
**典型触发：** Demo Dashboard、项目上下文浏览、B 的背景包结构规划。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | path string | 是 | 项目 ID |
| `tenant_id` | query string | 是 | 租户 ID |
| `workspace_id` | query string | 是 | 工作空间 ID |
| `depth` | query integer | 否 | 图谱展开深度，默认 2 |
| `entity` | query string | 否 | 从指定实体开始展开 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `nodes` | array | 图谱节点 |
| `edges` | array | 图谱边 |
| `summary` | string | 图谱概述 |
| `updated_at` | string | 最近更新时间 |

#### 请求示例
```bash
curl -X GET http://{algo_host}:8100/evidence/v1/graph/{project_id}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "nodes": [
      {
        "id": "entity_api_v2",
        "type": "Module",
        "label": "接口 v2"
      },
      {
        "id": "atom_decision_001",
        "type": "Decision",
        "label": "旧字段保留策略"
      }
    ],
    "edges": [
      {
        "source": "atom_decision_001",
        "target": "entity_api_v2",
        "relation": "relates_to",
        "evidence_ids": [
          "ev_mins_001"
        ]
      }
    ],
    "summary": "Alpha 项目当前重点集中在接口 v2、测试环境权限和压测报告。",
    "updated_at": "2026-04-24T09:30:00Z"
  },
  "request_id": "req_graph",
  "trace_id": "trace_graph"
}
```

#### 测试与验收
- 返回 nodes/edges 必须可被前端或 Demo Dashboard 直接渲染。
- depth 过大应被限制，防止返回过量数据。
- 图谱节点必须有 type 和 label。

#### 实现说明
- 比赛答辩中可用图谱说明 Agent 如何理解项目上下文。

### A12. 导出效果验证数据集
**接口：** `POST /evidence/v1/eval/dataset/export`
**调用模式：** 异步接口
**接口职责：** 把指定时间窗口内的证据、知识原子、卡片结论、Action Items 和人工标注导出为评测数据集，用于效果验证报告。
**典型触发：** 比赛交付物中的效果验证报告、人工评估、Baseline 对比。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `scenario_types` | array[string] | 否 | 场景类型列表 |
| `time_window` | object | 是 | 评测窗口 |
| `format` | string | 否 | jsonl/csv/xlsx，默认 jsonl |
| `include_raw_evidence` | boolean | 否 | 是否导出原文片段 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 导出任务 ID |
| `status` | string | queued |
| `estimated_samples` | integer | 预估样本数 |
| `download_url` | string|null | 完成后返回 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "scenario_types": [
    "pre_meeting_brief",
    "post_meeting_action_items",
    "weekly_insight"
  ],
  "time_window": {
    "start_at": "2026-04-20T00:00:00Z",
    "end_at": "2026-04-24T23:59:59Z"
  },
  "format": "jsonl",
  "include_raw_evidence": true
}
```

#### 响应示例
```json
{
  "code": 202,
  "message": "evaluation dataset export accepted",
  "data": {
    "task_id": "eval_export_001",
    "status": "queued",
    "estimated_samples": 80,
    "download_url": null
  },
  "request_id": "req_eval_export",
  "trace_id": "trace_eval"
}
```

#### 测试与验收
- 导出的每条样本必须包含 input、expected/label、evidence_ids、scenario_type。
- 如果 include_raw_evidence=false，也必须保留 evidence_id 以便回查。
- 导出文件应可被 Evaluation Service 或人工评估表直接使用。

#### 实现说明
- 比赛要求自证准确性和效率，本接口为效果报告提供原始数据。

### A13. 服务指标与调试信息
**接口：** `GET /evidence/v1/metrics`
**调用模式：** 同步接口
**接口职责：** 返回 A 服务在指定时间窗口内的调用量、平均耗时、检索命中率、空结果率、引用校验失败率、LLM token 消耗等。
**典型触发：** 性能优化、答辩效果展示、故障排查。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | query string | 否 | 租户 ID |
| `workspace_id` | query string | 否 | 工作空间 ID |
| `project_id` | query string | 否 | 项目 ID |
| `start_at` | query string | 否 | 开始时间 |
| `end_at` | query string | 否 | 结束时间 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `api_calls` | object | 各接口调用量 |
| `latency` | object | p50/p95/p99 |
| `retrieval` | object | 检索指标 |
| `llm_usage` | object | Token 与成本 |
| `errors` | object | 错误统计 |

#### 请求示例
```bash
curl -X GET http://{algo_host}:8100/evidence/v1/metrics
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "api_calls": {
      "retrieval_search": 128,
      "atoms_query": 42
    },
    "latency": {
      "retrieval_p50_ms": 980,
      "retrieval_p95_ms": 2600
    },
    "retrieval": {
      "empty_rate": 0.08,
      "avg_evidence_count": 6.4
    },
    "llm_usage": {
      "prompt_tokens": 128000,
      "completion_tokens": 34000
    },
    "errors": {
      "rate_limited": 2,
      "internal_error": 0
    }
  },
  "request_id": "req_metrics",
  "trace_id": "trace_metrics"
}
```

#### 测试与验收
- 必须支持按 project_id 过滤。
- p95 延迟应能用于判断 Demo 是否卡顿。
- 错误统计需包含 error_type。

#### 实现说明
- 可观测性是工程化加分项，建议保留。

## 5. 子系统 B：Proactive Distribution Agent 接口总览
子系统 B 是面向用户和比赛 Demo 的主动服务层。它接收 OpenClaw 对话、CLI 命令、飞书事件、定时任务和阈值触发，调用 A 取证据，生成卡片、任务、周报、风险预警，并通过 SSE 或飞书写入接口反馈给用户。

**Base URL：** `http://{algo_host}:8200/agent/v1`

### 5.1 B 接口列表
| 编号 | 方法 | 路径 | 类型 | 说明 |
|---|---|---|---|---|
| B0 | GET | `/health` | 同步 | 健康检查与依赖状态 |
| B1 | POST | `/chat/completions` | SSE | OpenClaw/CLI/前端统一对话入口 |
| B2 | POST | `/triggers/register` | 同步 | 注册主动触发规则 |
| B3 | POST | `/triggers/execute` | SSE/异步 | 执行定时/事件/阈值触发 |
| B4 | POST | `/briefs/pre-meeting` | SSE/同步 | 生成会前背景知识卡片 |
| B5 | POST | `/actions/extract` | 同步 | 会议纪要 Action Items 抽取与预览 |
| B6 | POST | `/cards/preview` | 同步 | 飞书卡片预览生成 |
| B7 | POST | `/cards/push` | 同步/异步 | 飞书卡片推送 |
| B8 | POST | `/tasks/preview` | 同步 | 飞书任务创建/更新预览 |
| B9 | POST | `/tasks/commit` | 同步/异步 | 确认后创建/更新飞书任务 |
| B10 | POST | `/insights/weekly` | SSE/异步 | 团队周报与风险洞察生成 |
| B11 | POST | `/risks/alert` | 同步/异步 | 风险预警生成与推送 |
| B12 | POST | `/bitable/sync` | 同步/异步 | 重点事项推进表更新 |
| B13 | POST | `/feedback` | 同步 | 用户反馈与点击/确认记录 |
| B14 | GET | `/runs/{run_id}` | 同步 | 场景运行结果查询 |
| B15 | DELETE | `/cache/{session_id}` | 同步 | 清理会话缓存和临时状态 |
| B16 | POST | `/eval/report` | 异步 | 生成效果验证报告 |

### B0. 健康检查与依赖状态
**接口：** `GET /agent/v1/health`
**调用模式：** 同步接口
**接口职责：** 确认 B 服务、A 服务连通性、飞书写入工具、SSE 能力、触发器调度器是否可用。
**典型触发：** 后端健康检查、演示脚本启动前检查、CI smoke test。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `service` | string | 服务名称 |
| `status` | string | ok/degraded/down |
| `dependencies` | object | A 服务、Redis、scheduler、feishu_writer 状态 |

#### 请求示例
```bash
curl -X GET http://{algo_host}:8200/agent/v1/health
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "service": "proactive-distribution-agent",
    "version": "1.0.0",
    "status": "ok",
    "dependencies": {
      "evidence_engine": "ok",
      "redis": "ok",
      "scheduler": "ok",
      "feishu_writer": "dry_run_only"
    }
  },
  "request_id": "req_b_health",
  "trace_id": "trace_b_health"
}
```

#### 测试与验收
- A 服务不可用时 B 应返回 degraded，并说明 evidence_engine=down。
- dry_run 模式下不应视为失败。
- CI 必须先过 B0 再跑 B1/B4/B10。

#### 实现说明
- B0 可以内部调用 A0，但需要设置短超时，避免健康检查阻塞。

### B1. OpenClaw/CLI/前端统一对话入口
**接口：** `POST /agent/v1/chat/completions`
**调用模式：** SSE 流式接口，兼容非流式
**接口职责：** 继承原接口文档 B1 的统一对话思路，但将 intent 扩展为企业办公知识分发场景。调用方只传用户输入、上下文和状态，不做意图判断。
**典型触发：** OpenClaw 对话框、飞书群 @机器人、CLI 命令、前端测试页面。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话 ID |
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `query` | string | 是 | 用户输入或 CLI 命令 |
| `history` | array | 否 | 对话历史 |
| `stream` | boolean | 否 | 默认 true |
| `scenario_hint` | string | 否 | 可选提示，不强制 |
| `source_scope` | object | 否 | 限定 source_ids/source_types/time_window |
| `runtime_context` | object | 否 | 当前会议、任务、卡片、触发器状态 |
| `generation_config` | object | 否 | 温度、最大 token、模型 |
| `dry_run` | boolean | 否 | 写操作是否只预览，默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `SSE` | text/event-stream | 流式事件；非流式时返回 final_answer/card_preview/task_preview/references |

#### 请求示例
```json
{
  "session_id": "sess_openclaw_001",
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "query": "请为 30 分钟后的 Alpha 项目周会生成会前背景卡片，并指出风险。",
  "history": [],
  "stream": true,
  "scenario_hint": "pre_meeting_brief",
  "source_scope": {
    "source_types": [
      "docs",
      "minutes",
      "messages",
      "tasks"
    ],
    "time_window": {
      "start_at": "2026-04-17T00:00:00Z",
      "end_at": "2026-04-24T10:00:00Z"
    }
  },
  "runtime_context": {
    "calendar_event_id": "cal_alpha_weekly_001",
    "target_chat_id": "oc_alpha_project"
  },
  "generation_config": {
    "temperature": 0.3,
    "max_tokens": 4096
  },
  "dry_run": true
}
```

#### 响应示例
```text
event: stream_start
data: {"run_id":"run_chat_001","session_id":"sess_openclaw_001"}

event: scenario
data: {"scenario_type":"pre_meeting_brief","confidence":0.94}

event: step
data: {"step":"retrieving_evidence","message":"正在检索会议背景、风险和未完成任务..."}

event: card_preview
data: {"card_id":"card_preview_001","title":"Alpha 项目周会会前背景"}

event: references
data: {"references":[{"evidence_id":"ev_task_002","source_name":"Alpha 任务列表"}]}

event: stream_end
data: {"finish_reason":"complete","duration_ms":4200}
```

#### 测试与验收
- query + runtime_context 能触发正确 scenario_type。
- stream=true 必须逐步返回 scenario、step、card_preview、references、stream_end。
- dry_run=true 时不得真实推送飞书卡片。

#### 实现说明
- 该接口保留“后端不做意图判断”的原则。B 内部根据 query/history/runtime_context/source_scope 决定调用 B4/B5/B10 等内部链路。

### B2. 注册主动触发规则
**接口：** `POST /agent/v1/triggers/register`
**调用模式：** 同步接口
**接口职责：** 注册定时、事件或阈值触发规则，用于主动知识服务。
**典型触发：** 每周五周报、会议前 30 分钟提醒、任务延期 2 天风险预警、群聊阻塞关键词阈值。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `trigger_name` | string | 是 | 触发器名称 |
| `trigger_type` | string | 是 | scheduled/event/threshold/manual |
| `scenario_type` | string | 是 | 触发的场景 |
| `schedule` | object | 条件必填 | 定时规则，如 cron/interval |
| `event_filter` | object | 条件必填 | 飞书事件过滤条件 |
| `threshold_rule` | object | 条件必填 | 风险分数/延期天数/关键词次数规则 |
| `target` | object | 是 | 目标群、用户、文档或表格 |
| `enabled` | boolean | 否 | 是否启用，默认 true |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `trigger_id` | string | 触发器 ID |
| `status` | string | enabled/disabled |
| `next_run_at` | string|null | 下次执行时间 |
| `scenario_type` | string | 场景类型 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "trigger_name": "Alpha 每周风险洞察",
  "trigger_type": "scheduled",
  "scenario_type": "weekly_insight",
  "schedule": {
    "cron": "0 17 * * 5",
    "timezone": "Asia/Singapore"
  },
  "target": {
    "chat_id": "oc_alpha_project",
    "reviewer_user_ids": [
      "ou_pm_001"
    ]
  },
  "enabled": true,
  "dry_run": true
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "trigger registered",
  "data": {
    "trigger_id": "trg_weekly_alpha",
    "status": "enabled",
    "next_run_at": "2026-04-24T17:00:00+08:00",
    "scenario_type": "weekly_insight"
  },
  "request_id": "req_trigger_register",
  "trace_id": "trace_trigger"
}
```

#### 测试与验收
- trigger_type=scheduled 时 schedule 必须存在。
- trigger_type=threshold 时 threshold_rule 必须存在。
- 同一 trigger_name 重复注册应返回冲突或更新原规则。

#### 实现说明
- 比赛 Demo 至少需要一种主动触发方式，本接口用于证明可配置主动服务。

### B3. 执行定时/事件/阈值触发
**接口：** `POST /agent/v1/triggers/execute`
**调用模式：** SSE 或异步接口
**接口职责：** 手动或由调度器执行某个 trigger，生成 trigger_context，并进入对应场景链路。
**典型触发：** 调度器到点执行、飞书事件回调、CLI 手动演示触发。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `trigger_id` | string | 否 | 已注册触发器 ID |
| `trigger_context` | object | 否 | 临时触发上下文 |
| `stream` | boolean | 否 | 是否 SSE 返回 |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` | string | 本次执行 ID |
| `scenario_type` | string | 场景类型 |
| `status` | string | running/waiting_review/completed |
| `preview_ids` | array | 生成的预览对象 ID |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "trigger_id": "trg_weekly_alpha",
  "stream": true,
  "dry_run": true
}
```

#### 响应示例
```text
event: stream_start
data: {"run_id":"run_trg_001","trigger_id":"trg_weekly_alpha"}

event: step
data: {"step":"collecting_context","message":"正在收集本周文档、会议、任务和群聊动态..."}

event: card_preview
data: {"card_id":"weekly_card_001","title":"Alpha 项目本周洞察"}

event: stream_end
data: {"finish_reason":"waiting_review","duration_ms":6200}
```

#### 测试与验收
- 未传 trigger_id 时必须能使用 trigger_context 临时执行。
- dry_run=true 时运行结束应为 waiting_review 或 completed_preview。
- SSE 中必须包含 run_id，便于后续查询。

#### 实现说明
- B3 是主动触发统一入口，B4/B10/B11 可以作为更明确的场景接口。

### B4. 生成会前背景知识卡片
**接口：** `POST /agent/v1/briefs/pre-meeting`
**调用模式：** SSE 或同步接口
**接口职责：** 围绕即将开始的会议，自动检索参会人、日历、上次会议、相关文档、未完成任务、近期变更和风险，生成会前背景卡片。
**典型触发：** 方向 B 主 Demo：会议前 30 分钟自动推送。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `calendar_event_id` | string | 是 | 会议日历 ID |
| `attendee_user_ids` | array[string] | 否 | 参会人 |
| `target_chat_id` | string | 是 | 目标群 |
| `time_window` | object | 否 | 默认近 7 天 |
| `sections` | array[string] | 否 | 背景/上次结论/未完成事项/风险/建议议题 |
| `stream` | boolean | 否 | 是否 SSE |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` | string | 运行 ID |
| `card_preview` | object | 卡片预览 |
| `references` | array | 证据引用 |
| `validation` | object | 引用校验结果 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "calendar_event_id": "cal_alpha_weekly_001",
  "attendee_user_ids": [
    "ou_pm_001",
    "ou_rd_002",
    "ou_qa_003"
  ],
  "target_chat_id": "oc_alpha_project",
  "time_window": {
    "start_at": "2026-04-17T00:00:00Z",
    "end_at": "2026-04-24T10:00:00Z"
  },
  "sections": [
    "meeting_goal",
    "previous_decisions",
    "open_tasks",
    "recent_changes",
    "risks",
    "suggested_agenda"
  ],
  "stream": true,
  "dry_run": true
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "pre-meeting brief generated",
  "data": {
    "run_id": "run_pre_meeting_001",
    "card_preview": {
      "card_id": "card_pre_001",
      "title": "Alpha 项目周会会前背景",
      "blocks": [
        {
          "type": "summary",
          "text": "本次会议建议重点关注接口 v2 字段变更、测试环境权限和压测报告进度。"
        }
      ]
    },
    "references": [
      {
        "evidence_id": "ev_mins_001",
        "source_name": "上次项目周会纪要"
      }
    ],
    "validation": {
      "overall_status": "passed"
    }
  },
  "request_id": "req_pre_meeting",
  "trace_id": "trace_pre_meeting"
}
```

#### 测试与验收
- 卡片中每条事实必须有 references。
- 如果 A9 返回 empty_reason，应展示“未找到相关背景”，不能编造。
- 输出必须适合直接进入 B6 卡片预览或 B7 推送。

#### 实现说明
- 这是最适合作为主线演示的接口。

### B5. 会议纪要 Action Items 抽取与预览
**接口：** `POST /agent/v1/actions/extract`
**调用模式：** 同步接口
**接口职责：** 从会议纪要、妙记、群聊或文本中抽取 Action Items，并补齐负责人、截止时间、优先级、关联证据和任务去重信息。
**典型触发：** 会后自动任务闭环、方向 B 和 D 的连接点。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `source_id` | string | 否 | 会议纪要 source_id |
| `text` | string | 否 | 直接传入文本，与 source_id 二选一 |
| `dedupe_with_existing_tasks` | boolean | 否 | 是否与现有飞书任务去重 |
| `default_due_days` | integer | 否 | 缺少截止时间时默认天数 |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `action_items` | array | 待办预览 |
| `missing_fields` | array | 缺失字段提醒 |
| `duplicates` | array | 疑似重复任务 |
| `references` | array | 引用证据 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "source_id": "src_mins_001",
  "dedupe_with_existing_tasks": true,
  "default_due_days": 3,
  "dry_run": true
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "action items extracted",
  "data": {
    "action_items": [
      {
        "action_id": "act_001",
        "title": "补充接口压测报告",
        "owner_user_id": "ou_rd_002",
        "due_at": "2026-04-26T18:00:00Z",
        "priority": "high",
        "evidence_ids": [
          "ev_mins_003"
        ],
        "dedupe_status": "new"
      }
    ],
    "missing_fields": [],
    "duplicates": [],
    "references": [
      {
        "evidence_id": "ev_mins_003",
        "source_name": "Alpha 联调纪要"
      }
    ]
  },
  "request_id": "req_action_extract",
  "trace_id": "trace_actions"
}
```

#### 测试与验收
- 待办必须包含 title 和 evidence_ids。
- 负责人缺失时不得强行猜测，应放入 missing_fields。
- 重复任务应标记 dedupe_status=possible_duplicate，而不是直接创建。

#### 实现说明
- B5 的输出可以直接作为 B8 的输入。

### B6. 飞书卡片预览生成
**接口：** `POST /agent/v1/cards/preview`
**调用模式：** 同步接口
**接口职责：** 把会前背景、周报、风险预警、会后行动项等结构化内容转换为飞书卡片 JSON 预览。
**典型触发：** 写飞书前人工审核、OpenClaw/CLI Demo 展示。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `card_type` | string | 是 | pre_meeting/weekly/risk/action_items/todo_table |
| `content` | object | 是 | 卡片内容结构 |
| `references` | array | 否 | 证据引用 |
| `style_config` | object | 否 | 卡片风格 |
| `review_required` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `card_id` | string | 卡片预览 ID |
| `card_json` | object | 飞书卡片 JSON |
| `plain_text` | string | 纯文本降级版本 |
| `review_required` | boolean | 是否需要审核 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "card_type": "risk",
  "content": {
    "title": "接口联调风险预警",
    "summary": "测试环境权限未开通，可能影响周五联调。",
    "actions": [
      "请负责人今天 18:00 前确认权限开通进度"
    ]
  },
  "references": [
    {
      "evidence_id": "ev_task_002",
      "source_name": "Alpha 任务列表"
    }
  ],
  "style_config": {
    "show_evidence": true,
    "show_feedback_buttons": true
  },
  "review_required": true
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "card preview generated",
  "data": {
    "card_id": "card_preview_risk_001",
    "card_json": {
      "config": {
        "wide_screen_mode": true
      },
      "header": {
        "title": {
          "tag": "plain_text",
          "content": "接口联调风险预警"
        }
      },
      "elements": []
    },
    "plain_text": "接口联调风险预警：测试环境权限未开通...",
    "review_required": true
  },
  "request_id": "req_card_preview",
  "trace_id": "trace_card"
}
```

#### 测试与验收
- card_json 必须可被飞书卡片调试器识别。
- plain_text 不得为空，用于 CLI 或失败降级。
- references 开启 show_evidence 时必须在卡片中体现来源入口。

#### 实现说明
- 此接口不做真实推送，只生成可审核对象。

### B7. 飞书卡片推送
**接口：** `POST /agent/v1/cards/push`
**调用模式：** 同步或异步接口
**接口职责：** 将已审核的 card_id 或 card_json 推送到飞书群/个人，并记录 send_status 和点击反馈追踪 ID。
**典型触发：** 人工确认后发送会前卡片、周报、风险预警。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `card_id` | string | 条件必填 | 预览卡片 ID |
| `card_json` | object | 条件必填 | 直接传卡片 JSON，与 card_id 二选一 |
| `target` | object | 是 | chat_id/user_id/open_id |
| `confirm_token` | string | 写操作建议必填 | 人工确认令牌 |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `send_id` | string | 发送记录 ID |
| `status` | string | preview_only/sent/failed |
| `target` | object | 目标 |
| `feishu_message_id` | string|null | 飞书消息 ID |
| `feedback_tracking_id` | string | 反馈追踪 ID |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "card_id": "card_preview_risk_001",
  "target": {
    "chat_id": "oc_alpha_project"
  },
  "confirm_token": "confirm_by_ou_pm_001_20260424",
  "dry_run": false
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "card pushed",
  "data": {
    "send_id": "send_001",
    "status": "sent",
    "target": {
      "chat_id": "oc_alpha_project"
    },
    "feishu_message_id": "om_xxx",
    "feedback_tracking_id": "fb_card_001"
  },
  "request_id": "req_card_push",
  "trace_id": "trace_card"
}
```

#### 测试与验收
- dry_run=true 时不得调用飞书真实发送接口。
- dry_run=false 且缺少 confirm_token 应返回 422。
- 推送成功后必须产生 feedback_tracking_id。

#### 实现说明
- 比赛现场建议默认 dry_run=true，最终演示可以只对测试群 dry_run=false。

### B8. 飞书任务创建/更新预览
**接口：** `POST /agent/v1/tasks/preview`
**调用模式：** 同步接口
**接口职责：** 将 Action Items 转换为飞书任务创建或更新预览，展示负责人、截止时间、优先级、描述、关联证据和重复任务判断。
**典型触发：** 会后 Action Items 转任务前的人工确认。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `action_items` | array | 是 | 来自 B5 的待办 |
| `task_mapping_config` | object | 否 | 字段映射规则 |
| `dry_run` | boolean | 否 | 固定 true 或默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `task_previews` | array | 任务预览 |
| `requires_confirmation` | boolean | 是否需要确认 |
| `validation_errors` | array | 字段错误 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "action_items": [
    {
      "action_id": "act_001",
      "title": "补充接口压测报告",
      "owner_user_id": "ou_rd_002",
      "due_at": "2026-04-26T18:00:00Z",
      "priority": "high",
      "evidence_ids": [
        "ev_mins_003"
      ]
    }
  ],
  "task_mapping_config": {
    "append_evidence_links": true,
    "default_project_section": "接口联调"
  },
  "dry_run": true
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "task preview generated",
  "data": {
    "task_previews": [
      {
        "preview_id": "task_prev_001",
        "operation": "create",
        "title": "补充接口压测报告",
        "owner_user_id": "ou_rd_002",
        "due_at": "2026-04-26T18:00:00Z",
        "description": "来源：Alpha 联调纪要 ev_mins_003",
        "dedupe_status": "new"
      }
    ],
    "requires_confirmation": true,
    "validation_errors": []
  },
  "request_id": "req_task_preview",
  "trace_id": "trace_tasks"
}
```

#### 测试与验收
- 每个 task_preview 必须包含 operation。
- owner 缺失时 validation_errors 中必须体现。
- dedupe_status=possible_duplicate 时默认不进入自动提交。

#### 实现说明
- 此接口只预览，不写飞书任务。

### B9. 确认后创建/更新飞书任务
**接口：** `POST /agent/v1/tasks/commit`
**调用模式：** 同步或异步接口
**接口职责：** 根据 B8 生成的 preview_id 或完整 task_previews，执行飞书任务创建/更新，并写回 evidence link。
**典型触发：** 用户确认后创建任务；会后闭环演示。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `preview_ids` | array[string] | 条件必填 | 任务预览 ID 列表 |
| `task_previews` | array | 条件必填 | 直接提交任务对象 |
| `confirm_token` | string | 是 | 人工确认令牌 |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `committed_tasks` | array | 已创建/更新任务 |
| `failed_tasks` | array | 失败任务 |
| `status` | string | completed/partial/failed |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "preview_ids": [
    "task_prev_001"
  ],
  "confirm_token": "confirm_by_ou_pm_001_20260424",
  "dry_run": false
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "tasks committed",
  "data": {
    "committed_tasks": [
      {
        "preview_id": "task_prev_001",
        "feishu_task_id": "task_feishu_001",
        "operation": "create",
        "status": "created"
      }
    ],
    "failed_tasks": [],
    "status": "completed"
  },
  "request_id": "req_task_commit",
  "trace_id": "trace_tasks"
}
```

#### 测试与验收
- 缺少 confirm_token 必须拒绝。
- partial 状态下必须返回 failed_tasks 及原因。
- 任务创建后应触发 B12 更新推进表或写入关联字段。

#### 实现说明
- 所有真实写飞书任务的操作均应保留审计日志。

### B10. 团队周报与风险洞察生成
**接口：** `POST /agent/v1/insights/weekly`
**调用模式：** SSE 或异步接口
**接口职责：** 自动汇总本周文档变更、会议决议、任务状态、群聊风险和未闭环问题，生成周报卡片和可选飞书文档。
**典型触发：** 方向 A 主体能力，适合作为第二条 Demo。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `time_window` | object | 是 | 周报时间窗口 |
| `target` | object | 是 | 目标群/文档 |
| `include_sections` | array[string] | 否 | 本周完成/重点变更/风险/下周计划/待确认问题 |
| `stream` | boolean | 否 | 是否流式 |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` | string | 运行 ID |
| `weekly_card` | object | 周报卡片 |
| `doc_draft` | object|null | 飞书文档草稿 |
| `metrics` | object | 统计指标 |
| `references` | array | 引用来源 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "time_window": {
    "start_at": "2026-04-20T00:00:00Z",
    "end_at": "2026-04-24T17:00:00Z"
  },
  "target": {
    "chat_id": "oc_alpha_project",
    "doc_parent_token": "fld_weekly_reports"
  },
  "include_sections": [
    "done",
    "changes",
    "risks",
    "next_week",
    "questions"
  ],
  "stream": true,
  "dry_run": true
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "weekly insight generated",
  "data": {
    "run_id": "run_weekly_001",
    "weekly_card": {
      "title": "Alpha 项目本周工作总结与风险洞察",
      "blocks": []
    },
    "doc_draft": {
      "title": "Alpha 项目周报 2026-04-24",
      "content_markdown": "# Alpha 项目周报"
    },
    "metrics": {
      "changed_docs": 3,
      "completed_tasks": 5,
      "delayed_tasks": 2,
      "risk_count": 3
    },
    "references": [
      {
        "evidence_id": "ev_doc_change_001",
        "source_name": "Alpha PRD"
      }
    ]
  },
  "request_id": "req_weekly",
  "trace_id": "trace_weekly"
}
```

#### 测试与验收
- 周报必须包含可量化统计字段 metrics。
- 风险洞察必须能追溯到 evidence。
- dry_run=true 时只返回 doc_draft，不创建飞书文档。

#### 实现说明
- 周报可用于证明方向 A 的周期性智能总结与洞察。

### B11. 风险预警生成与推送
**接口：** `POST /agent/v1/risks/alert`
**调用模式：** 同步或异步接口
**接口职责：** 当任务延期、阻塞关键词、风险分数或多人争议超过阈值时，生成风险预警卡片并建议升级对象。
**典型触发：** 方向 A/D 的阈值触发能力。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `risk_context` | object | 否 | 直接传入风险上下文 |
| `threshold_rule` | object | 否 | 触发阈值规则 |
| `target` | object | 是 | 推送目标 |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `risk_alert` | object | 风险预警内容 |
| `risk_score` | number | 风险分 |
| `recommended_actions` | array | 建议动作 |
| `card_preview` | object | 卡片预览 |
| `references` | array | 引用证据 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "threshold_rule": {
    "delayed_days_gte": 2,
    "risk_score_gte": 0.75
  },
  "target": {
    "chat_id": "oc_alpha_project",
    "mention_user_ids": [
      "ou_rd_002"
    ]
  },
  "dry_run": true
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "risk alert generated",
  "data": {
    "risk_alert": {
      "title": "测试环境权限阻塞接口联调",
      "level": "high",
      "summary": "任务延期 2 天，群聊中已两次提到权限未开通。"
    },
    "risk_score": 0.86,
    "recommended_actions": [
      "请负责人今天 18:00 前确认权限开通状态",
      "如未开通，建议升级给项目经理协调"
    ],
    "card_preview": {
      "card_id": "risk_card_001"
    },
    "references": [
      {
        "evidence_id": "ev_task_002"
      },
      {
        "evidence_id": "ev_chat_006"
      }
    ]
  },
  "request_id": "req_risk",
  "trace_id": "trace_risk"
}
```

#### 测试与验收
- 风险等级必须由明确规则或模型评分解释。
- 所有 recommended_actions 应避免命令式过强，保留人工判断。
- 高风险卡片默认需要 review。

#### 实现说明
- 该接口用于证明阈值触发的主动知识服务。

### B12. 重点事项推进表更新
**接口：** `POST /agent/v1/bitable/sync`
**调用模式：** 同步或异步接口
**接口职责：** 把 Action Items、任务状态、风险、阻塞原因同步到飞书多维表格，形成可追踪、可分派、可预警的推进总表。
**典型触发：** 方向 D 团队待办中枢与进展自动对账。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `bitable_token` | string | 是 | 多维表格 token |
| `records` | array | 否 | 待写入记录；不传时由 B 从 A 查询生成 |
| `sync_mode` | string | 否 | append/upsert/full_reconcile |
| `key_fields` | array[string] | 否 | 幂等匹配字段 |
| `dry_run` | boolean | 否 | 默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `sync_id` | string | 同步记录 ID |
| `preview_records` | array | dry_run 时的写入预览 |
| `created_count` | integer | 新建数量 |
| `updated_count` | integer | 更新数量 |
| `skipped_count` | integer | 跳过数量 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "bitable_token": "bascn_alpha",
  "sync_mode": "upsert",
  "key_fields": [
    "action_id"
  ],
  "dry_run": true
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "bitable sync preview generated",
  "data": {
    "sync_id": "bt_sync_001",
    "preview_records": [
      {
        "action_id": "act_001",
        "title": "补充接口压测报告",
        "owner": "张三",
        "status": "进行中",
        "risk_level": "high"
      }
    ],
    "created_count": 1,
    "updated_count": 3,
    "skipped_count": 0
  },
  "request_id": "req_bitable",
  "trace_id": "trace_bitable"
}
```

#### 测试与验收
- dry_run=true 时不能写入多维表格。
- upsert 必须根据 key_fields 幂等。
- preview_records 必须包含负责人、状态、截止时间、风险、证据链接。

#### 实现说明
- 这是方向 D 的核心接口，可作为任务闭环展示。

### B13. 用户反馈与点击/确认记录
**接口：** `POST /agent/v1/feedback`
**调用模式：** 同步接口
**接口职责：** 记录用户对卡片、任务、周报、风险预警的点击、点赞、无用、确认、驳回、修改等行为，为用户接受度指标提供数据。
**典型触发：** 卡片按钮回调、OpenClaw 反馈、Demo Dashboard 统计。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `feedback_tracking_id` | string | 是 | 反馈追踪 ID |
| `target_type` | string | 是 | card/task/weekly/risk/action_item |
| `target_id` | string | 是 | 目标对象 ID |
| `user_id` | string | 是 | 反馈用户 |
| `action` | string | 是 | click/useful/not_useful/confirm/reject/edit/open_reference |
| `payload` | object | 否 | 补充信息 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `feedback_id` | string | 反馈 ID |
| `accepted` | boolean | 是否记录成功 |
| `metric_updates` | object | 被更新的指标 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "feedback_tracking_id": "fb_card_001",
  "target_type": "card",
  "target_id": "card_pre_001",
  "user_id": "ou_pm_001",
  "action": "open_reference",
  "payload": {
    "evidence_id": "ev_task_002"
  }
}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "feedback recorded",
  "data": {
    "feedback_id": "feedback_001",
    "accepted": true,
    "metric_updates": {
      "card_open_reference_count": 1
    }
  },
  "request_id": "req_feedback",
  "trace_id": "trace_feedback"
}
```

#### 测试与验收
- 同一用户重复点击可以记录，但统计时需支持去重。
- action 枚举外的值返回 400。
- feedback_tracking_id 缺失时应仍可记录，但指标可信度降低。

#### 实现说明
- 比赛效果验证中的点击率、任务确认率、用户接受度依赖该接口。

### B14. 场景运行结果查询
**接口：** `GET /agent/v1/runs/{run_id}`
**调用模式：** 同步接口
**接口职责：** 查询 B1/B3/B4/B10/B11 等场景运行的最终结果、步骤日志、证据、生成产物、错误信息和耗时。
**典型触发：** 前端刷新页面、Demo Dashboard 回放、失败排查。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `run_id` | path string | 是 | 运行 ID |
| `include_steps` | query boolean | 否 | 是否返回步骤日志 |
| `include_artifacts` | query boolean | 否 | 是否返回卡片/任务/周报产物 |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` | string | 运行 ID |
| `scenario_type` | string | 场景类型 |
| `status` | string | running/waiting_review/completed/failed |
| `steps` | array | 步骤日志 |
| `artifacts` | array | 生成产物 |
| `references` | array | 证据引用 |
| `duration_ms` | integer | 耗时 |

#### 请求示例
```bash
curl -X GET http://{algo_host}:8200/agent/v1/runs/{run_id}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "run_id": "run_pre_meeting_001",
    "scenario_type": "pre_meeting_brief",
    "status": "waiting_review",
    "steps": [
      {
        "step": "retrieving_evidence",
        "duration_ms": 1800
      },
      {
        "step": "generating_card",
        "duration_ms": 1500
      }
    ],
    "artifacts": [
      {
        "type": "card_preview",
        "id": "card_pre_001"
      }
    ],
    "references": [
      {
        "evidence_id": "ev_task_002"
      }
    ],
    "duration_ms": 4200
  },
  "request_id": "req_run",
  "trace_id": "trace_pre_meeting"
}
```

#### 测试与验收
- run_id 不存在返回 404。
- include_artifacts=false 时不返回大对象，避免响应过大。
- 状态必须与 SSE 最终状态一致。

#### 实现说明
- 该接口是异步场景和页面刷新后的兜底。

### B15. 清理会话缓存和临时状态
**接口：** `DELETE /agent/v1/cache/{session_id}`
**调用模式：** 同步接口
**接口职责：** 清理 LangGraph/OpenClaw checkpoint、临时卡片、临时任务预览、临时文档 source、A 服务临时数据引用。
**典型触发：** 会话结束、Demo 重置、用户退出、测试用例 teardown。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | path string | 是 | 会话 ID |
| `tenant_id` | query string | 是 | 租户 ID |
| `workspace_id` | query string | 是 | 工作空间 ID |
| `cascade_to_evidence` | query boolean | 否 | 是否调用 A 删除临时 source，默认 true |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | string | 会话 ID |
| `cleared_checkpoints` | integer | 清理 checkpoint 数 |
| `cleared_temp_sources` | integer | 清理临时 source 数 |
| `cleared_previews` | integer | 清理预览对象数 |

#### 请求示例
```bash
curl -X DELETE http://{algo_host}:8200/agent/v1/cache/{session_id}
```

#### 响应示例
```json
{
  "code": 200,
  "message": "cache cleared",
  "data": {
    "session_id": "sess_openclaw_001",
    "cleared_checkpoints": 12,
    "cleared_temp_sources": 2,
    "cleared_previews": 5
  },
  "request_id": "req_cache_clear",
  "trace_id": "trace_cache"
}
```

#### 测试与验收
- 重复清理应返回 200 且数量为 0。
- cascade_to_evidence=true 时应调用 A4 删除临时 source。
- 不得删除已确认推送的历史审计记录。

#### 实现说明
- 继承原接口文档 B3 清理 session 缓存的思路。

### B16. 生成效果验证报告
**接口：** `POST /agent/v1/eval/report`
**调用模式：** 异步接口
**接口职责：** 基于 A 导出的评测数据、B 的反馈数据、运行日志和人工标注，生成比赛交付物中的效果验证报告。
**典型触发：** 比赛交付：准确性、自证引用、用户接受度、效率提升。

#### 请求字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_id` | string | 是 | 租户 ID |
| `workspace_id` | string | 是 | 工作空间 ID |
| `project_id` | string | 是 | 项目 ID |
| `time_window` | object | 是 | 评测时间窗口 |
| `scenario_types` | array[string] | 否 | 评测场景 |
| `baseline` | object | 否 | 人工搜索/普通 LLM baseline 记录 |
| `output_format` | string | 否 | markdown/docx/json，默认 markdown |

#### 响应字段
| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 报告生成任务 ID |
| `status` | string | queued |
| `estimated_seconds` | integer | 预估耗时 |
| `report_url` | string|null | 完成后下载地址 |

#### 请求示例
```json
{
  "tenant_id": "tenant_demo",
  "workspace_id": "ws_alpha",
  "project_id": "alpha_project",
  "time_window": {
    "start_at": "2026-04-20T00:00:00Z",
    "end_at": "2026-04-24T23:59:59Z"
  },
  "scenario_types": [
    "pre_meeting_brief",
    "post_meeting_action_items",
    "weekly_insight"
  ],
  "baseline": {
    "manual_minutes": 120,
    "normal_llm_minutes": 55,
    "agent_minutes": 18
  },
  "output_format": "markdown"
}
```

#### 响应示例
```json
{
  "code": 202,
  "message": "evaluation report task accepted",
  "data": {
    "task_id": "eval_report_001",
    "status": "queued",
    "estimated_seconds": 20,
    "report_url": null
  },
  "request_id": "req_eval_report",
  "trace_id": "trace_eval_report"
}
```

#### 测试与验收
- 报告至少包含 Citation Accuracy、Action Item Precision/Recall、Time Saving、Card Click Rate、Task Confirmation Rate。
- baseline 字段缺失时仍可生成准确性报告，但效率提升部分标记为待补充。
- 生成报告中的每个数字应可追溯到 metric record。

#### 实现说明
- 该接口直连比赛交付物中的“效果验证报告”。

## 6. SSE 事件流协议
B1/B3/B4/B10 等接口在 `stream=true` 时返回 SSE。协议继承原接口文档中的 `stream_start / step / intent / text_delta / references / error / stream_end` 思路，但把 `intent` 扩展为 `scenario`，并新增 `evidence_delta / atom_delta / card_preview / task_preview / push_result / feedback_required / metric_delta`。

### 6.1 SSE 基本格式
```text
event: {event_name}
data: {JSON 字符串}


```
响应头必须包含：
```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Request-Id: req_xxx
```

### 6.2 事件枚举
| event | 说明 | 典型 data 字段 | 前端/CLI 行为 |
|---|---|---|---|
| `stream_start` | 流开始 | `run_id/session_id/created_at` | 初始化输出区域 |
| `scenario` | 场景识别结果 | `scenario_type/confidence/message` | 切换 UI 渲染模式 |
| `step` | 阶段进度 | `step/message/progress` | 展示正在检索/生成/校验 |
| `evidence_delta` | 检索到一条证据 | `evidence_id/source_name/summary` | 可实时展示证据列表 |
| `atom_delta` | 生成或命中一个知识原子 | `atom_id/atom_type/title` | 更新知识原子面板 |
| `text_delta` | 普通文本增量 | `delta` | 拼接为回答/说明 |
| `card_preview` | 卡片预览完成 | `card_id/card_json/plain_text` | 渲染卡片预览 |
| `task_preview` | 任务预览完成 | `preview_id/title/owner/due_at` | 渲染任务确认面板 |
| `references` | 引用来源汇总 | `references[]` | 展示引用卡片 |
| `validation` | 证据校验结果 | `overall_status/unsupported_count` | 标记需人工复核内容 |
| `push_result` | 写入结果 | `send_id/status/message_id` | 展示推送成功/失败 |
| `feedback_required` | 需要用户确认 | `review_type/object_id/actions` | 显示确认/驳回按钮 |
| `metric_delta` | 效果指标增量 | `metric_name/value` | 更新 Demo 指标 |
| `error` | 错误 | `code/type/message/fatal` | 提示错误并视 fatal 决定是否终止 |
| `stream_end` | 流结束 | `usage/finish_reason/duration_ms` | 收尾，允许下载/复制结果 |

### 6.3 会前背景卡片完整 SSE 示例
```text
event: stream_start
data: {"run_id":"run_pre_meeting_001","session_id":"sess_demo_001","created_at":"2026-04-24T09:30:00Z"}

event: scenario
data: {"scenario_type":"pre_meeting_brief","confidence":0.94,"message":"已识别为会前背景知识卡片"}

event: step
data: {"step":"retrieving_evidence","message":"正在检索上次会议纪要、近期任务和群聊风险...","progress":20}

event: evidence_delta
data: {"evidence_id":"ev_mins_001","source_name":"Alpha 上次周会纪要","summary":"上次会议确认接口 v2 旧字段暂不下线。"}

event: evidence_delta
data: {"evidence_id":"ev_task_002","source_name":"Alpha 任务列表","summary":"测试环境权限未开通，任务延期 2 天。"}

event: atom_delta
data: {"atom_id":"atom_risk_001","atom_type":"Risk","title":"接口联调存在延期风险"}

event: step
data: {"step":"generating_card","message":"正在生成飞书卡片预览...","progress":70}

event: card_preview
data: {"card_id":"card_pre_001","title":"Alpha 项目周会会前背景","review_required":true}

event: validation
data: {"overall_status":"passed","unsupported_count":0,"conflict_count":0}

event: references
data: {"references":[{"evidence_id":"ev_mins_001","source_name":"Alpha 上次周会纪要"},{"evidence_id":"ev_task_002","source_name":"Alpha 任务列表"}]}

event: feedback_required
data: {"review_type":"card_push","object_id":"card_pre_001","actions":["confirm_push","edit","reject"]}

event: stream_end
data: {"finish_reason":"waiting_review","duration_ms":4200,"usage":{"prompt_tokens":2100,"completion_tokens":460,"total_tokens":2560}}

```

## 7. A/B 联调契约
### 7.1 B 调 A 的推荐顺序
以会前背景卡片为例，B 的调用顺序如下：
1. B 接收 `calendar_event_id` 和 `target_chat_id`。
2. B 调 A9 `/retrieval/search`，query 为“本次会议需要关注的背景、风险、未完成任务、近期变更”。
3. B 调 A8 `/atoms/query`，筛选 Decision、ActionItem、Risk、Change。
4. B 生成卡片候选内容。
5. B 调 A10 `/references/validate` 校验卡片结论是否被证据支持。
6. 校验通过后 B 返回 `card_preview`；若 dry_run=false 且有 confirm_token，再调 B7 推送。

### 7.2 B 调 A 的超时与降级
| 场景 | A 接口 | 建议超时 | 降级策略 |
|---|---|---:|---|
| 会前背景 | A9/A8/A10 | 3s/1s/2s | 使用最近一次缓存 evidence，卡片标记“基于缓存” |
| 会后任务 | A8/A10 | 2s/2s | 只输出任务预览，不允许自动提交 |
| 周报洞察 | A8/A9/A12 | 5s/5s/异步 | 转为异步任务，SSE 展示处理进度 |
| 风险预警 | A8/A9 | 2s/3s | 只提醒“疑似风险”，要求人工确认 |

### 7.3 Mock 协议
为了保证两个人并行开发，A 和 B 必须都支持 mock 模式：
- A 支持 `source_type=local_mock`，从 `tests/fixtures/alpha_project/*.json` 读取 Docs、Minutes、Messages、Tasks。
- B 支持 `mock_evidence=true`，直接从 `tests/fixtures/mock_evidence_response.json` 获取 A9 风格结果。
- 双方约定 mock 数据的 `evidence_id`、`atom_id`、`source_id` 不变，便于端到端测试。
- Mock 模式下也要返回 request_id 和 trace_id，不得跳过日志。

## 8. 请求与响应字段设计原则
### 8.1 后端/CLI 不做业务意图判断
与原接口文档中 B1 的原则一致，后端或 CLI 只负责把用户输入、上下文和当前状态传给算法端。比如用户说“把这个推送到群里”，后端不判断这是会前卡片还是周报卡片，而是把当前 `runtime_context.card_id`、`target_chat_id`、`query` 一起传给 B。B 根据状态进行判断。

### 8.2 写操作默认 dry_run
所有会影响飞书真实空间的接口都必须默认 `dry_run=true`，包括 B7 卡片推送、B9 任务提交、B12 多维表格更新。只有当 `dry_run=false` 且 `confirm_token` 存在时，才允许真实写入。

### 8.3 引用优先原则
任何进入卡片、任务描述、周报、风险预警的事实性内容，都必须具有 evidence_id。对于没有证据的结论，只能以“待确认问题”或“建议讨论事项”形式出现，不能作为事实陈述。

### 8.4 统一可观测字段
所有响应都应尽量携带 `trace_id`；所有异步任务都应有 `task_id`；所有场景执行都应有 `run_id`；所有飞书写入都应有 `send_id / feishu_message_id / feishu_task_id`；所有反馈都应有 `feedback_tracking_id`。这些 ID 是后续效果验证报告的证据链。

## 9. 开发测试与交付验收
### 9.1 子系统 A 独立测试
| 测试编号 | 测试目标 | 输入 | 期望结果 |
|---|---|---|---|
| A-T01 | 多源同步 | local_mock 项目数据 | 返回 sync task，状态 completed，产生 4 类 source |
| A-T02 | PageIndex 构建 | PRD 文档 source | 生成 node_path、summary、leaf chunk |
| A-T03 | 会议 Action 原子 | 会议纪要 source | 抽取 ActionItem，包含 owner/due/evidence |
| A-T04 | 风险原子 | 群聊 + 任务延期 | 抽取 Risk/Blocker，risk_reason 可解释 |
| A-T05 | 证据检索 | pre_meeting query | 返回至少 5 条 evidence，score 排序合理 |
| A-T06 | 引用校验 | 1 条支持结论 + 1 条不支持结论 | 分别返回 supported/unsupported |
| A-T07 | 权限隔离 | 错误 tenant_id | 返回 403 或空结果，不泄露数据 |
| A-T08 | 删除清理 | 删除临时 source | 相关 index/atom/graph 被清理 |

### 9.2 子系统 B 独立测试
| 测试编号 | 测试目标 | 输入 | 期望结果 |
|---|---|---|---|
| B-T01 | SSE 对话入口 | query=生成会前卡片 + mock_evidence | 按顺序输出 scenario/step/card_preview/references/stream_end |
| B-T02 | 触发器注册 | weekly cron | 返回 trigger_id 和 next_run_at |
| B-T03 | 手动执行触发器 | trigger_id | 生成 weekly card preview |
| B-T04 | 会前背景 | calendar_event_id | 生成包含背景/风险/建议议题的卡片 |
| B-T05 | Action Items | meeting source | 抽取任务预览并标记缺失字段 |
| B-T06 | 卡片推送 dry_run | card_id + dry_run=true | 不写飞书，仅返回 preview_only |
| B-T07 | 任务提交保护 | dry_run=false 但无 confirm_token | 返回 422 |
| B-T08 | 反馈统计 | open_reference 事件 | 更新 card_open_reference_count |

### 9.3 A/B 合并联调测试
| 测试编号 | 链路 | 接口调用顺序 | 验收标准 |
|---|---|---|---|
| I-T01 | 会前背景卡片 | A1→A5→A7→B4→A9→A10→B6 | 卡片事实均有 evidence，SSE 完整，无真实推送 |
| I-T02 | 会后任务闭环 | A1→A7→B5→B8→B9(dry_run) | Action Item 抽取准确，任务预览字段完整 |
| I-T03 | 周报洞察 | A1/A7→B10→B6→B13 | 周报包含完成、变化、风险、下周事项和指标 |
| I-T04 | 风险阈值 | B2→B3→A8/A9→B11 | 延期 2 天触发高风险预警 |
| I-T05 | 效果验证 | A12→B16 | 生成准确性、接受度、效率提升指标 |

### 9.4 比赛交付物与接口映射
| 交付物 | 必须说明的内容 | 依赖接口 | 验收证据 |
|---|---|---|---|
| 场景定义文档 | 为什么通用搜索/问答无法满足，为什么需要主动知识服务 | B2/B3/B4/B10/B11 | 触发器配置、SSE 运行日志、卡片样例 |
| 可运行 Demo | 至少一种主动触发方式，OpenClaw/CLI 可运行 | B1/B2/B3/B4/B7/B9 | 演示视频、curl、SSE 输出、dry_run 预览 |
| 效果验证报告 | 准确性、用户接受度、效率提升 | A10/A12/B13/B16 | 引用校验结果、点击率、确认率、Baseline 对比 |

## 10. CLI / curl 联调示例
### 10.1 准备 mock 数据
```bash
curl -X POST http://localhost:8100/evidence/v1/sources/sync \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id":"tenant_demo",
    "workspace_id":"ws_alpha",
    "project_id":"alpha_project",
    "source_type":"local_mock",
    "filter":{"dataset_path":"tests/fixtures/alpha_project"},
    "sync_mode":"full",
    "config":{"auto_index":true,"auto_extract_atoms":true}
  }'
```

### 10.2 触发会前背景卡片
```bash
curl -N -X POST http://localhost:8200/agent/v1/briefs/pre-meeting \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id":"tenant_demo",
    "workspace_id":"ws_alpha",
    "project_id":"alpha_project",
    "calendar_event_id":"cal_alpha_weekly_001",
    "target_chat_id":"oc_alpha_project",
    "stream":true,
    "dry_run":true
  }'
```

### 10.3 生成周报洞察
```bash
curl -N -X POST http://localhost:8200/agent/v1/insights/weekly \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id":"tenant_demo",
    "workspace_id":"ws_alpha",
    "project_id":"alpha_project",
    "time_window":{"start_at":"2026-04-20T00:00:00Z","end_at":"2026-04-24T17:00:00Z"},
    "target":{"chat_id":"oc_alpha_project"},
    "stream":true,
    "dry_run":true
  }'
```

### 10.4 生成效果验证报告
```bash
curl -X POST http://localhost:8200/agent/v1/eval/report \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id":"tenant_demo",
    "workspace_id":"ws_alpha",
    "project_id":"alpha_project",
    "time_window":{"start_at":"2026-04-20T00:00:00Z","end_at":"2026-04-24T23:59:59Z"},
    "scenario_types":["pre_meeting_brief","post_meeting_action_items","weekly_insight"],
    "baseline":{"manual_minutes":120,"normal_llm_minutes":55,"agent_minutes":18},
    "output_format":"markdown"
  }'
```

## 11. 数据库与缓存建议
本接口文档不强制数据库实现，但为了两个子系统合并方便，建议至少设计以下表或集合。
| 表/集合 | 职责 | 关键字段 |
|---|---|---|
| `source_raw` | 保存飞书原始数据和本地 mock 数据 | `source_id, source_type, tenant_id, workspace_id, project_id, raw_payload, updated_at` |
| `index_nodes` | 保存 PageIndex/ThreadIndex 节点 | `node_id, source_id, parent_node_id, node_path, summary, content, child_count` |
| `knowledge_atoms` | 保存知识原子 | `atom_id, atom_type, title, summary, owner_user_ids, due_at, confidence, evidence_ids` |
| `evidence_graph_edges` | 保存实体和证据关系 | `edge_id, source_node, target_node, relation, evidence_ids` |
| `scenario_runs` | 保存 B 的每次场景执行 | `run_id, scenario_type, status, trace_id, artifacts, duration_ms` |
| `card_previews` | 保存卡片预览 | `card_id, card_type, card_json, references, review_status` |
| `task_previews` | 保存任务预览 | `preview_id, action_id, task_payload, confirm_status` |
| `feedback_events` | 保存反馈与点击 | `feedback_id, tracking_id, user_id, action, target_type, target_id` |
| `eval_metrics` | 保存效果评测指标 | `metric_id, scenario_type, metric_name, score, judge_method, sample_id` |

缓存建议：Redis 用于存储 `session checkpoint`、`trigger lock`、`idempotency key`、`short-term evidence cache`、`SSE run state`。临时 source 与临时卡片预览应设置 TTL，并在 B15 清理时级联删除。

## 12. 安全、权限与审计
### 12.1 权限隔离
A/B 所有接口必须携带 `tenant_id` 和 `workspace_id`。A 在检索时必须先做权限过滤，B 在推送时必须确认目标群或目标用户具有查看证据来源的权限。如果目标群没有权限查看某条证据，该证据对应内容必须脱敏或只作为私聊提醒发送。

### 12.2 写操作审计
B7/B9/B12 是真实写飞书的接口，必须记录：调用人、确认人、confirm_token、写入前预览、写入后返回 ID、关联证据、运行链路 trace_id。答辩或复盘时可以证明 Agent 并非擅自执行不可逆操作。

### 12.3 幻觉控制
所有事实型输出必须先经过 A10 引用校验。如果 `overall_status=failed`，B 只能返回“需要人工确认”的卡片，不允许直接推送。对于冲突信息，卡片中应显式展示“存在信息冲突”，并列出两个来源的不同说法，而不是让模型强行合并。

## 13. 性能目标
| 场景 | 目标延迟 | 说明 |
|---|---:|---|
| A9 多源检索 | p95 < 3s | 会前卡片和问答体验关键路径 |
| A10 引用校验 | p95 < 2s | 推送前校验，允许批量并发 |
| B4 会前卡片 | 首个 SSE step < 1s，完整预览 < 8s | 用户能感知进度 |
| B5 Action Items 抽取 | p95 < 5s | 会议后任务创建体验 |
| B10 周报洞察 | 可异步，完整 < 60s | 内容较长，必须有进度反馈 |
| B7/B9 写飞书 | p95 < 5s | 外部 API 可能波动，需失败重试 |

## 14. 推荐项目目录结构
```text
openclaw-team-knowledge-pulse/
  services/
    evidence_engine/
      app.py
      routers/
        sources.py
        index.py
        atoms.py
        retrieval.py
        references.py
        eval.py
      schemas/
        shared.py
        evidence.py
        atoms.py
      tests/
        fixtures/alpha_project/
        test_sources_sync.py
        test_retrieval.py
        test_reference_validate.py
    proactive_agent/
      app.py
      routers/
        chat.py
        triggers.py
        briefs.py
        actions.py
        cards.py
        tasks.py
        insights.py
        feedback.py
        eval_report.py
      graph/
        scenario_router.py
        pre_meeting_graph.py
        weekly_graph.py
        action_item_graph.py
      tests/
        test_sse_chat.py
        test_pre_meeting.py
        test_task_commit_guard.py
  docs/
    openclaw_ab_subsystem_api_specification.md
  scripts/
    demo_prepare_mock_data.sh
    demo_pre_meeting_brief.sh
    demo_weekly_insight.sh
  docker-compose.yml

```

## 15. Codex 实现任务单
### P0：接口骨架和 Mock 联通
- 创建 FastAPI 双服务工程。
- 实现 A0/B0 health。
- 实现共享 Pydantic schemas。
- 准备 alpha_project mock 数据。
- 实现 A1/A2 local_mock 同步。
- 实现 B1 mock_evidence SSE。
- 编写 smoke tests。

### P1：证据引擎闭环
- 实现 A5 索引构建。
- 实现 A7 知识原子抽取。
- 实现 A8/A9 查询。
- 实现 A10 引用校验。
- 补充权限字段和 trace 日志。

### P2：主动分发 Demo
- 实现 B2/B3 触发器。
- 实现 B4 会前背景卡片。
- 实现 B5/B8 会后任务预览。
- 实现 B6 卡片预览。
- 实现 B13 反馈记录。

### P3：写入和效果验证
- 接入飞书卡片 dry_run/真实推送。
- 接入飞书任务创建。
- 实现 B10 周报洞察。
- 实现 A12/B16 效果报告。
- 完善演示脚本和 README。

## 16. 最终交付检查清单
| 检查项 | 子系统 A | 子系统 B | 联调要求 |
|---|---|---|---|
| 接口文档 | A0-A13 字段和示例完整 | B0-B16 字段和示例完整 | A/B 字段名称一致 |
| 可运行 Demo | local_mock 可生成 evidence/atom | B1/B4/B10 可生成 SSE 和卡片 | B 能调用 A9/A10 |
| 场景定义 | 提供证据来源和知识原子定义 | 提供主动触发和目标用户说明 | 说明通用搜索不足 |
| 效果验证 | A10/A12 可导出准确性数据 | B13/B16 可统计接受度和效率 | 输出 Citation Accuracy 等指标 |
| 安全审计 | tenant/workspace 权限过滤 | 写操作 dry_run/confirm_token | trace_id 可贯穿 |
| 测试 | pytest 覆盖核心接口 | SSE 事件顺序测试 | Docker Compose 一键启动 |

## 17. 附录：字段枚举
### 17.1 scenario_type
- `knowledge_qa`
- `pre_meeting_brief`
- `post_meeting_action_items`
- `weekly_insight`
- `risk_alert`
- `todo_reconciliation`
- `faq_push`
- `chitchat`
### 17.2 atom_type
- `Fact`
- `Decision`
- `ActionItem`
- `Risk`
- `Blocker`
- `Change`
- `Question`
- `Insight`
- `FAQ`
- `Reminder`
### 17.3 source_type
- `docs`
- `minutes`
- `messages`
- `tasks`
- `calendar`
- `bitable`
- `file`
- `text`
- `local_mock`
### 17.4 write_operation_status
- `preview_only`
- `waiting_confirm`
- `sent`
- `created`
- `updated`
- `partial`
- `failed`
- `cancelled`

## 18. 总结
本接口文档把原有算法端接口的服务拆分、异步任务、SSE 流式、统一响应、PageIndex 入库与 Agent 自主决策思想，扩展为 OpenClaw 企业办公知识整合与分发项目的 A/B 双子系统接口。A 子系统负责把飞书多源数据变成可追溯证据和知识原子；B 子系统负责把证据转化为主动知识服务，包括会前背景、会后任务、周报洞察、风险预警和效果验证。两人可以分别实现 A 与 B，通过 mock 协议并行开发，最后以 A9/A10/B1/B4/B10/B16 为主线完成合并联调和比赛交付。