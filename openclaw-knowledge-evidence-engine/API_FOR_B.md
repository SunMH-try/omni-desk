# 子系统 A → B 接口对接手册

> 子系统 A 提供 4 个 HTTP JSON 接口，子系统 B 直接调用即可，无需了解内部实现。

---

## 快速接入

**Base URL**（本地启动）
```
http://localhost:8000
```

**启动服务**
```bash
cd openclaw-knowledge-evidence-engine
uvicorn app.main:app --port 8000
```

**健康检查**（确认服务就绪）
```bash
curl http://localhost:8000/health
# {"status":"ok","built":true}
```

所有接口均为 `POST`，`Content-Type: application/json`，无需鉴权 Header。

---

## 接口一：证据检索

> 输入一个自然语言问题，返回经过质量验证的多源证据列表。适用于：生成飞书卡片前的事实核查、回答"项目现在什么状态"之类问题。

```
POST /evidence/v1/query
```

**请求**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | string | ✅ | 自然语言查询，中英文均可 |
| `project_id` | string | ✅ | 项目标识，默认 `alpha_report_platform` |
| `top_k` | int | — | 返回证据数上限，默认 8 |
| `source_scope` | string[] | — | 限定来源类型，可选值：`docs` `minutes` `messages` `tasks`；不传则全量检索 |
| `trace_id` | string | — | 调用方自定义追踪 ID，原样返回 |

```json
{
  "trace_id": "b_call_001",
  "project_id": "alpha_report_platform",
  "query": "Alpha 项目 P0 联调现在什么进度？",
  "source_scope": ["minutes", "messages"],
  "top_k": 5
}
```

**响应**

```json
{
  "code": 200,
  "trace_id": "b_call_001",
  "data": {
    "verified_evidence": [
      {
        "evidence_id": "ev_minutes_alpha_review_0001",
        "summary": "Alpha项目P0接口联调整体已延期2天，原因为测试环境权限未开通",
        "support_level": "low",
        "confidence": 0.85,
        "source_type": "minutes",
        "source_url": "https://example.feishu.cn/minutes/alpha_weekly_2026_04_21",
        "is_stale": false
      }
    ],
    "conflict_report": [
      {
        "evidence_id_a": "ev_minutes_alpha_review_0007",
        "evidence_id_b": "ev_doc_alpha_prd_0021",
        "description": "会议纪要确认顺延，但PRD中进度仍未更新"
      }
    ]
  }
}
```

**字段说明**

| 字段 | 说明 |
|---|---|
| `support_level` | `high`=多源交叉验证 / `medium`=单源可信 / `low`=有来源但待核实 / `unverified`=无来源 |
| `is_stale` | `true` 表示该证据可能已过期，B 端可加"⚠ 待核实"标记 |
| `conflict_report` | 检测到矛盾的证据对，B 端可决定是否展示给用户 |

---

## 接口二：会前上下文包

> 给定一个即将开始的会议 ID，返回结构化的背景包，包含背景事实、上次决议、未关闭风险、待确认问题。适用于：生成会前飞书卡片。

```
POST /evidence/v1/meeting/context-package
```

**请求**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `meeting_id` | string | ✅ | 飞书日历事件 ID |
| `lookback_days` | int | — | 向前追溯天数，默认 14 |
| `include_unfinished_tasks` | bool | — | 是否包含未完成任务，默认 true |

```json
{
  "meeting_id": "meeting_alpha_weekly_next",
  "lookback_days": 14,
  "include_unfinished_tasks": true
}
```

**响应**

```json
{
  "code": 200,
  "data": {
    "background_facts": [
      "测试环境权限由运维 user_ops 负责，计划 2026-04-24 完成开通",
      "接口字段 report_version 暂不下线，保留至旧版客户端迁移完成后废弃"
    ],
    "last_decisions": [
      "P0 联调 deadline 顺延至 2026-04-28，原因为测试环境权限延迟开通",
      "接口字段 report_version 暂不下线，相关内容已更新到 PRD 3.0 节"
    ],
    "open_risks": [
      "若测试环境权限未在 2026-04-24 前开通，将直接阻塞后续接口联调进度",
      "旧版客户端迁移计划仍在评估中，存在 report_version 字段废弃时间不确定的风险"
    ],
    "pending_questions": [
      "旧版客户端迁移完成时间尚未确认"
    ],
    "evidence_ids": [
      "ev_minutes_alpha_review_0007",
      "ev_doc_alpha_prd_0016"
    ]
  }
}
```

> `evidence_ids` 可用于向用户展示"信息来源"链接，直接拼 `source_url` 跳转飞书原文。

---

## 接口三：Action Item 抽取

> 输入会议纪要 ID，返回结构化的行动项列表，含负责人、截止日期、优先级。适用于：会后自动生成飞书任务卡片。

```
POST /evidence/v1/minutes/action-items
```

**请求**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `minutes_id` | string | ✅ | 飞书会议纪要文档 ID |
| `need_owner_inference` | bool | — | 是否推断负责人，默认 true |
| `need_deadline_inference` | bool | — | 是否推断截止日期，默认 true |

```json
{
  "minutes_id": "minutes_alpha_review",
  "need_owner_inference": true,
  "need_deadline_inference": true
}
```

**响应**

```json
{
  "code": 200,
  "data": {
    "action_items": [
      {
        "item_id": "ai_minutes_alpha_review_001",
        "title": "完成 Alpha 项目测试环境权限开通",
        "owner": "user_ops",
        "deadline": "2026-04-24",
        "priority": "high",
        "confidence": 1.0,
        "source_url": "https://example.feishu.cn/minutes/alpha_weekly_2026_04_21",
        "needs_confirmation": false
      },
      {
        "item_id": "ai_minutes_alpha_review_003",
        "title": "完成 Alpha 项目 P0 接口联调",
        "owner": "user_rd",
        "deadline": "2026-04-28",
        "priority": "high",
        "confidence": 1.0,
        "source_url": "https://example.feishu.cn/minutes/alpha_weekly_2026_04_21",
        "needs_confirmation": false
      }
    ],
    "missing_field_report": [
      {
        "item_id": "ai_xxx_005",
        "title": "某待办",
        "missing": ["owner"]
      }
    ]
  }
}
```

**注意**

- `needs_confirmation: true` 表示负责人或截止日期不确定，B 端可弹出确认框让用户填写
- `missing_field_report` 中列出字段缺失的条目，B 端可高亮提示

---

## 接口四：周报时间窗口聚合

> 输入时间窗口，返回本周进展摘要、风险摘要、关键洞察。适用于：自动生成周报飞书文档。

```
POST /evidence/v1/weekly/window-summary
```

**请求**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | string | ✅ | 项目标识 |
| `week_start` | string | ✅ | 周起始日期，格式 `YYYY-MM-DD` |
| `week_end` | string | ✅ | 周结束日期，格式 `YYYY-MM-DD` |
| `source_scope` | string[] | — | 限定来源类型，不传则全量 |

```json
{
  "project_id": "alpha_report_platform",
  "week_start": "2026-04-20",
  "week_end": "2026-04-26"
}
```

**响应**

```json
{
  "code": 200,
  "data": {
    "weekly_atoms": ["atom_001", "atom_007", "atom_012"],
    "progress_summary": "本周确认 report_version 接口字段保留至 2026-06-01 下线，P0 联调因权限延迟顺延至 2026-04-28，各角色节点已明确。",
    "risk_summary": "测试环境权限延迟问题已导致联调顺延，若运维 4.24 未按时开通将再次影响后续节奏。",
    "key_insights": [
      "report_version 字段保留至 2026-06-01，可平稳过渡旧版客户端迁移",
      "P0 联调 deadline 顺延至 2026-04-28，需重点跟进权限开通进度"
    ],
    "evidence_ids": [
      "ev_minutes_alpha_review_0007",
      "ev_doc_alpha_prd_0016"
    ]
  }
}
```

---

## 错误码

| code | 含义 | 处理建议 |
|---|---|---|
| 200 | 成功 | — |
| 404 | 指定的 minutes_id / meeting_id 不存在 | 检查 ID 是否正确 |
| 422 | 请求字段格式错误 | 检查必填字段和类型 |
| 500 | 引擎内部错误 | 查看服务日志，或重新 `build-index` |

无相关证据时，接口仍返回 200，`verified_evidence` 为空数组，或文本字段值为 `"待确认"`，**不返回 4xx**。

---

## 典型调用流程（B 端参考）

```
用户打开飞书会议日历
        ↓
B 端读取 meeting_id
        ↓
POST /evidence/v1/meeting/context-package   ← 拿到背景包，渲染会前卡片
        ↓
会议结束，B 端拿到 minutes_id
        ↓
POST /evidence/v1/minutes/action-items      ← 拿到 Action Items，创建飞书任务
        ↓
每周一
        ↓
POST /evidence/v1/weekly/window-summary     ← 拿到周报内容，写入飞书文档
```

---

## Swagger UI

服务启动后访问：

```
http://localhost:8000/docs
```

可在线调试所有接口，无需 Postman。