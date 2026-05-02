# OpenClaw Proactive Distribution Agent (Subsystem B)

## 概述
子系统B是OpenClaw团队知识脉冲助手的主动分发模块，负责将子系统A生成的证据转化为主动知识服务，实现会前背景推送、会后任务闭环、周报洞察、风险预警等功能。

## 核心功能
- 🎯 多模式触发：定时触发、事件触发、阈值触发、CLI手动触发
- 🚦 场景路由：会前背景、会后待办、周报洞察、风险预警、重点事项对账
- 🎫 卡片生成：飞书卡片、Markdown预览、证据来源绑定
- ✅ 任务闭环：任务预览、人工确认、飞书任务写入、多维表格同步
- 📊 反馈采集：用户行为埋点、效果指标统计
- 📈 Demo Dashboard：全链路展示、效果验证报告生成

## 快速开始
### 安装依赖
```bash
poetry install
```

### 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，配置A端服务地址和飞书相关配置
```

### 运行Demo
```bash
# 会前背景卡片Demo
python -m tkp_b trigger --scenario pre_meeting --dry-run

# 会后Action Items转任务Demo
python -m tkp_b trigger --scenario post_meeting --dry-run

# 每周风险洞察Demo
python -m tkp_b trigger --scenario weekly_insight --dry-run

# 风险预警Demo
python -m tkp_b trigger --scenario risk_alert --dry-run

# 启动Demo Dashboard
python -m tkp_b dashboard

# 生成效果验证报告
python -m tkp_b effect-report
```

### 启动API服务
```bash
make run-server
```
API文档地址：http://localhost:8000/docs

## 目录结构
```
openclaw-proactive-distribution-agent/
├── app/
│   ├── main.py              # FastAPI入口
│   ├── cli.py               # CLI入口
│   ├── config.py            # 配置文件
│   ├── clients/             # 外部客户端（AClient、飞书客户端）
│   ├── triggers/            # B01 场景触发器
│   ├── workflow/            # B02 场景路由与流程编排
│   ├── cards/               # B03/B06 卡片生成器（会前、周报、风险）
│   ├── tasks/               # B04 任务预览器
│   ├── writers/             # B05 飞书任务与多维表格写入器
│   ├── feedback/            # B10 反馈采集器
│   ├── reports/             # B12 效果验证报告生成器
│   └── dashboard/           # B11 Demo Dashboard
├── contracts/               # 接口合约定义
├── fixtures/
│   └── mock_a_responses/    # 子系统A mock响应数据
├── outputs/
│   ├── cards/               # 生成的卡片文件
│   └── reports/             # 生成的报告文件
├── tests/                   # 测试用例
├── README.md
├── Makefile
└── pyproject.toml
```

## API接口
- `POST /agent/v1/triggers/run` - 主动触发执行接口
- `POST /agent/v1/cards/preview` - 卡片预览接口
- `POST /agent/v1/tasks/confirm-create` - 任务创建确认接口
- `POST /agent/v1/feedback/events` - 反馈事件回传接口

详细接口文档请参考：[子系统B接口文档](../docs/子系统B/openclaw_proactive_distribution_agent_subsystem_plan.md)
