"""将确认的 Action Items 同步到飞书多维表格 (Bitable)。

多维表格字段要求（可在飞书 Bitable 里手动建，或用 API 自动建）：
    任务标题   (text)
    负责人     (text)
    截止日期   (date)
    状态       (select: 待处理 / 进行中 / 已完成)
    来源会议   (text)
    来源链接   (url)
    任务ID     (text)     ← 飞书任务 GUID，用于状态回查
    创建时间   (created_time)

配置（B 端 .env）：
    FEISHU_BITABLE_APP_TOKEN=<多维表格的 app_token>
    FEISHU_BITABLE_TABLE_ID=<表格 ID>
"""
from __future__ import annotations
import datetime
import logging
import time
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
_FEISHU_API = "https://open.feishu.cn/open-apis"
_token_cache: dict = {"token": "", "expire": 0.0}


def _get_token(app_id: str, app_secret: str) -> str:
    if _token_cache["token"] and time.time() < _token_cache["expire"] - 60:
        return _token_cache["token"]
    resp = httpx.post(
        f"{_FEISHU_API}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=15,
    )
    d = resp.json()
    _token_cache["token"] = d["tenant_access_token"]
    _token_cache["expire"] = time.time() + d.get("expire", 7200)
    return _token_cache["token"]


def sync_tasks_to_bitable(
    app_id: str,
    app_secret: str,
    bitable_app_token: str,
    table_id: str,
    tasks: list,
    meeting_source: str = "",
) -> list:
    """把任务列表写入 Bitable，返回每条记录的 record_id 列表。"""
    if not (app_id and app_secret and bitable_app_token and table_id):
        logger.warning("[bitable] 配置不完整，跳过同步")
        return []

    headers = {"Authorization": f"Bearer {_get_token(app_id, app_secret)}"}
    record_ids = []

    for task in tasks:
        due_date = task.get("deadline") or task.get("due_date")
        due_ts = None
        if due_date:
            try:
                dt = datetime.datetime.strptime(due_date[:10], "%Y-%m-%d")
                due_ts = int(dt.timestamp()) * 1000  # Bitable 用毫秒
            except Exception:
                pass

        fields: dict = {
            "任务标题": task.get("title", ""),
            "负责人": task.get("owner_name") or task.get("owner") or "待分配",
            "状态": "待处理",
            "来源会议": meeting_source,
            "来源链接": task.get("source_url", ""),
            "任务ID": task.get("task_id", ""),
        }
        if due_ts:
            fields["截止日期"] = due_ts

        try:
            resp = httpx.post(
                f"{_FEISHU_API}/bitable/v1/apps/{bitable_app_token}/tables/{table_id}/records",
                headers=headers,
                json={"fields": fields},
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0:
                record_id = data.get("data", {}).get("record", {}).get("record_id", "")
                record_ids.append(record_id)
                logger.info(f"[bitable] 同步任务: {task.get('title')} → record_id={record_id}")
            else:
                logger.warning(f"[bitable] 同步失败: {data}")
        except Exception as e:
            logger.error(f"[bitable] 同步异常: {e}")

    return record_ids


def update_task_status_in_bitable(
    app_id: str,
    app_secret: str,
    bitable_app_token: str,
    table_id: str,
    record_id: str,
    status: str,
) -> bool:
    """更新 Bitable 里某条任务的状态。"""
    if not (app_id and app_secret and bitable_app_token and table_id and record_id):
        return False
    headers = {"Authorization": f"Bearer {_get_token(app_id, app_secret)}"}
    try:
        resp = httpx.put(
            f"{_FEISHU_API}/bitable/v1/apps/{bitable_app_token}/tables/{table_id}/records/{record_id}",
            headers=headers,
            json={"fields": {"状态": status}},
            timeout=15,
        )
        return resp.json().get("code") == 0
    except Exception as e:
        logger.error(f"[bitable] 状态更新失败: {e}")
        return False
