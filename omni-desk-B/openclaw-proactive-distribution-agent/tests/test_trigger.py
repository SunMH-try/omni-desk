import pytest
from app.triggers.trigger_engine import trigger_engine, TriggerType, ScenarioType

def test_manual_trigger():
    """测试手动触发"""
    trigger_context = trigger_engine.manual_trigger(
        scenario_type=ScenarioType.PRE_MEETING,
        project_id="test_project",
        dry_run=True
    )
    
    assert trigger_context.trigger_type == TriggerType.MANUAL
    assert trigger_context.scenario_type == ScenarioType.PRE_MEETING
    assert trigger_context.project_id == "test_project"
    assert trigger_context.dry_run == True
    assert trigger_context.trace_id.startswith("trace_b_")
    assert len(trigger_context.trace_id) > 0

def test_schedule_trigger():
    """测试定时触发"""
    schedule_config = {"cron": "0 17 * * 5"}
    trigger_context = trigger_engine.schedule_trigger(
        scenario_type=ScenarioType.WEEKLY_INSIGHT,
        project_id="test_project",
        schedule_config=schedule_config,
        dry_run=False
    )
    
    assert trigger_context.trigger_type == TriggerType.SCHEDULE
    assert trigger_context.scenario_type == ScenarioType.WEEKLY_INSIGHT
    assert trigger_context.metadata["schedule_config"] == schedule_config

def test_event_trigger():
    """测试事件触发"""
    event_payload = {"event_type": "minutes_created", "minutes_id": "min_001"}
    trigger_context = trigger_engine.event_trigger(
        scenario_type=ScenarioType.POST_MEETING,
        project_id="test_project",
        event_payload=event_payload
    )
    
    assert trigger_context.trigger_type == TriggerType.EVENT
    assert trigger_context.scenario_type == ScenarioType.POST_MEETING
    assert trigger_context.metadata["event_payload"] == event_payload

def test_threshold_trigger():
    """测试阈值触发"""
    threshold_state = {"risk_score": 85, "threshold": 80}
    trigger_context = trigger_engine.threshold_trigger(
        scenario_type=ScenarioType.RISK_ALERT,
        project_id="test_project",
        threshold_state=threshold_state
    )
    
    assert trigger_context.trigger_type == TriggerType.THRESHOLD
    assert trigger_context.scenario_type == ScenarioType.RISK_ALERT
    assert trigger_context.metadata["threshold_state"] == threshold_state

def test_trigger_context_to_dict():
    """测试触发上下文转字典"""
    trigger_context = trigger_engine.manual_trigger(
        scenario_type=ScenarioType.PRE_MEETING,
        project_id="test_project",
        dry_run=True,
        meeting_id="meet_001"
    )
    
    context_dict = trigger_context.to_dict()
    assert context_dict["trace_id"] == trigger_context.trace_id
    assert context_dict["scenario_type"] == "pre_meeting"
    assert context_dict["trigger_type"] == "manual"
    assert context_dict["metadata"]["meeting_id"] == "meet_001"
