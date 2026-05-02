import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

class TriggerType(str, Enum):
    SCHEDULE = "schedule"
    EVENT = "event"
    THRESHOLD = "threshold"
    MANUAL = "manual"

class ScenarioType(str, Enum):
    PRE_MEETING = "pre_meeting"
    POST_MEETING = "post_meeting"
    WEEKLY_INSIGHT = "weekly_insight"
    RISK_ALERT = "risk_alert"
    KEY_REVIEW = "key_review"

class TriggerContext:
    def __init__(
        self,
        trigger_type: TriggerType,
        scenario_type: ScenarioType,
        project_id: str,
        dry_run: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.trigger_type = trigger_type
        self.scenario_type = scenario_type
        self.project_id = project_id
        self.dry_run = dry_run
        self.metadata = metadata or {}
        self.trace_id = f"trace_b_{uuid.uuid4().hex[:8]}"
        self.triggered_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "trigger_type": self.trigger_type.value,
            "scenario_type": self.scenario_type.value,
            "project_id": self.project_id,
            "dry_run": self.dry_run,
            "triggered_at": self.triggered_at,
            "metadata": self.metadata
        }

class TriggerEngine:
    def __init__(self):
        pass

    def manual_trigger(
        self,
        scenario_type: ScenarioType,
        project_id: str,
        dry_run: bool = True,
        **kwargs
    ) -> TriggerContext:
        """手动触发（CLI/OpenClaw调用）"""
        metadata = kwargs
        return TriggerContext(
            trigger_type=TriggerType.MANUAL,
            scenario_type=scenario_type,
            project_id=project_id,
            dry_run=dry_run,
            metadata=metadata
        )

    def schedule_trigger(
        self,
        scenario_type: ScenarioType,
        project_id: str,
        schedule_config: Dict[str, Any],
        dry_run: bool = True
    ) -> TriggerContext:
        """定时触发"""
        metadata = {"schedule_config": schedule_config}
        return TriggerContext(
            trigger_type=TriggerType.SCHEDULE,
            scenario_type=scenario_type,
            project_id=project_id,
            dry_run=dry_run,
            metadata=metadata
        )

    def event_trigger(
        self,
        scenario_type: ScenarioType,
        project_id: str,
        event_payload: Dict[str, Any],
        dry_run: bool = True
    ) -> TriggerContext:
        """事件触发（如会议纪要生成、日历事件等）"""
        metadata = {"event_payload": event_payload}
        return TriggerContext(
            trigger_type=TriggerType.EVENT,
            scenario_type=scenario_type,
            project_id=project_id,
            dry_run=dry_run,
            metadata=metadata
        )

    def threshold_trigger(
        self,
        scenario_type: ScenarioType,
        project_id: str,
        threshold_state: Dict[str, Any],
        dry_run: bool = True
    ) -> TriggerContext:
        """阈值触发（如风险分数超过阈值、任务延期超过天数等）"""
        metadata = {"threshold_state": threshold_state}
        return TriggerContext(
            trigger_type=TriggerType.THRESHOLD,
            scenario_type=scenario_type,
            project_id=project_id,
            dry_run=dry_run,
            metadata=metadata
        )

# 全局触发器实例
trigger_engine = TriggerEngine()
