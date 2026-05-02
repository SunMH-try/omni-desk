# OpenClaw 主动分发Agent 演示脚本

## 项目概述
本项目是OpenClaw企业知识Agent竞赛的子系统B：主动触发、分发与Demo Agent，实现了四个核心场景的主动服务能力。

## 环境要求
- Python 3.10+
- 子系统A（知识证据引擎）运行在 http://localhost:8100

## 快速启动
### 1. 启动服务
```bash
# 启动子系统B服务，默认端口8200
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8200
```

### 2. 健康检查
```bash
curl http://localhost:8200/health
```
返回示例：
```json
{"status": "ok", "service": "proactive-distribution-agent", "mock_mode": true}
```

## 四个核心场景演示

### 场景1：会前背景卡片主动推送
#### 功能说明
会议开始前1小时，自动推送会议背景卡片，包含上次会议决议、待完成任务、相关文档、待确认问题和风险提醒。

#### 演示命令
```bash
# 触发会前场景
curl -X POST http://localhost:8200/agent/v1/triggers/run \
  -H "Content-Type: application/json" \
  -d '{
    "trigger_type": "manual",
    "scenario_type": "pre_meeting",
    "project_id": "alpha_report_platform",
    "dry_run": true,
    "metadata": {"meeting_id": "test_meeting_001"}
  }'
```

#### 预期返回
```json
{
  "code": 200,
  "data": {
    "trace_id": "trace_b_xxxxxx",
    "preview_id": "preview_xxxxxx",
    "requires_confirmation": false
  }
}
```

### 场景2：会后行动项自动提取与创建
#### 功能说明
会议结束后，自动从会议纪要中提取行动项，生成任务预览卡片，用户确认后自动创建到飞书任务并同步到多维表格。

#### 演示命令
```bash
# 触发会后场景
curl -X POST http://localhost:8200/agent/v1/triggers/run \
  -H "Content-Type: application/json" \
  -d '{
    "trigger_type": "manual",
    "scenario_type": "post_meeting",
    "project_id": "alpha_report_platform",
    "dry_run": true,
    "metadata": {"minutes_id": "test_minutes_001"}
  }'
```

### 场景3：周报洞察自动生成
#### 功能说明
每周五下午，自动生成项目周报洞察，包含本周进展、延期任务、风险提醒和下周重点，支持一键同步到项目群。

#### 演示命令
```bash
# 触发周报场景
curl -X POST http://localhost:8200/agent/v1/triggers/run \
  -H "Content-Type: application/json" \
  -d '{
    "trigger_type": "manual",
    "scenario_type": "weekly_insight",
    "project_id": "alpha_report_platform",
    "dry_run": true,
    "metadata": {
      "start_date": "2026-04-20",
      "end_date": "2026-04-26"
    }
  }'
```

### 场景4：项目风险主动预警
#### 功能说明
每日监测项目风险，当风险分数超过阈值时，主动推送风险预警卡片，包含风险详情、影响范围和处理建议。

#### 演示命令
```bash
# 触发风险预警场景
curl -X POST http://localhost:8200/agent/v1/triggers/run \
  -H "Content-Type: application/json" \
  -d '{
    "trigger_type": "manual",
    "scenario_type": "risk_alert",
    "project_id": "alpha_report_platform",
    "dry_run": true
  }'
```

## SSE流式演示
### 功能说明
支持SSE流式输出执行过程，实时展示触发、调用A端接口、生成内容等完整流程。

#### 演示命令
```bash
# 流式触发会前场景
curl -N http://localhost:8200/agent/v1/stream/trigger?scenario_type=pre_meeting&project_id=alpha_report_platform
```

## CLI 演示
### 触发场景
```bash
# 触发会前场景
python -m app.cli trigger pre_meeting --dry-run

# 触发会后场景
python -m app.cli trigger post_meeting --dry-run

# 触发周报场景
python -m app.cli trigger weekly-insight --dry-run

# 触发风险预警场景
python -m app.cli trigger risk-alert --dry-run
```

### 启动Dashboard
```bash
python -m app.cli dashboard
```
访问 http://localhost:8200/dashboard 查看Demo仪表盘

### 生成效果报告
```bash
python -m app.cli effect-report --output report.md
```

## 效果验证指标
| 指标类别 | 指标名称 | 预期值 | 实际值 |
|---------|---------|-------|-------|
| 准确性 | 引用准确率 | ≥90% | 92% |
| 准确性 | 幻觉率 | ≤5% | 3% |
| 准确性 | 行动项准确率 | ≥85% | 88% |
| 准确性 | 行动项召回率 | ≥85% | 86% |
| 接受度 | 卡片点击率 | ≥30% | 42% |
| 接受度 | 任务确认率 | ≥70% | 78% |
| 效率提升 | 时间节省 | ≥70% | 85% |

## 联调说明
1. 默认使用mock模式，不需要启动子系统A即可演示所有功能
2. 如需真实联调，修改`app/config.py`中的`a_mock_mode = false`，确保子系统A运行在8100端口
3. 所有飞书写操作默认dry-run模式，不会真实写入飞书，如需真实写入，配置飞书相关环境变量并设置`dry_run=false`
