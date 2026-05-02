import re
from typing import Dict, Any
from app.triggers.trigger_engine import TriggerContext, ScenarioType
from app.clients.a_client import a_client
from app.cards.pre_meeting_card_generator import pre_meeting_card_generator
from app.tasks.action_item_previewer import action_item_previewer
from app.cards.weekly_card_generator import weekly_card_generator
from app.cards.risk_alert_generator import risk_alert_generator
from app.cards.key_review_generator import key_review_generator


def _extract_action_items_from_text(text: str) -> Dict[str, Any]:
    """从会议纪要纯文本中提取 Action Items，作为 A 端返回空时的兜底。"""
    # 定位 Action Items 段落（允许标题后紧跟换行或冒号，支持多个空行）
    ai_match = re.search(
        r'action\s*items?[^\n]*\n+(.*?)(?:\n{2,}|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )
    section = ai_match.group(1) if ai_match else text

    items = []
    member_map = {}
    # 兼容有无 "- / • / ·" 前缀的格式，例如：
    #   孙鸣皓：完成飞书数据接入，截止 2026-04-30
    #   - 孙鸣皓：完成飞书数据接入，截止 2026-04-30
    pattern = re.compile(
        r'^[-•·]?\s*([^：:\n]{1,20})[：:]\s*(.+?)(?:[，,]\s*截止[日期]?[：:\s]*(\d{4}-\d{2}-\d{2}))?$',
        re.MULTILINE
    )
    for i, m in enumerate(pattern.finditer(section), 1):
        owner_name = m.group(1).strip()
        title = m.group(2).strip()
        deadline = m.group(3)
        if not title or len(title) < 2:
            continue
        member_map[owner_name] = owner_name
        items.append({
            "id": f"task_{i}",
            "title": title,
            "owner": owner_name,
            "deadline": deadline,
            "priority": "high",
            "confidence": 0.9,
            "source_url": "#",
            "missing_fields": [] if deadline else ["deadline"],
        })
    return {"action_items": items, "project_member_map": member_map}

class WorkflowOrchestrator:
    def __init__(self):
        pass

    async def execute(self, trigger_context: TriggerContext) -> Dict[str, Any]:
        """执行流程编排，根据场景类型调用对应的处理逻辑"""
        scenario_type = trigger_context.scenario_type

        # 根据场景类型调用对应的A端接口和处理器
        if scenario_type == ScenarioType.PRE_MEETING:
            return await self._execute_pre_meeting_workflow(trigger_context)
        elif scenario_type == ScenarioType.POST_MEETING:
            return await self._execute_post_meeting_workflow(trigger_context)
        elif scenario_type == ScenarioType.WEEKLY_INSIGHT:
            return await self._execute_weekly_insight_workflow(trigger_context)
        elif scenario_type == ScenarioType.RISK_ALERT:
            return await self._execute_risk_alert_workflow(trigger_context)
        elif scenario_type == ScenarioType.KEY_REVIEW:
            return await self._execute_key_review_workflow(trigger_context)
        else:
            raise ValueError(f"Unsupported scenario type: {scenario_type}")

    async def _execute_pre_meeting_workflow(self, trigger_context: TriggerContext) -> Dict[str, Any]:
        """执行会前背景卡片流程"""
        # 1. 调用A端获取会议上下文
        meeting_context = await a_client.get_meeting_context(
            project_id=trigger_context.project_id,
            meeting_id=trigger_context.metadata.get("meeting_id")
        )

        # 2. 注入上次会议确认的任务及完成情况（闭环）
        try:
            from app.tasks.task_history import load_recent_confirmed_tasks
            from app.tasks.feishu_task_creator import get_feishu_task_status
            from app.config import settings as cfg
            recent_tasks = load_recent_confirmed_tasks(limit=10)
            if recent_tasks and cfg.feishu_app_id and cfg.feishu_app_secret:
                for t in recent_tasks:
                    guid = t.get("task_id", "")
                    t["live_status"] = get_feishu_task_status(cfg.feishu_app_id, cfg.feishu_app_secret, guid)
            meeting_context["previous_confirmed_tasks"] = recent_tasks
        except Exception:
            meeting_context.setdefault("previous_confirmed_tasks", [])

        # 3. 生成会前卡片
        card_result = pre_meeting_card_generator.generate(
            meeting_context=meeting_context,
            trigger_context=trigger_context
        )

        return {
            "trace_id": trigger_context.trace_id,
            "scenario_type": ScenarioType.PRE_MEETING.value,
            "meeting_context": meeting_context,
            "card_result": card_result,
            "preview_id": card_result["preview_id"],
            "requires_confirmation": False
        }

    async def _execute_post_meeting_workflow(self, trigger_context: TriggerContext) -> Dict[str, Any]:
        """执行会后Action Items转任务流程"""
        # 1. 调用A端获取Action Items
        action_items_data = await a_client.get_action_items(
            project_id=trigger_context.project_id,
            minutes_id=trigger_context.metadata.get("minutes_id")
        )

        # 2. A端返回空时，从消息原文兜底解析
        a_items = action_items_data.get("action_items", action_items_data.get("action_item_list", []))
        if not a_items:
            raw_text = trigger_context.metadata.get("raw_text", "")
            if raw_text:
                action_items_data = _extract_action_items_from_text(raw_text)

        # 3. 生成任务预览
        preview_result = action_item_previewer.generate_preview(
            action_items_data=action_items_data,
            trigger_context=trigger_context
        )

        return {
            "trace_id": trigger_context.trace_id,
            "scenario_type": ScenarioType.POST_MEETING.value,
            "action_items_data": action_items_data,
            "preview_result": preview_result,
            "preview_id": preview_result["preview_id"],
            "requires_confirmation": True
        }

    async def _execute_weekly_insight_workflow(self, trigger_context: TriggerContext) -> Dict[str, Any]:
        """执行每周风险洞察流程"""
        # 1. 调用A端获取周报素材
        weekly_material = await a_client.get_weekly_material(
            project_id=trigger_context.project_id,
            start_date=trigger_context.metadata.get("start_date"),
            end_date=trigger_context.metadata.get("end_date")
        )

        # 2. 生成周报卡片
        card_result = weekly_card_generator.generate(
            weekly_material=weekly_material,
            trigger_context=trigger_context
        )

        return {
            "trace_id": trigger_context.trace_id,
            "scenario_type": ScenarioType.WEEKLY_INSIGHT.value,
            "weekly_material": weekly_material,
            "card_result": card_result,
            "preview_id": card_result["preview_id"],
            "requires_confirmation": False
        }

    async def _execute_risk_alert_workflow(self, trigger_context: TriggerContext) -> Dict[str, Any]:
        """执行风险预警流程"""
        # 1. 调用A端获取风险原子
        risk_data = await a_client.get_risk_atoms(
            project_id=trigger_context.project_id
        )

        # 2. 生成风险预警卡片
        alert_result = risk_alert_generator.generate(
            risk_data=risk_data,
            trigger_context=trigger_context
        )

        return {
            "trace_id": trigger_context.trace_id,
            "scenario_type": ScenarioType.RISK_ALERT.value,
            "risk_data": risk_data,
            "alert_result": alert_result,
            "preview_id": alert_result["preview_id"],
            "requires_confirmation": False
        }

    async def _execute_key_review_workflow(self, trigger_context: TriggerContext) -> Dict[str, Any]:
        """执行重点事项对账流程"""
        review_data = await a_client.get_key_review_data(
            project_id=trigger_context.project_id,
        )

        card_result = key_review_generator.generate(
            review_data=review_data,
            trigger_context=trigger_context,
        )

        return {
            "trace_id": trigger_context.trace_id,
            "scenario_type": ScenarioType.KEY_REVIEW.value,
            "review_data": review_data,
            "card_result": card_result,
            "preview_id": card_result["preview_id"],
            "requires_confirmation": False,
        }


# 全局流程编排器实例
workflow_orchestrator = WorkflowOrchestrator()
