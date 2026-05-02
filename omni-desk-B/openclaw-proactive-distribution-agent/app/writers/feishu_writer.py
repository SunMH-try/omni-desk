import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings

class FeishuWriter:
    def __init__(self):
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.output_dir = Path(__file__).parent.parent.parent / "outputs" / "writes"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._tenant_access_token = None

    async def write_tasks(
        self,
        task_preview: Dict[str, Any],
        confirmed_items: List[str],
        task_group_id: Optional[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """将确认的任务写入飞书任务"""
        task_group_id = task_group_id or settings.default_task_group_id
        preview_id = task_preview["preview_id"]
        trace_id = task_preview["trace_id"]
        
        # 筛选出确认的任务项
        items_to_create = [
            item for item in task_preview["processed_items"]
            if item["id"] in confirmed_items
        ]

        write_result = {
            "preview_id": preview_id,
            "trace_id": trace_id,
            "dry_run": dry_run,
            "created_tasks": [],
            "bitable_updated": False,
            "write_trace": []
        }

        if dry_run:
            # dry-run模式，模拟创建结果
            for item in items_to_create:
                mock_task_id = f"task_mock_{item['id']}"
                write_result["created_tasks"].append({
                    "task_id": mock_task_id,
                    "title": item["title"],
                    "owner": item["owner"],
                    "deadline": item.get("deadline"),
                    "status": "created_dry_run"
                })
                write_result["write_trace"].append(f"Dry run: 创建任务 {item['title']}，ID: {mock_task_id}")
            
            write_result["bitable_updated"] = True
            write_result["write_trace"].append("Dry run: 多维表格更新成功")
            
            # 保存dry-run结果
            self._save_write_result(preview_id, write_result)
            return write_result

        # 真实写入模式
        try:
            # 1. 获取飞书访问令牌
            await self._get_tenant_access_token()
            
            # 2. 逐个创建任务
            for item in items_to_create:
                task_data = await self._create_feishu_task(item, task_group_id)
                write_result["created_tasks"].append(task_data)
                write_result["write_trace"].append(f"创建任务 {item['title']} 成功，ID: {task_data['task_id']}")
            
            # 3. 同步到多维表格
            if settings.default_bitable_app_token and settings.default_bitable_table_id:
                await self._sync_to_bitable(items_to_create, write_result["created_tasks"])
                write_result["bitable_updated"] = True
                write_result["write_trace"].append("多维表格同步成功")

        except Exception as e:
            write_result["error"] = str(e)
            write_result["write_trace"].append(f"写入失败: {str(e)}")
        
        # 保存写入结果
        self._save_write_result(preview_id, write_result)
        return write_result

    async def _get_tenant_access_token(self) -> str:
        """获取飞书租户访问令牌"""
        if self._tenant_access_token:
            return self._tenant_access_token
        
        if not self.app_id or not self.app_secret:
            raise ValueError("飞书应用配置未完成，请设置FEISHU_APP_ID和FEISHU_APP_SECRET")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"获取访问令牌失败: {data.get('msg')}")
            
            self._tenant_access_token = data["tenant_access_token"]
            return self._tenant_access_token

    async def _create_feishu_task(self, task_item: Dict[str, Any], task_group_id: str) -> Dict[str, Any]:
        """创建单个飞书任务"""
        url = "https://open.feishu.cn/open-apis/task/v2/tasks"
        headers = {
            "Authorization": f"Bearer {self._tenant_access_token}",
            "Content-Type": "application/json"
        }
        
        task_data = {
            "summary": task_item["title"],
            "description": f"来源：{task_item['source_url']}\n置信度：{int(task_item['confidence']*100)}%",
            "due": {
                "time": task_item.get("deadline")
            } if task_item.get("deadline") else None,
            "task_list_id": task_group_id
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json={"task": task_data})
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"创建任务失败: {data.get('msg')}")
            
            return {
                "task_id": data["data"]["task"]["guid"],
                "title": task_item["title"],
                "owner": task_item["owner"],
                "deadline": task_item.get("deadline"),
                "status": "created"
            }

    async def _sync_to_bitable(self, items: List[Dict[str, Any]], created_tasks: List[Dict[str, Any]]):
        """同步任务到多维表格"""
        app_token = settings.default_bitable_app_token
        table_id = settings.default_bitable_table_id
        
        if not app_token or not table_id:
            return
        
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {
            "Authorization": f"Bearer {self._tenant_access_token}",
            "Content-Type": "application/json"
        }
        
        records = []
        for item, task in zip(items, created_tasks):
            records.append({
                "fields": {
                    "任务名称": item["title"],
                    "负责人": item["owner_name"],
                    "截止时间": item.get("deadline"),
                    "优先级": item["priority"],
                    "来源链接": item["source_url"],
                    "飞书任务链接": f"https://applink.feishu.cn/client/task/{task['task_id']}"
                }
            })
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json={"records": records})
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"同步到多维表格失败: {data.get('msg')}")

    def _save_write_result(self, preview_id: str, result: Dict[str, Any]):
        """保存写入结果到文件"""
        result_path = self.output_dir / f"{preview_id}_write_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

# 全局写入器实例
feishu_writer = FeishuWriter()
