#!/bin/bash

# OpenClaw 主动分发Agent 完整Demo一键运行脚本

echo "🚀 开始运行 OpenClaw 主动分发Agent 完整Demo"
echo "=================================================="

# 检查Python环境
if ! command -v python3 &> /dev/null
then
    echo "❌ 错误：未找到Python3，请先安装Python 3.10+"
    exit 1
fi

echo "✅ Python环境检查通过"

# 安装依赖
echo ""
echo "📦 安装项目依赖..."
pip install -r requirements.txt > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "⚠️  依赖安装失败，尝试使用poetry安装..."
    poetry install > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败，请手动安装依赖"
        exit 1
    fi
fi
echo "✅ 依赖安装完成"

# 创建输出目录
mkdir -p outputs/cards outputs/reports outputs/writes

echo ""
echo "=================================================="
echo "🧪 运行单元测试..."
python -m pytest tests/ --ignore=tests/test_integration_ab.py -v
if [ $? -ne 0 ]; then
    echo "❌ 单元测试失败"
    exit 1
fi
echo "✅ 单元测试全部通过"

echo ""
echo "=================================================="
echo "🎬 演示场景1：会前背景卡片"
echo "--------------------------------------------------"
python -m app.cli trigger pre-meeting --dry-run
echo "--------------------------------------------------"

echo ""
echo "🎬 演示场景2：会后行动项提取"
echo "--------------------------------------------------"
python -m app.cli trigger post-meeting --dry-run
echo "--------------------------------------------------"

echo ""
echo "🎬 演示场景3：周报洞察生成"
echo "--------------------------------------------------"
python -m app.cli trigger weekly-insight --dry-run
echo "--------------------------------------------------"

echo ""
echo "🎬 演示场景4：风险预警"
echo "--------------------------------------------------"
python -m app.cli trigger risk-alert --dry-run
echo "--------------------------------------------------"

echo ""
echo "=================================================="
echo "📊 生成效果验证报告"
echo "--------------------------------------------------"
python -m app.cli effect-report --output outputs/reports/final_demo_report.md
echo "✅ 效果报告已生成：outputs/reports/final_demo_report.md"
echo "--------------------------------------------------"

echo ""
echo "=================================================="
echo "🌐 启动API服务（端口8200）"
echo "--------------------------------------------------"
echo "服务启动后可以访问："
echo "  健康检查：http://localhost:8200/health"
echo "  API文档：http://localhost:8200/docs"
echo "  触发API示例："
echo "    curl -X POST http://localhost:8200/agent/v1/triggers/run \\"
echo "      -H \"Content-Type: application/json\" \\"
echo "      -d '{\"trigger_type\":\"manual\",\"scenario_type\":\"pre_meeting\",\"project_id\":\"alpha_report_platform\",\"dry_run\":true}'"
echo ""
echo "按 Ctrl+C 停止服务"
echo "--------------------------------------------------"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8200
