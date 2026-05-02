"""Creates real Feishu tasks via Task API v2."""
from __future__ import annotations
import datetime
import json
import logging
import time
from pathlib import Path
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

_FEISHU_API = "https://open.feishu.cn/open-apis"
_token_cache: dict = {"token": "", "expire": 0.0}

# 自动创建的任务清单 GUID 缓存到本地文件，重启后不重复创建
_STATE_FILE = Path(__file__).parent.parent.parent / "outputs" / "state.json"


def _load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"保存 state.json 失败: {e}")


def ensure_tasklist(app_id: str, app_secret: str, name: str = "OpenClaw 项目任务") -> str:
    """返回项目任务清单的 GUID，不存在则自动创建。"""
    state = _load_state()
    cached = state.get("tasklist_guid", "")
    if cached:
        return cached

    headers = {"Authorization": f"Bearer {_get_token(app_id, app_secret)}"}
    # 先查是否已存在同名清单
    r = httpx.get(f"{_FEISHU_API}/task/v2/tasklists", headers=headers, timeout=15)
    for item in r.json().get("data", {}).get("items", []):
        if item.get("name") == name:
            guid = item["guid"]
            state["tasklist_guid"] = guid
            _save_state(state)
            logger.info(f"复用已有任务清单 guid={guid}")
            return guid

    # 不存在则创建
    resp = httpx.post(
        f"{_FEISHU_API}/task/v2/tasklists",
        headers=headers,
        json={"name": name},
        timeout=15,
    )
    d = resp.json()
    if d.get("code") != 0:
        logger.warning(f"创建任务清单失败: {d.get('msg')}")
        return ""
    guid = d.get("data", {}).get("tasklist", {}).get("guid", "")
    if guid:
        state["tasklist_guid"] = guid
        _save_state(state)
        logger.info(f"自动创建任务清单 '{name}' guid={guid}")
    return guid


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


def create_feishu_task(
    app_id: str,
    app_secret: str,
    summary: str,
    due_date: Optional[str] = None,
    description: str = "",
    tasklist_guid: Optional[str] = None,
    assignee_open_id: Optional[str] = None,
) -> dict:
    """Create a task. Returns the task dict or {"error": msg} on failure."""
    headers = {"Authorization": f"Bearer {_get_token(app_id, app_secret)}"}
    body: dict = {"summary": summary}
    if description:
        body["description"] = description
    if due_date:
        try:
            dt = datetime.datetime.strptime(due_date[:10], "%Y-%m-%d")
            body["due"] = {"timestamp": str(int(dt.timestamp()) * 1000), "is_all_day": True}
        except Exception:
            pass
    if assignee_open_id:
        body["members"] = [{"id": assignee_open_id, "type": "user", "role": "assignee"}]

    resp = httpx.post(f"{_FEISHU_API}/task/v2/tasks", headers=headers, json=body, timeout=30)
    data = resp.json()
    if data.get("code") != 0:
        logger.warning(f"Create task failed: {data}")
        return {"error": data.get("msg", "unknown")}

    task = data.get("data", {}).get("task", {})
    task_guid = task.get("guid", "")

    if task_guid and tasklist_guid:
        try:
            httpx.post(
                f"{_FEISHU_API}/task/v2/tasklists/{tasklist_guid}/tasks",
                headers=headers,
                json={"tasks": [{"task_guid": task_guid}]},
                timeout=15,
            )
        except Exception as e:
            logger.warning(f"Add to tasklist failed: {e}")

    logger.info(f"Created Feishu task guid={task_guid} title={summary}")
    return task


_member_cache: dict = {}  # chat_id -> {name: open_id}


def _fetch_chat_members(app_id: str, app_secret: str, chat_id: str) -> dict:
    """拉取群成员列表，返回 {name: open_id} 字典。"""
    headers = {"Authorization": f"Bearer {_get_token(app_id, app_secret)}"}
    members: dict = {}
    page_token = ""
    while True:
        params: dict = {"member_id_type": "open_id", "page_size": 100}
        if page_token:
            params["page_token"] = page_token
        resp = httpx.get(
            f"{_FEISHU_API}/im/v1/chats/{chat_id}/members",
            headers=headers,
            params=params,
            timeout=15,
        )
        d = resp.json()
        if d.get("code") != 0:
            logger.warning(f"拉取群成员失败: {d.get('msg')}")
            break
        for m in d.get("data", {}).get("items", []):
            name = m.get("name", "")
            open_id = m.get("member_id", "")
            if name and open_id:
                members[name] = open_id
        if not d.get("data", {}).get("has_more", False):
            break
        page_token = d.get("data", {}).get("page_token", "")
    logger.info(f"群 {chat_id} 成员缓存更新，共 {len(members)} 人")
    return members


def lookup_open_id_by_name(app_id: str, app_secret: str, name: str) -> Optional[str]:
    """通过姓名查 open_id，从群成员缓存里找。"""
    if not name:
        return None
    try:
        from app.config import settings as _cfg
        chat_id = _cfg.feishu_target_chat_id or ""
        if not chat_id:
            logger.warning("未配置 FEISHU_TARGET_CHAT_ID，无法查群成员")
            return None
        # 缓存未命中时重新拉取
        if chat_id not in _member_cache:
            _member_cache[chat_id] = _fetch_chat_members(app_id, app_secret, chat_id)
        members = _member_cache[chat_id]
        open_id = members.get(name)
        if not open_id:
            # 名字可能是部分匹配，重新拉一次
            _member_cache[chat_id] = _fetch_chat_members(app_id, app_secret, chat_id)
            open_id = _member_cache[chat_id].get(name)
        return open_id
    except Exception as e:
        logger.warning(f"lookup_open_id_by_name failed for '{name}': {e}")
        return None


def send_task_dm(
    app_id: str,
    app_secret: str,
    open_id: str,
    task_title: str,
    task_guid: str = "",
    due_date: str = "",
) -> bool:
    """Send a DM to the task assignee notifying them of the new task."""
    if not open_id:
        return False
    try:
        headers = {"Authorization": f"Bearer {_get_token(app_id, app_secret)}"}
        lines = [
            "你好！你有一个新任务等待处理：",
            "",
            f"📌 {task_title}",
        ]
        if due_date:
            lines.append(f"📅 截止日期：{due_date}")
        if task_guid and not task_guid.startswith("mock_"):
            lines.append(f"🔗 查看任务：https://applink.feishu.cn/client/todo/detail?guid={task_guid}")
        lines.append("")
        lines.append("此消息由 OpenClaw MeetingOps Agent 自动发送。")
        text = "\n".join(lines)

        resp = httpx.post(
            f"{_FEISHU_API}/im/v1/messages?receive_id_type=open_id",
            headers=headers,
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("code") == 0:
            logger.info(f"DM sent to open_id={open_id} for task '{task_title}'")
            return True
        logger.warning(f"DM failed to {open_id}: code={data.get('code')} {data.get('msg')}")
        return False
    except Exception as e:
        logger.warning(f"send_task_dm failed: {e}")
        return False


def get_feishu_task_status(app_id: str, app_secret: str, task_guid: str) -> str:
    """Query a task's completion status. Returns 'completed', 'in_progress', or 'unknown'."""
    if not task_guid:
        return "unknown"
    if task_guid.startswith("mock_"):
        # Demo模式：用 task_guid 哈希确定性地模拟完成状态（约2/3完成，1/3进行中）
        import hashlib
        h = int(hashlib.md5(task_guid.encode()).hexdigest(), 16)
        return ["completed", "completed", "in_progress"][h % 3]
    try:
        headers = {"Authorization": f"Bearer {_get_token(app_id, app_secret)}"}
        resp = httpx.get(
            f"{_FEISHU_API}/task/v2/tasks/{task_guid}",
            headers=headers,
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            return "unknown"
        task = data.get("data", {}).get("task", {})
        completed_at = task.get("completed_at", "")
        if completed_at and completed_at != "0":
            return "completed"
        return "in_progress"
    except Exception as e:
        logger.warning(f"Query task status failed guid={task_guid}: {e}")
        return "unknown"
