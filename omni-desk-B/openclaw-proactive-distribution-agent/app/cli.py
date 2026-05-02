import click
import asyncio
import json
from app.config import settings
from app.triggers.trigger_engine import trigger_engine, ScenarioType
from app.workflow.workflow_orchestrator import workflow_orchestrator

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """OpenClaw Proactive Distribution Agent CLI"""
    pass

@cli.group()
def trigger():
    """触发各类场景流程"""
    pass

@trigger.command(name="pre-meeting")
@click.option("--project-id", default=settings.demo_project_id, help="项目ID")
@click.option("--meeting-id", help="会议ID")
@click.option("--dry-run", is_flag=True, default=True, help="是否为预览模式，不真实写入")
@click.option("--output", type=click.Choice(["text", "json", "markdown"]), default="text", help="输出格式")
def trigger_pre_meeting(project_id: str, meeting_id: str, dry_run: bool, output: str):
    """触发会前背景卡片流程"""
    asyncio.run(_run_trigger(ScenarioType.PRE_MEETING, project_id, dry_run, {"meeting_id": meeting_id}, output))

@trigger.command(name="post-meeting")
@click.option("--project-id", default=settings.demo_project_id, help="项目ID")
@click.option("--minutes-id", help="会议纪要ID")
@click.option("--dry-run", is_flag=True, default=True, help="是否为预览模式，不真实写入")
@click.option("--output", type=click.Choice(["text", "json", "markdown"]), default="text", help="输出格式")
def trigger_post_meeting(project_id: str, minutes_id: str, dry_run: bool, output: str):
    """触发会后Action Items转任务流程"""
    asyncio.run(_run_trigger(ScenarioType.POST_MEETING, project_id, dry_run, {"minutes_id": minutes_id}, output))

@trigger.command(name="weekly-insight")
@click.option("--project-id", default=settings.demo_project_id, help="项目ID")
@click.option("--start-date", help="开始日期 YYYY-MM-DD")
@click.option("--end-date", help="结束日期 YYYY-MM-DD")
@click.option("--dry-run", is_flag=True, default=True, help="是否为预览模式，不真实写入")
@click.option("--output", type=click.Choice(["text", "json", "markdown"]), default="text", help="输出格式")
def trigger_weekly_insight(project_id: str, start_date: str, end_date: str, dry_run: bool, output: str):
    """触发每周风险洞察流程"""
    metadata = {"start_date": start_date, "end_date": end_date}
    asyncio.run(_run_trigger(ScenarioType.WEEKLY_INSIGHT, project_id, dry_run, metadata, output))

@trigger.command(name="risk-alert")
@click.option("--project-id", default=settings.demo_project_id, help="项目ID")
@click.option("--dry-run", is_flag=True, default=True, help="是否为预览模式，不真实写入")
@click.option("--output", type=click.Choice(["text", "json", "markdown"]), default="text", help="输出格式")
def trigger_risk_alert(project_id: str, dry_run: bool, output: str):
    """触发风险预警流程"""
    asyncio.run(_run_trigger(ScenarioType.RISK_ALERT, project_id, dry_run, {}, output))

async def _run_trigger(scenario_type: ScenarioType, project_id: str, dry_run: bool, metadata: dict, output: str):
    """统一触发流程执行"""
    click.echo(f"🚀 触发 {scenario_type.value} 流程，项目ID: {project_id}, dry-run: {dry_run}")
    
    # 1. 创建触发上下文
    trigger_context = trigger_engine.manual_trigger(
        scenario_type=scenario_type,
        project_id=project_id,
        dry_run=dry_run,
        **metadata
    )
    click.echo(f"🔍 Trace ID: {trigger_context.trace_id}")
    
    # 2. 执行流程编排
    try:
        result = await workflow_orchestrator.execute(trigger_context)
        click.echo("✅ 流程执行完成")
        
        # 输出结果
        if output == "json":
            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        elif output == "markdown":
            if "card_result" in result:
                click.echo(result["card_result"]["markdown"])
            elif "preview_result" in result:
                click.echo(result["preview_result"]["markdown"])
        else:
            click.echo(f"📄 预览ID: {result['preview_id']}")
            if "card_result" in result:
                click.echo(f"📌 卡片标题: {result['card_result']['card_title']}")
            elif "preview_result" in result:
                click.echo(f"📋 待办数量: {len(result['preview_result']['processed_items'])}")
                click.echo(f"⚠️  缺失字段数: {result['preview_result']['missing_fields_count']}")
            
            click.echo(f"💾 结果已保存到 outputs/ 目录")
    
    except Exception as e:
        click.echo(f"❌ 流程执行失败: {str(e)}", err=True)

@cli.command()
@click.option("--host", default="0.0.0.0", help="监听地址")
@click.option("--port", default=8080, type=int, help="监听端口")
def dashboard(host: str, port: int):
    """启动Demo Dashboard"""
    from app.dashboard.dashboard_server import run_dashboard
    run_dashboard(host, port)

@cli.command(name="effect-report")
@click.option("--project-name", default=settings.demo_project_id, help="项目名称")
@click.option("--output", type=click.Choice(["text", "json", "markdown"]), default="text", help="输出格式")
def effect_report(project_name: str, output: str):
    """生成效果验证报告"""
    from app.reports.effect_report_generator import effect_report_generator
    
    click.echo(f"📊 生成 {project_name} 效果验证报告...")
    result = effect_report_generator.generate_report(project_name=project_name)
    
    if output == "json":
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    elif output == "markdown":
        click.echo(result["content"])
    else:
        click.echo(f"✅ 报告生成完成")
        click.echo(f"📄 Markdown报告: {result['md_path']}")
        click.echo(f"📊 JSON数据: {result['json_path']}")
        click.echo("")
        click.echo("📈 核心指标:")
        click.echo(result["summary"])

if __name__ == "__main__":
    cli()
