import pytest
import json
import asyncio
from pathlib import Path
from app.writers.feishu_writer import feishu_writer

def test_dry_run_write_tasks():
    """测试dry-run模式写入任务"""
    # 模拟任务预览数据
    task_preview = {
        "preview_id": "test_preview_001",
        "trace_id": "trace_test_001",
        "processed_items": [
            {
                "id": "ai_001",
                "title": "测试任务1",
                "owner": "user_rd",
                "owner_name": "张三",
                "deadline": "2026-04-30",
                "priority": "high",
                "confidence": 0.95,
                "source_url": "https://feishu.cn/minutes/xxx1"
            },
            {
                "id": "ai_002",
                "title": "测试任务2",
                "owner": "user_pm",
                "owner_name": "李四",
                "deadline": "2026-05-05",
                "priority": "medium",
                "confidence": 0.88,
                "source_url": "https://feishu.cn/minutes/xxx2"
            }
        ]
    }
    
    # 执行dry-run写入
    result = asyncio.run(feishu_writer.write_tasks(
        task_preview=task_preview,
        confirmed_items=["ai_001", "ai_002"],
        dry_run=True
    ))
    
    # 验证结果
    assert result["dry_run"] == True
    assert result["preview_id"] == "test_preview_001"
    assert len(result["created_tasks"]) == 2
    assert result["bitable_updated"] == True
    
    # 验证任务ID是mock格式
    assert result["created_tasks"][0]["task_id"].startswith("task_mock_")
    assert result["created_tasks"][0]["title"] == "测试任务1"
    assert result["created_tasks"][1]["title"] == "测试任务2"
    
    # 验证写入结果文件存在
    output_dir = Path(__file__).parent.parent / "outputs" / "writes"
    result_file = output_dir / f"{result['preview_id']}_write_result.json"
    assert result_file.exists()
    
    # 验证文件内容
    with open(result_file, "r", encoding="utf-8") as f:
        saved_result = json.load(f)
        assert saved_result["preview_id"] == result["preview_id"]
        assert len(saved_result["created_tasks"]) == 2

def test_dry_run_with_partial_confirmed():
    """测试部分确认的dry-run写入"""
    task_preview = {
            "preview_id": "test_preview_002",
            "trace_id": "trace_test_002",
            "processed_items": [
                {"id": "ai_001", "title": "任务1", "owner": "user_rd", "owner_name": "张三"},
                {"id": "ai_002", "title": "任务2", "owner": "user_pm", "owner_name": "李四"},
                {"id": "ai_003", "title": "任务3", "owner": "user_ops", "owner_name": "王五"}
            ]
        }
    
    result = asyncio.run(feishu_writer.write_tasks(
        task_preview=task_preview,
        confirmed_items=["ai_001", "ai_003"],
        dry_run=True
    ))
    
    assert len(result["created_tasks"]) == 2
    task_titles = [t["title"] for t in result["created_tasks"]]
    assert "任务1" in task_titles
    assert "任务3" in task_titles
    assert "任务2" not in task_titles
