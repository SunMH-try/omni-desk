import pytest
from pathlib import Path
from app.reports.effect_report_generator import effect_report_generator

def test_generate_report_default():
    """测试生成默认效果报告"""
    result = effect_report_generator.generate_report()
    
    # 验证返回结果
    assert "report_id" in result
    assert "md_path" in result
    assert "json_path" in result
    assert "content" in result
    assert "summary" in result
    
    # 验证文件存在
    assert Path(result["md_path"]).exists()
    assert Path(result["json_path"]).exists()
    
    # 验证内容包含必要部分
    assert "效果验证报告" in result["content"]
    assert "核心指标" in result["content"]
    assert "案例分析" in result["content"]
    assert "失败样例与优化方向" in result["content"]
    
    # 验证指标正确
    assert "Citation Accuracy" in result["content"]
    assert "Hallucination Rate" in result["content"]
    assert "Time Saving" in result["content"]
    
    # 验证总结内容
    assert "达标率" in result["summary"]
    assert "准确性指标表现优异" in result["summary"]

def test_generate_report_with_custom_metrics():
    """测试使用自定义指标生成报告"""
    custom_metrics = {
        "准确性": {
            "Citation Accuracy": {"value": 95, "unit": "%", "target": ">=90%"},
            "Hallucination Rate": {"value": 2.1, "unit": "%", "target": "<=5%"}
        },
        "效率": {
            "Time Saving": {"value": 75, "unit": "%", "target": ">=50%"}
        }
    }
    
    result = effect_report_generator.generate_report(
        custom_metrics=custom_metrics,
        project_name="自定义测试项目"
    )
    
    assert "自定义测试项目" in result["content"]
    assert "95%" in result["content"]
    assert "2.1%" in result["content"]
    assert "75%" in result["content"]

def test_check_target():
    """测试指标达标检查函数"""
    # >= 类型
    assert effect_report_generator._check_target(92, ">=90%") == True
    assert effect_report_generator._check_target(88, ">=90%") == False
    
    # <= 类型
    assert effect_report_generator._check_target(3.2, "<=5%") == True
    assert effect_report_generator._check_target(6.1, "<=5%") == False
    
    # 分数类型
    assert effect_report_generator._check_target(4.3, ">=4.0/5") == True
    assert effect_report_generator._check_target(3.8, ">=4.0/5") == False
