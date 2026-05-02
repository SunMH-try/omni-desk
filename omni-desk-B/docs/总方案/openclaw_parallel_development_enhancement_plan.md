# OpenClaw Parallel Development Enhancement Plan

> 中文名称：完整项目内容增强方案与双人并行开发联调计划  
> 英文名称：OpenClaw Parallel Development Enhancement Plan  
> 项目名称：Team Knowledge Pulse Agent / 团队知识脉冲助手  
> 适用对象：两名开发者协作参加飞书 OpenClaw 企业办公知识整合与分发 Agent 挑战赛  
> 文档目标：在两个子系统方案基础上，给出完整项目增强版架构、接口边界、测试流程、交付物组织和最终合并验收标准。

## 1. 总体说明

本项目基于前一版 Team Knowledge Pulse Agent 方案继续拆分与增强。项目主方向为飞书 OpenClaw 赛道的“会议与项目的全链路伴侣”，同时融合“周期性智能总结与洞察”和“团队待办中枢与进展自动对账”。最终作品不是一个普通聊天 Bot，而是一个能够主动读取飞书 Docs、Minutes、消息、任务、日历和多维表格，并把分散信息转化为可引用、可追踪、可推送、可执行知识产物的办公 Agent。

完整项目拆分为两个并行子系统。子系统 A 是 OpenClaw Knowledge Evidence Engine，负责知识接入、权限过滤、结构化解析、PageIndex 树索引、知识原子、证据图谱、检索、Action Item 抽取和效果评测。子系统 B 是 OpenClaw Proactive Distribution Agent，负责主动触发、场景路由、飞书卡片、任务预览、任务写入、多维表格同步、用户反馈、Demo Dashboard 和最终效果报告。

这种拆分的核心优势是两个人可以同时开发：A 端先输出 mock evidence JSON，B 端基于 mock evidence 开发卡片和任务流程；B 端先固定 AClient 调用接口，A 端按照 contracts 实现真实服务。双方通过 contracts、fixtures、trace_id 和 evidence_id 进行合并，不需要在早期互相等待。

## 2. 最终比赛方案定位

主方向为方向 B：会议与项目的全链路伴侣。增强方向为方向 A：周期性智能总结与洞察，以及方向 D：团队待办中枢与进展自动对账。最终作品不是一个普通聊天 Bot，而是一个主动知识服务系统。

核心演示闭环为：

1. 会前背景卡片：会议前自动推送上次决议、相关文档、未完成任务和风险。
2. 会后 Action Items 闭环：会议纪要生成后自动抽取待办，创建任务预览，确认后写入飞书任务和多维表格。
3. 每周风险洞察：每周定时汇总文档变更、会议结论、任务状态和群聊阻塞，生成周报卡片和风险预警。

## 3. 双子系统职责总览

| 子系统 | 英文名称 | 主要负责 | 不负责 | 可独立 Demo |
|---|---|---|---|---|
| 子系统 A | OpenClaw Knowledge Evidence Engine | 数据读取、权限过滤、解析、PageIndex、知识原子、证据图谱、检索、Action Item 抽取、评测 | 卡片 UI、任务写入、Dashboard、用户反馈 | 命令行查询证据、抽取待办、生成周报素材 |
| 子系统 B | OpenClaw Proactive Distribution Agent | 触发器、场景路由、会前卡片、会后任务预览、飞书写入、反馈埋点、Dashboard、效果报告 | 文档解析、检索算法、证据真实性判断 | 使用 mock A 数据生成卡片、任务预览和周报 |

## 4. 完整项目增强架构

完整项目在前一版方案基础上增加四个工程化增强点。

第一，加入双层 mock 机制。A 端可以使用本地飞书 fixture，不依赖真实飞书权限；B 端可以使用 A 端 mock response，不依赖 A 端服务完成。第二，加入合约测试机制。所有接口字段都在 `contracts/` 中维护，字段变更必须先改合约。第三，加入统一 trace 机制。每次触发、检索、生成、写入、反馈都共享 trace_id，答辩时可以回放完整链路。第四，加入效果验证自动化。A 端输出准确性指标，B 端输出接受度指标，最终合成效果验证报告。

完整链路如下：

```text
飞书数据 / Demo Fixtures
  -> 子系统 A：读取、解析、索引、知识原子、证据判断
  -> A API：meeting_context / action_items / weekly_window / evidence_query
  -> 子系统 B：触发、路由、卡片、任务预览、人工确认、写入
  -> 飞书群 / 飞书任务 / 多维表格 / 飞书文档 / Dashboard
  -> 反馈事件与效果指标
  -> 最终效果验证报告
```

## 5. 合并接口矩阵

| 方向 | 数据对象 | 用途 | 合约要求 |
|---|---|---|---|
| A -> B | verified_evidence_list | 卡片生成、周报生成、风险预警 | 必须包含 evidence_id、source_url、support_level |
| A -> B | action_item_list | 任务创建预览 | 必须包含 owner、deadline、missing_fields、confidence |
| A -> B | weekly_material | 每周洞察 | 必须包含 weekly_atoms、risk_summary、evidence_ids |
| B -> A | feedback_event | 效果评估 | 必须包含 card_id、event_type、evidence_id、user_id |
| B -> A | created_task_result | Action Item 闭环评估 | 必须包含 action_item_id、task_id、status |

## 6. 统一数据对象

### 6.1 trace_id

所有请求必须携带 trace_id。如果是用户主动触发，由 B 端生成；如果是 A 端事件触发入库，由 A 端生成并传递给 B 端。trace_id 用于串联数据读取、证据检索、卡片生成、任务写入和反馈事件。

### 6.2 evidence_id

所有卡片事实、周报结论、任务创建建议都必须引用 evidence_id。没有 evidence_id 的内容只能以“推测”“待确认”“建议检查”形式出现，不能写成确定事实。

### 6.3 preview_id

所有写操作先生成 preview_id。只有用户确认或配置允许自动写入时，preview_id 才能转换为真实写操作。

### 6.4 feedback_event

所有用户交互都以 feedback_event 记录，包括点击证据、确认任务、忽略卡片、评分、驳回和修改。

## 7. 推荐仓库结构

```text
team-knowledge-pulse-agent/
  apps/
    knowledge-evidence-engine/
    proactive-distribution-agent/
  packages/
    shared-contracts/
    shared-schemas/
    shared-tracing/
  fixtures/
    alpha-demo-project/
  contracts/
    a_to_b/
    b_to_a/
  docs/
    scenario_definition.md
    runnable_demo_guide.md
    effect_validation_report.md
  scripts/
    run_full_demo.sh
    run_contract_tests.sh
  README.md
```

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

## 9. 可运行 Demo 总流程

### 9.1 Demo 数据准备

建议准备一个模拟项目“Alpha 智能报表平台”。数据至少包含 3 篇飞书文档、2 份会议纪要、1 个包含 30-50 条消息的飞书群聊、8 条飞书任务、1 个日历会议和 1 张重点事项推进表。数据中必须故意设置几个可被 Agent 发现的事实：接口字段发生变更、测试环境权限导致延期、上次会议仍有待确认问题、某个任务负责人缺失。

### 9.2 一键演示命令

```bash
cd apps/knowledge-evidence-engine
make seed-demo-data
make build-index
make run-mock-server

cd ../proactive-distribution-agent
export A_BASE_URL=http://localhost:8010
python -m tkp_b trigger --scenario pre_meeting --dry-run
python -m tkp_b trigger --scenario post_meeting --dry-run
python -m tkp_b trigger --scenario weekly_insight --dry-run
python -m tkp_b dashboard
```

### 9.3 演示脚本

第一步展示普通搜索的不足：面对 Alpha 周会，用户不知道要搜索哪些文档、群聊和会议纪要。第二步展示会前卡片：系统自动拉取上次会议、未完成任务、近期风险和相关文档。第三步展示会后任务闭环：系统从会议纪要中抽取 Action Items，生成任务预览，用户确认后写入任务和推进表。第四步展示周报洞察：系统定时生成本周总结、风险和下周重点。第五步展示效果指标：准确性、点击率、任务确认率和节省时间。

## 10. 效果验证报告完整设计

| 指标类别 | 指标 | 负责子系统 | 计算方式 | 目标值 |
|---|---|---|---|---|
| 准确性 | Citation Accuracy | A | 被证据支持的结论数 / 总结论数 | >= 90% |
| 准确性 | Hallucination Rate | A | 无证据事实数 / 总事实数 | <= 5% |
| 待办质量 | Action Item Precision | A | 正确待办数 / 抽取待办数 | >= 85% |
| 待办质量 | Action Item Recall | A | 抽取真实待办数 / 标注真实待办数 | >= 85% |
| 接受度 | Card Click Rate | B | 点击卡片详情人数 / 接收卡片人数 | >= 30% |
| 接受度 | Task Confirmation Rate | B | 确认任务数 / 任务预览数 | >= 70% |
| 效率 | Time Saving | A+B | 1 - Agent 用时 / 人工整理用时 | >= 50% |
| 满意度 | User Rating | B | 用户评分均值 | >= 4.0/5 |

## 11. 合并联调计划

| 阶段 | 名称 | 目标 | 验收物 | 建议时间 |
|---|---|---|---|---|
| P0 | 并行起步 | 两端都能使用本地 fixture 跑通 | A 输出证据 JSON；B 使用 mock 证据生成卡片 | 第 1-2 天 |
| P1 | 合约冻结 | 双方确认 API 字段和错误码 | contracts/ 目录固定；自动合约测试通过 | 第 3 天 |
| P2 | 单向联调 | B 调用 A 的真实 mock server | 会前卡片、任务预览、周报均能由真实 A 输出驱动 | 第 4-5 天 |
| P3 | 写入联调 | B 在测试空间执行任务创建和表格更新 | 写入成功且 trace 可回放 | 第 6 天 |
| P4 | 效果验证 | 生成准确性、接受度、效率提升报告 | final_effect_report.md 和 dashboard 截图 | 第 7 天 |
| P5 | 答辩封装 | 打包 Demo、README、演示脚本和录屏 | 一键运行命令和故障兜底方案 | 第 8 天 |

## 12. 开发任务拆分

### 12.1 开发者 A 任务清单

- 完成飞书数据 fixture 规范。
- 完成读取适配器、权限过滤、结构化解析。
- 完成 PageIndex 树索引和摘要。
- 完成知识原子抽取、Evidence Graph 和检索。
- 完成 Action Item 抽取和周报素材聚合。
- 完成 A 端 mock server 和合约测试。
- 完成准确性评测和人工标注样例。

### 12.2 开发者 B 任务清单

- 完成 CLI/OpenClaw 触发入口。
- 完成 trigger engine 和 scenario router。
- 完成会前卡片、会后任务预览、周报洞察卡片。
- 完成任务写入、多维表格同步和 dry-run 模式。
- 完成反馈采集和 Demo Dashboard。
- 完成 B 端 mock AClient 和合约测试。
- 完成效果验证报告生成器和答辩演示脚本。

## 13. 测试体系

### 13.1 单元测试

每个模块至少包含正常路径、空结果路径、异常路径三类测试。A 端重点测解析、索引、检索和证据判断；B 端重点测触发、路由、卡片、任务预览和反馈。

### 13.2 合约测试

合约测试是双人协作最关键的测试。任何接口字段变更都必须先修改 contracts，再修改代码。合约测试通过后才能合并。

### 13.3 集成测试

集成测试分三层。第一层是 B 端调用 mock A 文件；第二层是 B 端调用 A 端 mock server；第三层是 B 端调用 A 端真实服务，并写入飞书测试空间。

### 13.4 Demo 回归测试

```bash
bash scripts/run_contract_tests.sh
bash scripts/run_full_demo.sh --dry-run
bash scripts/run_effect_report.sh
```

## 14. 风险与兜底方案

| 风险 | 影响 | 兜底方案 |
|---|---|---|
| 飞书真实 API 权限不足 | Demo 无法读取真实数据 | 使用 fixtures 和 mock server 完成可运行 Demo |
| A 端索引耗时较长 | B 端无法等待真实结果 | 预构建索引并缓存输出 |
| B 端写入任务失败 | 会后闭环无法展示 | 使用 dry-run 预览和本地写入结果模拟 |
| LLM 输出不稳定 | 卡片质量波动 | 固定 Demo 数据、固定 prompt、保存 golden output |
| 字段合约变更 | 双方联调失败 | contracts 先行，任何变更需同步版本号 |
| 卡片内容过长 | 用户接受度下降 | 使用 3 层展示：卡片摘要、展开详情、源文档链接 |

## 15. 最终提交检查清单

- 场景定义文档已完成，能清晰说明方向 B 主线、方向 A/D 增强和通用问答不足。
- 可运行 Demo 已完成，至少包含定时触发或事件触发中的一种。
- 效果验证报告已完成，包含准确性、接受度和效率提升三类指标。
- A 端和 B 端均可独立运行。
- 合约测试和 dry-run 全流程通过。
- 卡片中的关键结论都有 evidence_id。
- 写操作默认 dry-run，确认后才写入测试空间。
- Dashboard 或日志能展示完整 trace。
- README 包含环境配置、运行命令、演示脚本和常见问题。

## 16. 最终项目增强建议

1. 证据冲突展示：当会议纪要和群聊对同一问题说法不一致时，卡片显示“存在冲突”，并列出来源。
2. 角色化推送：项目经理看到风险和阻塞，研发看到待办和接口变更，管理者看到周报和里程碑。
3. 反馈学习：如果用户经常忽略某类卡片，系统降低推送频率；如果用户经常点击某类证据，系统提高其优先级。
4. 一键沉淀：会后确认的结论自动写入飞书知识文档，形成项目 FAQ。
5. 答辩 Trace 回放：点击 trace_id 展示从触发、检索、证据判断、卡片生成到用户反馈的完整链路。

## 17. 结论

拆分后的项目既能支持两个人并行开发，又能保证最终 Demo 不割裂。子系统 A 保障可信知识，子系统 B 保障主动分发和任务闭环。完整项目最终体现的是“企业办公知识整合与分发 Agent”的核心价值：不是让用户多一个聊天框，而是让关键知识在正确时间、以正确形式、带着证据和行动入口主动到达团队。
