import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from app.config import settings

class AClient:
    def __init__(self):
        self.base_url = settings.a_base_url
        self.mock_mode = settings.a_mock_mode
        self.mock_dir = Path(__file__).parent.parent.parent / "fixtures" / "mock_a_responses"
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0)

    async def get_meeting_context(self, project_id: str, meeting_id: Optional[str] = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取会议上下文包，用于会前背景卡片"""
        if self.mock_mode:
            return self._load_mock_response("pre_meeting_meeting_context.json")
        
        request_data = {
            "project_id": project_id,
            "meeting_id": meeting_id,
            "lookback_days": 14,
            "include_unfinished_tasks": True
        }
        if trace_id:
            request_data["trace_id"] = trace_id
        
        response = await self.client.post(
            "/evidence/v1/meeting/context-package",
            json=request_data
        )
        response.raise_for_status()
        return response.json()["data"]

    async def get_action_items(self, project_id: str, minutes_id: Optional[str] = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取Action Item列表，用于会后任务预览"""
        if self.mock_mode:
            return self._load_mock_response("post_meeting_action_items.json")
        
        request_data = {
            "minutes_id": minutes_id,
            "need_owner_inference": True,
            "need_deadline_inference": True
        }
        if trace_id:
            request_data["trace_id"] = trace_id
        
        response = await self.client.post(
            "/evidence/v1/minutes/action-items",
            json=request_data
        )
        response.raise_for_status()
        return response.json()["data"]

    async def get_weekly_material(self, project_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取周报窗口素材，用于周报洞察"""
        if self.mock_mode:
            return self._load_mock_response("weekly_insight_material.json")
        
        request_data = {
            "project_id": project_id,
            "week_start": start_date,
            "week_end": end_date
        }
        if trace_id:
            request_data["trace_id"] = trace_id
        
        response = await self.client.post(
            "/evidence/v1/weekly/window-summary",
            json=request_data
        )
        response.raise_for_status()
        return response.json()["data"]

    async def get_risk_atoms(self, project_id: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取风险原子和任务状态，用于风险预警"""
        if self.mock_mode:
            return self._load_mock_response("risk_alert_atoms.json")
        
        request_data = {
            "query": "项目当前有哪些风险？",
            "project_id": project_id,
            "source_scope": ["messages", "tasks", "minutes"]
        }
        if trace_id:
            request_data["trace_id"] = trace_id
        
        response = await self.client.post(
            "/evidence/v1/query",
            json=request_data
        )
        response.raise_for_status()
        return response.json()["data"]

    async def get_key_review_data(self, project_id: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取重点事项对账数据 — 近期承诺的任务与当前完成状态"""
        if self.mock_mode:
            return {
                "period": "本周期",
                "verified_evidence": [],
                "review_items": [
                    {"id": "r1", "content": "完成 API 接口开发", "status": "completed", "owner": "张三", "deadline": "2026-04-30", "source_url": "#"},
                    {"id": "r2", "content": "输出测试报告", "status": "in_progress", "owner": "李四", "deadline": "2026-05-05", "source_url": "#"},
                    {"id": "r3", "content": "上线灰度发布", "status": "overdue", "owner": "王五", "deadline": "2026-04-28", "source_url": "#"},
                ],
                "evidence_sources": {},
                "evidence_ids": [],
            }

        request_data = {
            "query": "本周期重点事项和任务完成情况",
            "project_id": project_id,
            "source_scope": ["tasks", "minutes", "messages"],
        }
        if trace_id:
            request_data["trace_id"] = trace_id

        response = await self.client.post(
            "/evidence/v1/query",
            json=request_data
        )
        response.raise_for_status()
        data = response.json()["data"]
        data.setdefault("period", "本周期")
        return data

    async def query_evidence(self, query: str, project_id: str, source_scope: Optional[list] = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """通用证据检索接口"""
        if self.mock_mode:
            # mock模式返回通用证据结构
            return {
                "verified_evidence": [],
                "conflict_report": []
            }
        
        request_data = {
            "query": query,
            "project_id": project_id,
            "source_scope": source_scope or ["docs", "minutes", "messages", "tasks"]
        }
        if trace_id:
            request_data["trace_id"] = trace_id
        
        response = await self.client.post(
            "/evidence/v1/query",
            json=request_data
        )
        response.raise_for_status()
        return response.json()["data"]

    def _load_mock_response(self, filename: str) -> Dict[str, Any]:
        """加载本地mock响应文件"""
        file_path = self.mock_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Mock response file not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

# 全局AClient实例
a_client = AClient()
