"""A01 — Feishu data adapter.

Routes between local fixtures (FEISHU_MODE=fixture, default) and the
real Feishu Open API (FEISHU_MODE=real).  The rest of the engine only
calls load_source() / load_manifest() and sees the same schema either way.
"""
from __future__ import annotations
import json
import re
import yaml
import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional
from app.config import (
    FIXTURES_DIR,
    FEISHU_MODE,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_TENANT_ID,
    FEISHU_PROJECT_ID,
    FEISHU_CHAT_IDS,
    FEISHU_DOC_TOKENS,
    FEISHU_MINUTES_TOKENS,
    FEISHU_TASKLIST_GUIDS,
    FEISHU_CALENDAR_IDS,
    FEISHU_LOOKBACK_DAYS,
)


# 识别飞书文档/Wiki链接的正则
_FEISHU_URL_RE = re.compile(
    r'https?://[a-zA-Z0-9\-]+\.feishu\.cn/(docx|wiki|docs)/([A-Za-z0-9]+)'
)


_FIXTURE_MAP = {
    "docs":     "docs",
    "minutes":  "minutes",
    "messages": "messages",
    "tasks":    "tasks",
    "calendar": "calendar",
    "bitable":  "bitable",
}


# ── Fixture helpers ────────────────────────────────────────────────────────


def _load_all_fixtures(source_type: str) -> list[dict]:
    folder = FIXTURES_DIR / _FIXTURE_MAP[source_type]
    if not folder.exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in folder.glob("*.json")]


# ── Real-API helpers ───────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_real_client():
    from app.connectors.feishu_api_client import FeishuAPIClient
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        raise RuntimeError(
            "FEISHU_MODE=real but FEISHU_APP_ID / FEISHU_APP_SECRET are not set in .env"
        )
    return FeishuAPIClient(FEISHU_APP_ID, FEISHU_APP_SECRET)


def _load_real_sources(source_type: str) -> list[dict]:
    """Fetch live data from Feishu and return normalised fixture-schema dicts."""
    client = _get_real_client()
    tenant_id = FEISHU_TENANT_ID
    project_id = FEISHU_PROJECT_ID
    results = []

    if source_type == "docs":
        for token in FEISHU_DOC_TOKENS:
            try:
                results.append(client.fetch_doc(token, project_id, tenant_id, source_type="docs"))
            except Exception as exc:
                print(f"[feishu_adapter] WARNING: failed to fetch doc {token}: {exc}")

    elif source_type == "minutes":
        for token in FEISHU_MINUTES_TOKENS:
            try:
                results.append(client.fetch_doc(token, project_id, tenant_id, source_type="minutes"))
            except Exception as exc:
                print(f"[feishu_adapter] WARNING: failed to fetch minutes doc {token}: {exc}")

    elif source_type == "messages":
        for chat_id in FEISHU_CHAT_IDS:
            try:
                msg_source = client.fetch_chat_messages(chat_id, project_id, tenant_id, FEISHU_LOOKBACK_DAYS)
                results.append(msg_source)
                # 自动识别消息中分享的飞书文档链接并抓取
                _fetch_linked_docs(client, msg_source, project_id, tenant_id, results)
            except Exception as exc:
                print(f"[feishu_adapter] WARNING: failed to fetch chat {chat_id}: {exc}")

    elif source_type == "tasks":
        if FEISHU_TASKLIST_GUIDS:
            for guid in FEISHU_TASKLIST_GUIDS:
                try:
                    results.append(client.fetch_tasks(project_id, tenant_id, tasklist_guid=guid))
                except Exception as exc:
                    print(f"[feishu_adapter] WARNING: failed to fetch tasklist {guid}: {exc}")
        else:
            try:
                results.append(client.fetch_tasks(project_id, tenant_id))
            except Exception as exc:
                print(f"[feishu_adapter] WARNING: failed to fetch tasks: {exc}")

    elif source_type == "calendar":
        for cal_id in FEISHU_CALENDAR_IDS:
            try:
                results.append(
                    client.fetch_calendar_events(cal_id, project_id, tenant_id, FEISHU_LOOKBACK_DAYS)
                )
            except Exception as exc:
                print(f"[feishu_adapter] WARNING: failed to fetch calendar {cal_id}: {exc}")

    return results


def _fetch_linked_docs(client, msg_source: dict, project_id: str, tenant_id: str, results: list) -> None:
    """扫描消息中的飞书文档/Wiki链接，自动抓取文档内容追加到 results。"""
    seen_tokens = {s.get("source_id", "") for s in results}
    for msg in msg_source.get("messages", []):
        text = msg.get("text", "")
        for match in _FEISHU_URL_RE.finditer(text):
            link_type, token = match.group(1), match.group(2)
            try:
                if link_type == "wiki":
                    # wiki token 需要先解析成 docx token
                    docx_token = client.resolve_wiki_token(token)
                else:
                    docx_token = token
                source_id = f"doc_{docx_token}"
                if source_id in seen_tokens:
                    continue
                seen_tokens.add(source_id)
                doc = client.fetch_doc(docx_token, project_id, tenant_id, source_type="docs")
                results.append(doc)
                print(f"[feishu_adapter] 从群消息链接自动抓取文档: {docx_token}")
            except Exception as exc:
                print(f"[feishu_adapter] WARNING: failed to fetch linked doc {token}: {exc}")


# ── Public API ─────────────────────────────────────────────────────────────


def load_source(
    source_type: str,
    source_id: Optional[str] = None,
    tenant_id: str = "demo_tenant",
    project_id: Optional[str] = None,
    mode: str = "demo",
) -> list[dict]:
    """Load raw source objects from fixtures or real Feishu API.

    Returns list of source dicts matching the given filters.
    """
    if FEISHU_MODE == "real":
        all_sources = _load_real_sources(source_type)
        # In real mode the tenant_id comes from config, not the caller arg —
        # don't filter by the demo default so callers still get results.
        filtered = []
        for s in all_sources:
            if source_id and s.get("source_id") != source_id:
                continue
            if project_id and s.get("project_id") != project_id:
                continue
            filtered.append(s)
    else:
        all_sources = _load_all_fixtures(source_type)
        filtered = []
        for s in all_sources:
            if s.get("tenant_id") != tenant_id:
                continue
            if source_id and s.get("source_id") != source_id:
                continue
            if project_id and s.get("project_id") != project_id:
                continue
            filtered.append(s)

    _write_trace(source_type, source_id, tenant_id, project_id, len(filtered))
    return filtered


def load_manifest(tenant_id: str = "demo_tenant", project_id: Optional[str] = None) -> list[dict]:
    """Return lightweight source manifest (no content) for all types."""
    manifest = []
    if FEISHU_MODE == "real":
        for stype in _FIXTURE_MAP:
            for s in _load_real_sources(stype):
                if project_id and s.get("project_id") != project_id:
                    continue
                manifest.append({
                    "source_id": s["source_id"],
                    "source_type": s["source_type"],
                    "title": s.get("title", ""),
                    "url": s.get("url", ""),
                    "tenant_id": s.get("tenant_id", ""),
                    "project_id": s.get("project_id", ""),
                    "permission_scope": s.get("permission_scope", []),
                    "updated_at": s.get("updated_at", ""),
                })
    else:
        for stype in _FIXTURE_MAP:
            for s in _load_all_fixtures(stype):
                if s.get("tenant_id") != tenant_id:
                    continue
                if project_id and s.get("project_id") != project_id:
                    continue
                manifest.append({
                    "source_id": s["source_id"],
                    "source_type": s["source_type"],
                    "title": s.get("title", ""),
                    "url": s.get("url", ""),
                    "tenant_id": s.get("tenant_id", ""),
                    "project_id": s.get("project_id", ""),
                    "permission_scope": s.get("permission_scope", []),
                    "updated_at": s.get("updated_at", ""),
                })
    return manifest


# ── Trace writer ───────────────────────────────────────────────────────────


def _write_trace(source_type, source_id, tenant_id, project_id, count):
    from app.config import OUTPUTS_DIR
    trace = {
        "source_type": source_type,
        "source_id": source_id,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "source_count": count,
        "mode": FEISHU_MODE,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    out_dir = OUTPUTS_DIR / "events"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    (out_dir / f"read_trace_{source_type}_{ts}.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8"
    )