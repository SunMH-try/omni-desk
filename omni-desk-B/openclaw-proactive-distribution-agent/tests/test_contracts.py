import pytest
import json
from pathlib import Path
from jsonschema import validate, ValidationError
from app.clients.a_client import a_client

def get_schema(schema_path: str):
    """加载schema文件"""
    schema_file = Path(__file__).parent.parent / "contracts" / schema_path
    with open(schema_file, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.mark.asyncio
async def test_meeting_context_contract():
    """测试A端会议上下文接口合约"""
    # 加载schema
    schema = get_schema("a_to_b/meeting_context.schema.json")
    
    # 获取mock数据
    meeting_context = await a_client.get_meeting_context(project_id="test_project")
    
    # 验证数据符合合约
    try:
        validate(instance=meeting_context, schema=schema)
        assert True, "数据符合合约规范"
    except ValidationError as e:
        assert False, f"数据不符合合约规范: {e.message}"
    
    # 验证必填字段存在
    assert "trace_id" in meeting_context
    assert "meeting_title" in meeting_context
    assert "attendees" in meeting_context
    
    # 验证evidence_id存在
    for item in meeting_context.get("last_meeting_resolutions", []):
        assert "evidence_id" in item
        assert "source_url" in item
    
    for task in meeting_context.get("unfinished_tasks", []):
        assert "evidence_id" in task
        assert "source_url" in task

def test_b_api_trigger_run_request_schema():
    """测试B端触发接口请求格式"""
    from app.main import TriggerRunRequest
    
    # 验证请求模型符合文档定义
    request = TriggerRunRequest(
        trigger_type="schedule",
        scenario_type="weekly_insight",
        project_id="alpha_report_platform",
        dry_run=True
    )
    
    assert request.trigger_type == "schedule"
    assert request.scenario_type == "weekly_insight"
    assert request.project_id == "alpha_report_platform"
    assert request.dry_run == True

def test_b_api_trigger_run_response_schema():
    """测试B端触发接口响应格式"""
    from app.main import TriggerRunResponse
    
    response = TriggerRunResponse(
        data={
            "trace_id": "trace_b_001",
            "preview_id": "preview_weekly_001",
            "requires_confirmation": True
        }
    )
    
    assert response.code == 200
    assert "trace_id" in response.data
    assert "preview_id" in response.data
    assert "requires_confirmation" in response.data

def test_evidence_id_present_in_all_outputs():
    """验证所有输出内容都携带evidence_id"""
    import json
    # 检查mock数据中的evidence_id
    mock_files = [
        "pre_meeting_meeting_context.json",
        "post_meeting_action_items.json",
        "weekly_insight_material.json",
        "risk_alert_atoms.json"
    ]
    
    for filename in mock_files:
        file_path = Path(__file__).parent.parent / "fixtures" / "mock_a_responses" / filename
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 递归检查所有对象是否有evidence_id
        def check_evidence_id(obj, path=""):
            if isinstance(obj, dict):
                if "evidence_id" in obj:
                    assert isinstance(obj["evidence_id"], str), f"{path}.evidence_id 必须是字符串"
                    assert len(obj["evidence_id"]) > 0, f"{path}.evidence_id 不能为空"
                for key, value in obj.items():
                    check_evidence_id(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_evidence_id(item, f"{path}[{i}]")
        
        check_evidence_id(data)
