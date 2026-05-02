# OpenClaw Proactive Distribution Agent Subsystem Plan

> 中文名称：子系统 B：主动触发、分发与 Demo Agent  
> 英文名称：OpenClaw Proactive Distribution Agent  
> 适合负责角色：开发者 B  
> 并行开发定位：先基于子系统 A 的 mock 证据完成触发、卡片、任务、周报、反馈和 Demo，再与子系统 A 的真实证据 API 合并联调。

## 1. 文档目标

本项目基于前一版 Team Knowledge Pulse Agent 方案继续拆分与增强。项目主方向为飞书 OpenClaw 赛道的“会议与项目的全链路伴侣”，同时融合“周期性智能总结与洞察”和“团队待办中枢与进展自动对账”。最终作品不是一个普通聊天 Bot，而是一个能够主动读取飞书 Docs、Minutes、消息、任务、日历和多维表格，并把分散信息转化为可引用、可追踪、可推送、可执行知识产物的办公 Agent。

本文件只描述子系统 B。子系统 B 的核心职责是把证据转化为主动知识服务：什么时候触发、推给谁、以什么卡片形态推送、是否需要创建任务、是否需要更新多维表格、如何采集用户反馈、如何展示 Demo。它不负责底层文档解析、PageIndex 树索引、证据判断和知识原子抽取，这些由子系统 A 提供。

## 2. 子系统 B 的边界

### 2.1 负责内容

- 定时触发、事件触发、阈值触发和手动 CLI/OpenClaw 触发。
- 场景路由：会前背景、会后待办、周报洞察、风险预警、重点事项对账。
- 调用子系统 A 的证据 API，并将证据转换为面向用户的卡片、任务和文档。
- 飞书卡片 JSON、Markdown 预览、OpenClaw 对话入口和 CLI 演示命令。
- 任务创建预览、人工确认、飞书任务写入、多维表格同步。
- 用户反馈采集：卡片点击、证据点击、任务确认、评分、忽略、驳回原因。
- Demo Dashboard、答辩演示脚本和效果验证报告生成。

### 2.2 不负责内容

- 不负责直接解析文档、会议纪要和群聊原文。
- 不负责判断证据是否真实支持结论。
- 不负责跨源检索算法和 PageIndex 树遍历。
- 不负责知识原子生成和 Evidence Graph 构建。
- 不负责评测数据人工标注，但需要采集用户接受度和效率对比数据。

## 3. 场景定义文档：子系统 B 视角

子系统 B 面向实际用户交互，核心场景是“知识在正确时间主动到达正确的人”。目标用户包括项目经理、产品经理、研发负责人、测试负责人和团队管理者。它需要把子系统 A 输出的证据转化为可理解、可点击、可确认、可执行的知识产物。

通用搜索无法满足该场景，因为用户通常不会在会议前主动搜索所有相关文档，也不会在会议后手动把所有待办复制成任务。普通问答无法满足该场景，因为它缺少主动触发、缺少写入动作、缺少任务闭环和效果反馈。子系统 B 的价值是把“证据”变成“行动”：会前让参会人快速对齐，会后让 Action Items 进入任务系统，每周让管理者看到进展和风险。

## 4. 总体架构

子系统 B 建议采用 FastAPI + CLI + Card Renderer + Feishu Writer + Feedback Tracker 的结构。开发初期通过 `mock_a_server` 或本地 JSON 使用 A 端接口样例，保证 B 端不等待 A 端完成即可独立开发。合并阶段只需要把 `A_BASE_URL` 从 mock 地址切换为真实服务地址。

主流程如下：

1. B01 触发器收到定时、事件、阈值或手动命令。
2. B02 场景路由器判断该走会前、会后、周报还是风险流程。
3. B02 调用子系统 A 的证据接口。
4. B03/B04/B06/B07 根据证据生成卡片、任务预览或周报。
5. B09 进入人工审核和确认。
6. B05 执行飞书任务或多维表格写入。
7. B10 采集用户反馈。
8. B11 Demo Dashboard 展示完整链路。
9. B12 合成效果验证报告。

## 5. API 合约

### B-API-01 主动触发执行接口

- 路径：`/agent/v1/triggers/run`
- 说明：用于定时、事件、阈值触发后启动上层 Agent 流程。

请求示例：

```json
{
  "trigger_type": "schedule",
  "scenario_type": "weekly_insight",
  "project_id": "alpha_report_platform",
  "dry_run": true
}
```

响应示例：

```json
{
  "code": 200,
  "data": {
    "trace_id": "trace_b_001",
    "preview_id": "preview_weekly_001",
    "requires_confirmation": true
  }
}
```

### B-API-02 卡片预览接口

- 路径：`/agent/v1/cards/preview`
- 说明：用于生成飞书卡片 JSON 和本地预览。

请求示例：

```json
{
  "scenario_type": "pre_meeting",
  "meeting_context_id": "ctx_meeting_001",
  "evidence_ids": [
    "ev_doc_001",
    "ev_task_003"
  ],
  "target_chat_id": "chat_alpha_demo"
}
```

响应示例：

```json
{
  "code": 200,
  "data": {
    "preview_id": "preview_card_001",
    "card_title": "Alpha 项目周会会前背景",
    "dry_run": true
  }
}
```

### B-API-03 任务创建确认接口

- 路径：`/agent/v1/tasks/confirm-create`
- 说明：用于人工确认后将 Action Items 写入飞书任务和多维表格。

请求示例：

```json
{
  "preview_id": "task_preview_001",
  "confirmed_items": [
    "ai_001"
  ],
  "target_task_group": "Alpha 项目任务组"
}
```

响应示例：

```json
{
  "code": 200,
  "data": {
    "created_tasks": [
      {
        "task_id": "task_001",
        "title": "补充接口压测报告",
        "owner": "user_rd"
      }
    ],
    "bitable_updated": true
  }
}
```

### B-API-04 反馈事件回传接口

- 路径：`/agent/v1/feedback/events`
- 说明：用于效果验证报告统计卡片点击率、证据点击率和任务确认率。

请求示例：

```json
{
  "card_id": "card_weekly_001",
  "event_type": "click_evidence",
  "user_id": "user_pm",
  "evidence_id": "ev_task_003"
}
```

响应示例：

```json
{
  "code": 200,
  "data": {
    "feedback_event_id": "fb_001",
    "accepted": true
  }
}
```


## 6. 产品流程设计

### 6.1 会前背景卡片流程

会议前 30 分钟，系统根据日历事件识别会议主题和参会人，调用子系统 A 的会议上下文包接口，获取历史决议、相关文档、未完成任务、开放风险和待确认问题。子系统 B 将这些证据压缩为一张飞书会前卡片，推送到会议群或参会人私聊。卡片中每条结论都带来源编号，用户可点击查看原始文档或任务。

### 6.2 会后 Action Items 转任务流程

会议纪要生成后，系统收到 minutes_created 事件，调用子系统 A 的 Action Item 抽取接口。B 端先生成任务创建预览，展示标题、负责人、截止时间、优先级、来源链接和置信度。如果字段缺失，则要求人工补齐。用户确认后，B 端调用飞书任务 API 创建任务，并同步更新项目重点事项推进表。

### 6.3 每周风险洞察流程

每周五 17:00，系统调用子系统 A 的周报窗口聚合接口，获取本周文档变化、会议决议、任务状态、风险点和群聊阻塞。B 端生成周报洞察卡片，包含本周进展、延期任务、下周风险、需要管理者确认的问题和证据链接。同时将详细版本沉淀为飞书文档，便于后续追溯。

### 6.4 阈值风险预警流程

当同一个风险在任务评论和群聊中反复出现，或任务延期超过配置天数，B 端根据风险规则计算分数。超过阈值后，系统主动生成风险预警卡片，提醒项目负责人处理。风险卡片必须说明触发原因，例如“接口联调任务延期 2 天 + 群聊中 3 次提到测试环境权限问题”。

## 7. 模块详细设计

### B01 场景触发器

**模块目标：** 实现定时触发、事件触发和阈值触发，为会前背景、会后任务、周报洞察和风险预警提供入口。

**输入：**
- trigger_config.yaml
- event_payload
- threshold_state

**输出：**
- trigger_context
- scenario_type
- trace_id

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 定时触发生成 weekly_insight
- minutes_created 触发 post_meeting
- risk_score 超阈值触发 risk_alert

### B02 场景路由与流程编排器

**模块目标：** 根据触发类型和用户指令选择会前、会后、周报、风险预警或问答流程，并调用 A 端接口。

**输入：**
- trigger_context
- user_command
- scenario_policy

**输出：**
- workflow_plan
- a_api_request_list
- agent_trace

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 会前触发调用 A-API-02
- 会后触发调用 A-API-03
- 周报触发调用 A-API-04

### B03 会前背景卡片生成器

**模块目标：** 将 A 端 meeting_context_package 组织成飞书卡片，包含会议目标、上次决议、未完成任务、待确认问题和风险提醒。

**输入：**
- meeting_context_package
- verified_evidence_list
- target_chat_id

**输出：**
- premeeting_card_json
- card_markdown
- evidence_link_map

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 每条关键结论显示来源编号
- 卡片不超过 6 个区块
- 无证据事实不写成确定结论

### B04 会后行动项任务预览器

**模块目标：** 把 A 端 Action Items 转化为飞书任务创建预览，展示负责人、截止时间、来源链接和需要人工确认的缺失字段。

**输入：**
- action_item_list
- project_member_map
- task_policy

**输出：**
- task_preview_list
- missing_field_ui
- duplicate_warning

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 没有 owner 的待办进入待确认
- 重复任务需要提示
- 每个任务带 minutes evidence link

### B05 飞书任务与多维表格写入器

**模块目标：** 用户确认后将待办写入飞书任务，并同步更新重点事项推进表。

**输入：**
- confirmed_task_preview
- task_group_id
- bitable_id

**输出：**
- created_task_list
- bitable_update_result
- write_trace

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- dry-run 不真实写入
- 确认模式写入测试空间
- 写入失败可重试或回滚记录

### B06 周报洞察卡片生成器

**模块目标：** 基于 A 端 weekly_window_summary 生成每周工作总结、下周风险洞察和重点事项更新卡片。

**输入：**
- weekly_material
- project_goal
- target_chat_id

**输出：**
- weekly_card_json
- weekly_doc_markdown
- risk_table

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 卡片包含本周进展、风险、下周重点
- 每个风险有 evidence_id
- 支持生成飞书文档版本

### B07 风险预警与阈值规则器

**模块目标：** 根据风险原子、延期任务和群聊阻塞次数计算风险分数，超过阈值时主动生成预警卡片。

**输入：**
- risk_atoms
- task_snapshot
- message_thread_stats
- risk_policy.yaml

**输出：**
- risk_score
- risk_alert_card
- alert_reason

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 延期超过 2 天风险升高
- 同一 blocker 多次出现风险升高
- 低置信度风险只提示待确认

### B08 OpenClaw/CLI 交互入口

**模块目标：** 提供比赛演示入口，让评委通过 CLI 或 OpenClaw 对话触发会前、会后、周报和风险流程。

**输入：**
- command_args
- openclaw_session
- demo_profile

**输出：**
- workflow_result
- preview_url_or_path
- trace_id

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- CLI 命令可运行
- OpenClaw 指令可映射到场景
- 异常时给出清晰提示

### B09 卡片人工审核与确认器

**模块目标：** 所有推送和写入前进入预览态，让用户确认、修改、拒绝或只保存为文档。

**输入：**
- card_preview
- task_preview
- user_action

**输出：**
- confirmed_operation
- rejected_operation
- review_trace

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 未确认不得写入飞书
- 拒绝原因要记录
- 修改后重新生成 preview_id

### B10 反馈采集与效果埋点器

**模块目标：** 采集卡片点击、证据点击、任务确认、用户评分、推送打开率等数据，为效果验证报告提供用户接受度指标。

**输入：**
- card_event
- task_event
- user_rating

**输出：**
- feedback_event
- metric_log
- acceptance_stat

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 点击证据记录 evidence_id
- 任务确认记录 action_item_id
- 评分关联 card_id

### B11 Demo Dashboard

**模块目标：** 提供本地演示面板，展示触发事件、A 端证据、生成卡片、写入结果、反馈指标和 trace 日志。

**输入：**
- agent_trace
- card_json
- feedback_metrics

**输出：**
- dashboard_page
- demo_screenshot
- explainable_trace_view

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 能展示完整链路
- 能展示证据来源
- 能展示效果指标

### B12 效果验证报告生成器

**模块目标：** 把 A 端准确性指标和 B 端交互指标合并为比赛效果验证报告。

**输入：**
- evaluation_report_json
- feedback_metrics
- baseline_time_log

**输出：**
- final_effect_report.md
- metric_summary_table
- case_study_list

**开发要求：**
- 每个模块必须可以独立运行，并能读取 `fixtures/` 中的本地样例数据。
- 模块输出必须为稳定 JSON，不允许在联调阶段频繁改字段。
- 如果调用大模型，需要记录 prompt 名称、模型名称、耗时、token 用量和失败重试信息。
- 如果使用飞书数据，需要保留 source_type、source_id、source_url、updated_at 和 permission_scope。
- 如果产生面向用户的结论，必须绑定 evidence_id；没有证据的结论只能标记为“待确认”。

**测试要求：**
- 包含准确性、接受度、效率提升
- 有 baseline 对比
- 至少列出 3 个案例


## 8. 可运行 Demo：子系统 B 独立演示

子系统 B 的 Demo 可以不依赖子系统 A 的真实服务，先使用 `fixtures/mock_a_responses/` 中的 JSON 作为证据输入。建议提供以下命令：

```bash
python -m tkp_b trigger --scenario pre_meeting --dry-run
python -m tkp_b trigger --scenario post_meeting --dry-run
python -m tkp_b trigger --scenario weekly_insight --dry-run
python -m tkp_b trigger --scenario risk_alert --dry-run
python -m tkp_b dashboard
python -m tkp_b effect-report
```

主动触发方式建议至少实现两种：第一种是定时触发，例如每周五生成周报；第二种是事件触发，例如会议纪要生成后自动创建任务预览。阈值触发作为增强项，用于展示风险预警能力。

## 9. 测试方案

### 9.1 单元测试

- B01：不同 trigger_type 能路由到正确 scenario_type。
- B03：会前卡片必须包含会议目标、背景事实、风险和证据链接。
- B04：Action Items 能生成任务预览，缺失字段进入待确认状态。
- B05：dry-run 模式不会写入真实飞书。
- B06：周报卡片能覆盖进展、风险、下周重点。
- B10：点击事件能记录 card_id、evidence_id、user_id。

### 9.2 合约测试

- 使用 mock A 响应测试 B 端所有流程。
- A 端接口字段缺失时，B 端应降级为“证据不足，待人工确认”。
- A 端返回 conflict_report 时，B 端卡片必须展示“信息冲突”，不能强行合并结论。
- A 端返回 NO_RELEVANT_EVIDENCE 时，B 端不得生成确定性结论。

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

## 10. 与子系统 A 的合并联调准备

- B 端先使用 mock A 响应文件开发，所有响应文件放在 `fixtures/mock_a_responses/`。
- B 端所有调用统一通过 `AClient`，禁止业务模块直接拼接 A 端 URL。
- 合并前双方冻结 `contracts/` 中的请求和响应样例。
- 联调时先验证 dry-run 卡片，不直接写入飞书。
- B 端将 card_id、feedback_event、task_id 回传，供 A 端和完整项目效果评估使用。

## 11. 推荐目录结构

```text
openclaw-proactive-distribution-agent/
  app/
    main.py
    clients/
    triggers/
    workflow/
    cards/
    tasks/
    writers/
    feedback/
    reports/
    dashboard/
  contracts/
  fixtures/mock_a_responses/
  outputs/cards/
  outputs/reports/
  tests/
  README.md
  Makefile
```

## 12. 阶段计划

- P0：完成 CLI、mock AClient、会前卡片和本地预览。
- P1：完成会后 Action Items 任务预览和确认流程。
- P2：完成周报洞察、风险预警和反馈采集。
- P3：完成 Dashboard、效果验证报告和合并联调。

## 13. 最终验收标准

子系统 B 可以在没有真实飞书写入权限的情况下，通过 mock 数据展示完整主动知识服务流程；也可以在接入真实 A 端 API 后，生成带证据来源的卡片、任务预览和效果验证报告。它应让评委直接看到项目不是普通问答，而是能够主动触发、主动分发、推动任务闭环的办公 Agent。
