from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
import os
from app.reports.effect_report_generator import effect_report_generator

app = FastAPI(title="OpenClaw Demo Dashboard")

# 静态文件和模板路径
dashboard_dir = Path(__file__).parent
static_dir = dashboard_dir / "static"
templates_dir = dashboard_dir / "templates"
outputs_dir = Path(__file__).parent.parent.parent / "outputs"

static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# 创建默认的HTML模板
def create_default_template():
    template_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Demo Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <header class="mb-8">
            <h1 class="text-3xl font-bold text-gray-800">🔍 OpenClaw Demo Dashboard</h1>
            <p class="text-gray-600 mt-2">团队知识脉冲助手 - 子系统B演示面板</p>
        </header>

        <!-- 指标卡片 -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {% for metric in metrics %}
            <div class="bg-white rounded-lg shadow p-6">
                <div class="text-sm text-gray-600 mb-1">{{ metric.name }}</div>
                <div class="text-3xl font-bold {% if metric.passed %}text-green-600{% else %}text-red-600{% endif %}">
                    {{ metric.value }}{{ metric.unit }}
                </div>
                <div class="text-xs text-gray-500 mt-1">目标: {{ metric.target }}</div>
            </div>
            {% endfor %}
        </div>

        <!-- 场景展示 -->
        <div class="bg-white rounded-lg shadow mb-8">
            <div class="p-6 border-b">
                <h2 class="text-xl font-semibold">🎯 核心场景演示</h2>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 p-6">
                <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                    <h3 class="font-medium text-lg mb-2">📅 会前背景卡片</h3>
                    <p class="text-gray-600 text-sm mb-3">会议前自动推送上次决议、相关文档、未完成任务和风险提醒</p>
                    <a href="/demo/pre_meeting" class="text-blue-600 text-sm hover:underline">查看Demo →</a>
                </div>
                <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                    <h3 class="font-medium text-lg mb-2">📋 会后任务闭环</h3>
                    <p class="text-gray-600 text-sm mb-3">会议纪要生成后自动抽取待办，生成任务预览，确认后写入飞书任务</p>
                    <a href="/demo/post_meeting" class="text-blue-600 text-sm hover:underline">查看Demo →</a>
                </div>
                <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                    <h3 class="font-medium text-lg mb-2">📊 每周风险洞察</h3>
                    <p class="text-gray-600 text-sm mb-3">每周定时汇总文档变更、会议结论、任务状态和群聊阻塞</p>
                    <a href="/demo/weekly_insight" class="text-blue-600 text-sm hover:underline">查看Demo →</a>
                </div>
                <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                    <h3 class="font-medium text-lg mb-2">🚨 风险预警</h3>
                    <p class="text-gray-600 text-sm mb-3">风险超过阈值时主动生成预警卡片，提醒项目负责人处理</p>
                    <a href="/demo/risk_alert" class="text-blue-600 text-sm hover:underline">查看Demo →</a>
                </div>
            </div>
        </div>

        <!-- 最近输出 -->
        <div class="bg-white rounded-lg shadow mb-8">
            <div class="p-6 border-b">
                <h2 class="text-xl font-semibold">📁 最近生成的文件</h2>
            </div>
            <div class="p-6">
                <table class="w-full">
                    <thead>
                        <tr class="text-left text-sm text-gray-600">
                            <th class="pb-3">文件名</th>
                            <th class="pb-3">类型</th>
                            <th class="pb-3">修改时间</th>
                            <th class="pb-3">大小</th>
                        </tr>
                    </thead>
                    <tbody class="text-sm">
                        {% for file in recent_files %}
                        <tr class="border-t">
                            <td class="py-3">
                                <a href="/output/{{ file.path }}" class="text-blue-600 hover:underline">{{ file.name }}</a>
                            </td>
                            <td class="py-3 text-gray-600">{{ file.type }}</td>
                            <td class="py-3 text-gray-600">{{ file.mtime }}</td>
                            <td class="py-3 text-gray-600">{{ file.size }}KB</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 效果报告 -->
        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b flex justify-between items-center">
                <h2 class="text-xl font-semibold">📈 效果验证报告</h2>
                <a href="/generate-report" class="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700">
                    生成最新报告
                </a>
            </div>
            <div class="p-6">
                <p class="text-gray-600">
                    点击上方按钮生成完整的效果验证报告，包含准确性、接受度、效率提升三类指标和案例分析。
                </p>
            </div>
        </div>
    </div>
</body>
</html>
    """
    
    template_path = templates_dir / "dashboard.html"
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(template_content)

# 创建模板文件
create_default_template()

def get_metrics():
    """获取指标数据"""
    report_data = effect_report_generator.default_metrics
    metrics = []
    
    key_metrics = [
        ("Citation Accuracy", report_data["准确性"]["Citation Accuracy"]),
        ("Hallucination Rate", report_data["准确性"]["Hallucination Rate"]),
        ("Task Confirmation Rate", report_data["接受度"]["Task Confirmation Rate"]),
        ("Time Saving", report_data["效率"]["Time Saving"])
    ]
    
    for name, data in key_metrics:
        metrics.append({
            "name": name,
            "value": data["value"],
            "unit": data["unit"],
            "target": data["target"],
            "passed": effect_report_generator._check_target(data["value"], data["target"])
        })
    
    return metrics

def get_recent_files():
    """获取最近生成的文件"""
    files = []
    output_types = [
        ("cards", "卡片文件"),
        ("reports", "报告文件"),
        ("writes", "写入结果")
    ]
    
    for dir_name, type_name in output_types:
        dir_path = outputs_dir / dir_name
        if dir_path.exists():
            for file_path in dir_path.iterdir():
                if file_path.is_file() and not file_path.name.startswith("."):
                    stat = file_path.stat()
                    files.append({
                        "name": file_path.name,
                        "path": f"{dir_name}/{file_path.name}",
                        "type": type_name,
                        "mtime": Path(file_path).stat().st_mtime,
                        "size": int(stat.st_size / 1024)
                    })
    
    # 按修改时间倒序
    files.sort(key=lambda x: x["mtime"], reverse=True)
    # 格式化时间
    from datetime import datetime
    for f in files[:10]:
        f["mtime"] = datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M")
    
    return files[:10]

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard首页"""
    metrics = get_metrics()
    recent_files = get_recent_files()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "recent_files": recent_files
        }
    )

@app.get("/generate-report")
async def generate_report():
    """生成效果报告"""
    result = effect_report_generator.generate_report()
    return {"status": "success", "report_path": result["md_path"]}

def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    """启动Dashboard服务"""
    import uvicorn
    print(f"🚀 Demo Dashboard 启动成功，访问地址: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_dashboard()
