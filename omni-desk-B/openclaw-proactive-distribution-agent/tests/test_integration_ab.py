import pytest
from app.clients.a_client import a_client
from app.config import settings
from app.workflow.workflow_orchestrator import workflow_orchestrator
from app.triggers.trigger_engine import trigger_engine
from app.cards.pre_meeting_card_generator import pre_meeting_card_generator
from app.tasks.action_item_previewer import action_item_previewer
from app.cards.weekly_card_generator import weekly_card_generator
from app.cards.risk_alert_generator import risk_alert_generator

pytestmark = pytest.mark.asyncio

class TestABIntegration:
    """A/B子系统联调测试"""
    
    async def test_a_client_pre_meeting_api(self):
        """测试AClient调用A端会前上下文接口"""
        # 测试mock模式
        meeting_context = await a_client.get_meeting_context(
            project_id=settings.demo_project_id,
            meeting_id="test_meeting_001"
        )
        
        # 验证返回数据结构
        assert "trace_id" in meeting_context
        assert "meeting_title" in meeting_context
        assert "attendees" in meeting_context
        assert "last_meeting_resolutions" in meeting_context
        assert "unfinished_tasks" in meeting_context
        assert "related_materials" in meeting_context
        
        # 验证所有事实项都有evidence_id
        for item in meeting_context["last_meeting_resolutions"]:
            assert "evidence_id" in item
            assert "source_url" in item
        
        for task in meeting_context["unfinished_tasks"]:
            assert "evidence_id" in task
            assert "source_url" in task
    
    async def test_a_client_post_meeting_api(self):
        """测试AClient调用A端会后行动项接口"""
        action_items = await a_client.get_action_items(
            project_id=settings.demo_project_id,
            minutes_id="test_minutes_001"
        )
        
        assert "trace_id" in action_items
        assert "action_items" in action_items
        assert len(action_items["action_items"]) > 0
        
        for item in action_items["action_items"]:
            assert "id" in item
            assert "title" in item
            assert "owner" in item
            assert "deadline" in item
            assert "evidence_id" in item
            assert "source_url" in item
    
    async def test_a_client_weekly_insight_api(self):
        """测试AClient调用A端周报素材接口"""
        weekly_material = await a_client.get_weekly_material(
            project_id=settings.demo_project_id,
            start_date="2026-04-20",
            end_date="2026-04-26"
        )
        
        assert "trace_id" in weekly_material
        assert "weekly_highlights" in weekly_material
        assert "key_milestones" in weekly_material
        assert "risk_points" in weekly_material
        assert "next_week_plan" in weekly_material
    
    async def test_a_client_risk_alert_api(self):
        """测试AClient调用A端风险原子接口"""
        risk_atoms = await a_client.get_risk_atoms(
            project_id=settings.demo_project_id
        )
        
        assert "trace_id" in risk_atoms
        assert "risk_items" in risk_atoms
        assert len(risk_atoms["risk_items"]) >= 0
        
        for risk in risk_atoms["risk_items"]:
            assert "risk_id" in risk
            assert "title" in risk
            assert "level" in risk
            assert "description" in risk
            assert "evidence_id" in risk
            assert "source_url" in risk
    
    async def test_full_pre_meeting_flow(self):
        """测试会前背景卡片完整流程：从触发到生成卡片"""
        # 1. 触发会前场景
        trigger_context = trigger_engine.manual_trigger(
            scenario_type="pre_meeting",
            project_id=settings.demo_project_id,
            dry_run=True,
            meeting_id="test_meeting_001"
        )
        
        # 2. 执行工作流
        result = await workflow_orchestrator.execute(trigger_context)
        
        assert "trace_id" in result
        assert "preview_id" in result
        assert "card_result" in result
        
        # 3. 验证卡片内容
        card_content = result["card_result"]["markdown"]
        assert "meeting_title" in card_content
        assert "meeting_time" in card_content
        assert "attendees" in card_content
        assert "last_meeting_review" in card_content
        assert "unfinished_tasks" in card_content
        assert "preparation_suggestions" in card_content
    
    async def test_full_post_meeting_flow(self):
        """测试会后任务完整流程：从触发到生成任务预览"""
        # 1. 触发会后场景
        trigger_context = trigger_engine.manual_trigger(
            scenario_type="post_meeting",
            project_id=settings.demo_project_id,
            dry_run=True,
            minutes_id="test_minutes_001"
        )
        
        # 2. 执行工作流
        result = await workflow_orchestrator.execute(trigger_context)
        
        assert "trace_id" in result
        assert "preview_id" in result
        assert "action_item_preview" in result
        
        # 3. 验证任务内容
        tasks = result["action_item_preview"]["action_items"]
        assert len(tasks) > 0
        for task in tasks:
            assert "title" in task
            assert "owner" in task
            assert "deadline" in task
            assert "evidence_ref" in task
    
    async def test_full_weekly_insight_flow(self):
        """测试周报洞察完整流程：从触发到生成周报卡片"""
        # 1. 触发周报场景
        trigger_context = trigger_engine.manual_trigger(
            scenario_type="weekly_insight",
            project_id=settings.demo_project_id,
            dry_run=True,
            start_date="2026-04-20",
            end_date="2026-04-26"
        )
        
        # 2. 执行工作流
        result = await workflow_orchestrator.execute(trigger_context)
        
        assert "trace_id" in result
        assert "preview_id" in result
        assert "card_result" in result
        
        # 3. 验证周报内容
        card_content = result["card_result"]["markdown"]
        assert "本周进展" in card_content
        assert "延期任务" in card_content
        assert "风险提醒" in card_content
        assert "下周重点" in card_content
    
    async def test_full_risk_alert_flow(self):
        """测试风险预警完整流程：从触发到生成预警卡片"""
        # 1. 触发风险预警场景
        trigger_context = trigger_engine.manual_trigger(
            scenario_type="risk_alert",
            project_id=settings.demo_project_id,
            dry_run=True
        )
        
        # 2. 执行工作流
        result = await workflow_orchestrator.execute(trigger_context)
        
        assert "trace_id" in result
        assert "preview_id" in result
        assert "alert_result" in result
        
        # 3. 验证预警内容
        card_content = result["alert_result"]["markdown"]
        assert "风险预警" in card_content
        assert "风险分数" in card_content
        assert "风险等级" in card_content
        assert "高频风险项" in card_content
        assert "任务概览" in card_content
