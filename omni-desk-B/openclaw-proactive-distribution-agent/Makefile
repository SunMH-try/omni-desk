.PHONY: install run-server run-cli test lint format demo-pre demo-post demo-weekly demo-risk dashboard report

# 安装依赖
install:
	poetry install

# 启动FastAPI服务
run-server:
	poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 运行CLI
run-cli:
	poetry run python -m tkp_b

# 运行测试
test:
	poetry run pytest tests/ -v

# 代码检查
lint:
	poetry run flake8 app/ tests/
	poetry run mypy app/ tests/

# 代码格式化
format:
	poetry run black app/ tests/

# Demo：会前背景卡片
demo-pre:
	poetry run python -m tkp_b trigger --scenario pre_meeting --dry-run

# Demo：会后任务预览
demo-post:
	poetry run python -m tkp_b trigger --scenario post_meeting --dry-run

# Demo：周报洞察
demo-weekly:
	poetry run python -m tkp_b trigger --scenario weekly_insight --dry-run

# Demo：风险预警
demo-risk:
	poetry run python -m tkp_b trigger --scenario risk_alert --dry-run

# 启动Dashboard
dashboard:
	poetry run python -m tkp_b dashboard

# 生成效果报告
report:
	poetry run python -m tkp_b effect-report

# 运行所有Demo
demo-all: demo-pre demo-post demo-weekly demo-risk
