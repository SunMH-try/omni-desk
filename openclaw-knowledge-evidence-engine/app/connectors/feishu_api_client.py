"""Feishu Open API real-data client.

Fetches docs / messages / tasks / calendar from the Feishu tenant and
normalises the responses into the same schema as local fixture files so
the rest of the engine needs zero changes.

Configuration (via .env):
    FEISHU_APP_ID          – Feishu app ID
    FEISHU_APP_SECRET      – Feishu app secret
    FEISHU_TENANT_ID       – logical tenant label used inside our schema
    FEISHU_PROJECT_ID      – project label used inside our schema
    FEISHU_CHAT_IDS        – comma-separated group-chat IDs  (oc_xxxx,…)
    FEISHU_DOC_TOKENS      – comma-separated doc tokens       (docx_xxxx,…)
    FEISHU_MINUTES_TOKENS  – comma-separated minutes doc tokens
    FEISHU_TASKLIST_GUIDS  – comma-separated task-list GUIDs  (optional)
    FEISHU_CALENDAR_IDS    – comma-separated calendar IDs     (optional)
    FEISHU_LOOKBACK_DAYS   – message / event look-back window (default 14)
"""
from __future__ import annotations
import json
import os
import time
import datetime
from typing import Optional
import httpx


_BASE = "https://open.feishu.cn/open-apis"
# 飞书文档/群的 Web 访问域名，从环境变量读取（测试企业有独立子域名）
_WEB_BASE = os.environ.get("FEISHU_WEB_BASE_URL", "https://feishu.cn").rstrip("/")


class FeishuAPIClient:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: Optional[str] = None
        self._token_exp: float = 0.0
        self._http = httpx.Client(timeout=30.0)

    # ── Auth ──────────────────────────────────────────────────────────────

    def _token_valid(self) -> bool:
        return self._token is not None and time.time() < self._token_exp - 60

    def _refresh_token(self):
        resp = self._http.post(
            f"{_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Feishu auth failed: {data}")
        self._token = data["tenant_access_token"]
        self._token_exp = time.time() + data.get("expire", 7200)

    def _h(self) -> dict:
        if not self._token_valid():
            self._refresh_token()
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        resp = self._http.get(f"{_BASE}{path}", headers=self._h(), params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Feishu API error {path}: {data}")
        return data.get("data", {})

    # ── Docs ──────────────────────────────────────────────────────────────

    def fetch_doc(
        self,
        doc_token: str,
        project_id: str,
        tenant_id: str,
        source_type: str = "docs",
    ) -> dict:
        """Fetch a Feishu Docx and normalise to fixture schema."""
        meta = self._get(f"/docx/v1/documents/{doc_token}")
        title = meta.get("document", {}).get("title", doc_token)
        url = f"{_WEB_BASE}/docx/{doc_token}"

        raw = self._get(f"/docx/v1/documents/{doc_token}/raw_content")
        full_text: str = raw.get("content", "")

        sections = _split_sections(full_text)

        return {
            "source_id": f"doc_{doc_token}",
            "source_type": source_type,
            "title": title,
            "url": url,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "permission_scope": [],
            "updated_at": meta.get("document", {}).get("revision_id", ""),
            "sections": sections,
            "comments": [],
        }

    # ── Messages ──────────────────────────────────────────────────────────

    def fetch_chat_messages(
        self,
        chat_id: str,
        project_id: str,
        tenant_id: str,
        lookback_days: int = 14,
    ) -> dict:
        """Fetch recent messages from a group chat."""
        now = int(time.time())
        start = now - lookback_days * 86400

        messages = []
        page_token = None
        while True:
            params = {
                "container_id_type": "chat",
                "container_id": chat_id,
                "start_time": str(start),
                "end_time": str(now),
                "page_size": 50,
            }
            if page_token:
                params["page_token"] = page_token

            data = self._get("/im/v1/messages", params=params)
            for item in data.get("items", []):
                msg = _parse_message(item)
                if msg:
                    messages.append(msg)

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        chat_info = self._get(f"/im/v1/chats/{chat_id}")
        chat_name = chat_info.get("name", chat_id)

        return {
            "source_id": f"msg_{chat_id}",
            "source_type": "messages",
            "title": chat_name,
            "url": f"{_WEB_BASE}/client/chat/{chat_id}",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "permission_scope": [],
            "updated_at": datetime.datetime.utcnow().isoformat() + "+08:00",
            "messages": messages,
        }

    # ── Tasks ─────────────────────────────────────────────────────────────

    def fetch_tasks(
        self,
        project_id: str,
        tenant_id: str,
        tasklist_guid: Optional[str] = None,
    ) -> dict:
        """Fetch tasks from a tasklist (or all visible tasks)."""
        tasks_raw = []
        page_token = None

        if tasklist_guid:
            path = f"/task/v2/tasklists/{tasklist_guid}/tasks"
        else:
            path = "/task/v2/tasks"

        while True:
            params = {"page_size": 50}
            if page_token:
                params["page_token"] = page_token
            data = self._get(path, params=params)
            tasks_raw.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        tasks = [_normalise_task(t) for t in tasks_raw]

        return {
            "source_id": f"tasks_{project_id}",
            "source_type": "tasks",
            "title": f"{project_id} 任务列表",
            "url": "",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "permission_scope": [],
            "updated_at": datetime.datetime.utcnow().isoformat() + "+08:00",
            "tasks": tasks,
        }

    # ── Calendar ──────────────────────────────────────────────────────────

    def fetch_calendar_events(
        self,
        calendar_id: str,
        project_id: str,
        tenant_id: str,
        lookback_days: int = 14,
    ) -> dict:
        """Fetch upcoming and recent calendar events."""
        now = int(time.time())
        start = now - lookback_days * 86400
        end = now + 7 * 86400  # include next week

        data = self._get(
            f"/calendar/v4/calendars/{calendar_id}/events",
            params={
                "start_time": str(start),
                "end_time": str(end),
                "page_size": 50,
            },
        )
        events = [_normalise_event(e) for e in data.get("items", [])]

        return {
            "source_id": f"calendar_{calendar_id}",
            "source_type": "calendar",
            "title": f"{project_id} 日历",
            "url": "",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "permission_scope": [],
            "updated_at": datetime.datetime.utcnow().isoformat() + "+08:00",
            "events": events,
        }

    # ── Wiki ──────────────────────────────────────────────────────────────

    def resolve_wiki_token(self, wiki_token: str) -> str:
        """Resolve a wiki page token to its underlying docx obj_token."""
        data = self._get("/wiki/v2/spaces/get_node", params={"token": wiki_token, "obj_type": "wiki"})
        obj_token = data.get("node", {}).get("obj_token", "")
        if not obj_token:
            raise RuntimeError(f"Cannot resolve wiki token {wiki_token}: {data}")
        return obj_token

    # ── Task creation ─────────────────────────────────────────────────────

    def create_task(
        self,
        summary: str,
        due_date: Optional[str] = None,
        description: str = "",
        tasklist_guid: Optional[str] = None,
    ) -> dict:
        """Create a task via Feishu Task API v2. Returns the task dict."""
        body: dict = {"summary": summary}
        if description:
            body["description"] = description
        if due_date:
            try:
                dt = datetime.datetime.strptime(due_date[:10], "%Y-%m-%d")
                body["due"] = {"timestamp": str(int(dt.timestamp())), "is_all_day": True}
            except Exception:
                pass

        resp = self._http.post(f"{_BASE}/task/v2/tasks", headers=self._h(), json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Create task failed: {data}")
        task = data.get("data", {}).get("task", {})
        task_guid = task.get("guid", "")

        if task_guid and tasklist_guid:
            try:
                self._http.post(
                    f"{_BASE}/task/v2/tasklists/{tasklist_guid}/tasks",
                    headers=self._h(),
                    json={"tasks": [{"task_guid": task_guid}]},
                    timeout=15,
                )
            except Exception:
                pass
        return task

    def close(self):
        self._http.close()


# ── Normalisation helpers ──────────────────────────────────────────────────


def _split_sections(text: str) -> list[dict]:
    """Convert plain text into rough section list."""
    sections = []
    current_heading = "正文"
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Detect headings: starts with #, or is a short all-caps-ish line
        if stripped.startswith("# "):
            _flush_section(sections, current_heading, current_lines, level=1)
            current_heading = stripped.lstrip("# ").strip()
            current_lines = []
        elif stripped.startswith("## "):
            _flush_section(sections, current_heading, current_lines, level=2)
            current_heading = stripped.lstrip("# ").strip()
            current_lines = []
        elif stripped.startswith("### "):
            _flush_section(sections, current_heading, current_lines, level=3)
            current_heading = stripped.lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(stripped)

    _flush_section(sections, current_heading, current_lines, level=1)
    return sections


def _flush_section(sections, heading, lines, level):
    content = " ".join(lines).strip()
    if content:
        sections.append({"heading": heading, "level": level, "content": content})


def _parse_message(item: dict) -> Optional[dict]:
    body = item.get("body", {})
    raw_content = body.get("content", "{}")
    try:
        parsed = json.loads(raw_content)
        text = parsed.get("text", "")
    except (json.JSONDecodeError, AttributeError):
        text = raw_content

    if not text:
        return None

    sender_info = item.get("sender", {})
    sender_id = sender_info.get("id", "unknown")
    # create_time is unix milliseconds string
    ts_ms = int(item.get("create_time", "0"))
    ts_str = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc).astimezone(
        datetime.timezone(datetime.timedelta(hours=8))
    ).isoformat()

    return {
        "msg_id": item.get("message_id", ""),
        "sender": sender_id,
        "timestamp": ts_str,
        "text": text,
    }


def _normalise_task(t: dict) -> dict:
    due = t.get("due", {})
    deadline = None
    if due.get("timestamp"):
        ts = int(due["timestamp"])
        deadline = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

    members = t.get("members", [])
    assignee = None
    for m in members:
        if m.get("role") == "assignee":
            assignee = m.get("id")
            break
    if not assignee and members:
        assignee = members[0].get("id")

    status_map = {"to_do": "pending", "in_progress": "in_progress", "done": "completed"}
    status = status_map.get(t.get("status", ""), "pending")

    priority_map = {0: "low", 1: "medium", 2: "high"}
    priority = priority_map.get(t.get("priority", 1), "medium")

    return {
        "task_id": t.get("guid", ""),
        "title": t.get("summary", ""),
        "assignee": assignee,
        "status": status,
        "priority": priority,
        "deadline": deadline,
        "created_at": _ts_to_iso(t.get("created_at")),
        "updated_at": _ts_to_iso(t.get("updated_at")),
        "comments": [],
    }


def _normalise_event(e: dict) -> dict:
    start_ts = e.get("start_time", {}).get("timestamp", "0")
    end_ts = e.get("end_time", {}).get("timestamp", "0")
    return {
        "meeting_id": e.get("event_id", ""),
        "title": e.get("summary", ""),
        "start_time": _ts_to_iso(start_ts),
        "end_time": _ts_to_iso(end_ts),
        "attendees": [],
        "minutes_id": None,
    }


def _ts_to_iso(ts) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone(datetime.timedelta(hours=8)))
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        return str(ts)