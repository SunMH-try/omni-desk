from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, AsyncGenerator
import asyncio
import json
import logging
from pathlib import Path
from app.config import settings
from app.triggers.trigger_engine import trigger_engine, ScenarioType, TriggerType
from app.workflow.workflow_orchestrator import workflow_orchestrator
from app.tasks.feishu_task_creator import create_feishu_task, get_feishu_task_status, lookup_open_id_by_name, send_task_dm, ensure_tasklist
from app.tasks.feishu_bitable_sync import sync_tasks_to_bitable
from app.tasks.task_history import append_confirmed_tasks, load_recent_confirmed_tasks

logger = logging.getLogger(__name__)

# 预览结果缓存
preview_cache: Dict[str, Dict[str, Any]] = {}


def get_preview_result(preview_id: str) -> Dict[str, Any]:
    """从缓存或文件获取预览结果"""
    if preview_id in preview_cache:
        return preview_cache[preview_id]
    
    # 尝试从文件读取
    output_dir = Path(__file__).parent.parent / "outputs" / "cards"
    for ext in [".json", ".md"]:
        file_path = output_dir / f"{preview_id}{ext}"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                if ext == ".json":
                    return json.load(f)
                else:
                    return {"markdown": f.read()}
    
    raise HTTPException(status_code=404, detail=f"Preview {preview_id} not found")

app = FastAPI(
    title="OpenClaw Proactive Distribution Agent API",
    description="子系统B：主动触发、分发与Demo Agent API接口",
    version="0.1.0",
    debug=settings.debug,
)

# ============== API 请求响应模型 ==============
# B-API-01 主动触发执行接口
class TriggerRunRequest(BaseModel):
    trigger_type: str = Field(description="触发类型: schedule/event/threshold/manual")
    scenario_type: str = Field(description="场景类型: pre_meeting/post_meeting/weekly_insight/risk_alert")
    project_id: str = Field(description="项目ID")
    dry_run: Optional[bool] = Field(default=True, description="是否为预览模式")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="额外元数据")

class TriggerRunResponse(BaseModel):
    code: int = 200
    data: Dict[str, Any]

# B-API-02 卡片预览接口
class CardPreviewRequest(BaseModel):
    scenario_type: str = Field(description="场景类型")
    meeting_context_id: Optional[str] = Field(None, description="会议上下文ID")
    evidence_ids: Optional[List[str]] = Field(default=[], description="证据ID列表")
    target_chat_id: Optional[str] = Field(None, description="目标聊天ID")

class CardPreviewResponse(BaseModel):
    code: int = 200
    data: Dict[str, Any]

# B-API-03 任务创建确认接口
class TaskConfirmCreateRequest(BaseModel):
    preview_id: str = Field(description="预览ID")
    confirmed_items: List[str] = Field(description="确认的任务项ID列表")
    target_task_group: str = Field(description="目标任务组")

class TaskConfirmCreateResponse(BaseModel):
    code: int = 200
    data: Dict[str, Any]

# B-API-04 反馈事件回传接口
class FeedbackEventRequest(BaseModel):
    card_id: str = Field(description="卡片ID")
    event_type: str = Field(description="事件类型: click_evidence/confirm_task/ignore_card/rate")
    user_id: str = Field(description="用户ID")
    evidence_id: Optional[str] = Field(None, description="证据ID")
    task_id: Optional[str] = Field(None, description="任务ID")
    rating: Optional[int] = Field(None, description="评分")

class FeedbackEventResponse(BaseModel):
    code: int = 200
    data: Dict[str, Any]

# ============== API 接口实现 ==============
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "proactive-distribution-agent", "mock_mode": settings.a_mock_mode}

# B-API-01 主动触发执行接口
@app.post("/agent/v1/triggers/run", response_model=TriggerRunResponse)
async def trigger_run(request: TriggerRunRequest):
    # 创建触发上下文
    trigger_context = trigger_engine.manual_trigger(
        scenario_type=ScenarioType(request.scenario_type),
        project_id=request.project_id,
        dry_run=request.dry_run,
        **request.metadata
    )
    
    # 执行流程
    result = await workflow_orchestrator.execute(trigger_context)
    # 存入预览缓存
    if result.get("preview_id"):
        preview_cache[result["preview_id"]] = result
    return TriggerRunResponse(
        data={
            "trace_id": result["trace_id"],
            "preview_id": result["preview_id"],
            "requires_confirmation": result["requires_confirmation"]
        }
    )

# B-API-02 卡片预览接口
@app.post("/agent/v1/cards/preview", response_model=CardPreviewResponse)
async def card_preview(request: CardPreviewRequest):
    # 简化实现，直接触发对应场景
    trigger_context = trigger_engine.manual_trigger(
        scenario_type=ScenarioType(request.scenario_type),
        project_id=settings.demo_project_id,
        dry_run=True
    )
    
    result = await workflow_orchestrator.execute(trigger_context)
    
    return CardPreviewResponse(
        data={
            "preview_id": result["preview_id"],
            "card_title": result.get("card_result", {}).get("card_title", "卡片预览"),
            "dry_run": True
        }
    )

# B-API-03 任务创建确认接口
@app.post("/agent/v1/tasks/confirm-create", response_model=TaskConfirmCreateResponse)
async def task_confirm_create(request: TaskConfirmCreateRequest):
    app_id = settings.feishu_app_id
    app_secret = settings.feishu_app_secret
    # .env 没配 GUID 时自动创建「OpenClaw 项目任务」清单并缓存
    tasklist_guid = settings.feishu_tasklist_guid
    if not tasklist_guid and app_id and app_secret:
        tasklist_guid = ensure_tasklist(app_id, app_secret)

    # 从预览缓存中获取任务详情
    try:
        preview_data = get_preview_result(request.preview_id)
    except HTTPException:
        preview_data = {}

    preview_result = preview_data.get("preview_result", {})
    processed_items = preview_result.get("processed_items", [])

    # 缓存丢失时（服务重启）从磁盘 _items.json 兜底加载
    if not processed_items:
        items_path = Path(__file__).parent.parent / "outputs" / "cards" / f"{request.preview_id}_items.json"
        if items_path.exists():
            with open(items_path, encoding="utf-8") as f:
                processed_items = json.load(f)

    item_map = {item["id"]: item for item in processed_items}

    created_tasks = []
    for item_id in request.confirmed_items:
        item = item_map.get(item_id)
        if not item:
            continue

        summary = item.get("title", item_id)
        due_date = item.get("deadline")
        owner_name = item.get("owner_name", "")
        source_url = item.get("source_url", "")
        description = f"负责人：{owner_name}\n来源：{source_url}".strip(" \n：")

        if app_id and app_secret:
            assignee_open_id = lookup_open_id_by_name(app_id, app_secret, owner_name) if owner_name else None
            task = create_feishu_task(
                app_id=app_id,
                app_secret=app_secret,
                summary=summary,
                due_date=due_date,
                description=description,
                tasklist_guid=tasklist_guid or None,
                assignee_open_id=assignee_open_id,
            )
            if "error" in task:
                logger.error(f"飞书任务创建失败: {task['error']} | title={summary}")
                raise HTTPException(
                    status_code=502,
                    detail=f"飞书任务创建失败：{task['error']}（请确认已开通 task:task:write 权限）"
                )
            task_id = task.get("guid", "")
            if not task_id:
                logger.error(f"飞书任务创建成功但未返回 guid: {task}")
                continue
        else:
            task_id = f"mock_{item_id}"

        created_tasks.append({
            "task_id": task_id,
            "title": summary,
            "owner": owner_name,
            "due_date": due_date or "",
            "source_url": source_url,
        })

    # 追加到确认任务历史（闭环）
    append_confirmed_tasks(created_tasks)

    # 给每个负责人发飞书私信通知
    notified_count = 0
    if app_id and app_secret:
        for t in created_tasks:
            name = t.get("owner", "")
            if not name:
                continue
            open_id = lookup_open_id_by_name(app_id, app_secret, name)
            if open_id:
                ok = send_task_dm(
                    app_id=app_id,
                    app_secret=app_secret,
                    open_id=open_id,
                    task_title=t["title"],
                    task_guid=t["task_id"],
                    due_date=t.get("due_date", ""),
                )
                if ok:
                    notified_count += 1

    # 同步到 Bitable
    bitable_record_ids = []
    bitable_app_token = settings.feishu_bitable_app_token
    bitable_table_id = settings.feishu_bitable_table_id
    if app_id and app_secret and bitable_app_token and bitable_table_id and created_tasks:
        bitable_tasks = [
            {
                "title": t["title"],
                "owner_name": t["owner"],
                "task_id": t["task_id"],
                "source_url": t.get("source_url", ""),
            }
            for t in created_tasks
        ]
        bitable_record_ids = sync_tasks_to_bitable(
            app_id=app_id,
            app_secret=app_secret,
            bitable_app_token=bitable_app_token,
            table_id=bitable_table_id,
            tasks=bitable_tasks,
            meeting_source=preview_result.get("trace_id", request.preview_id),
        )

    return TaskConfirmCreateResponse(
        data={
            "created_tasks": created_tasks,
            "bitable_updated": len(bitable_record_ids) > 0,
            "bitable_record_ids": bitable_record_ids,
            "notified_count": notified_count,
        }
    )

# 反馈存储
_feedback_log: list = []
_feedback_log_path = Path(__file__).parent.parent / "outputs" / "feedback_log.jsonl"
_feedback_log_path.parent.mkdir(parents=True, exist_ok=True)

# B-API-04 反馈事件回传接口
@app.post("/agent/v1/feedback/events", response_model=FeedbackEventResponse)
async def feedback_event(request: FeedbackEventRequest):
    import uuid
    from datetime import datetime
    feedback_id = f"fb_{uuid.uuid4().hex[:8]}"

    entry = {
        "feedback_event_id": feedback_id,
        "card_id": request.card_id,
        "event_type": request.event_type,
        "user_id": request.user_id,
        "evidence_id": request.evidence_id,
        "task_id": request.task_id,
        "rating": request.rating,
        "timestamp": datetime.now().isoformat(),
    }
    _feedback_log.append(entry)
    try:
        with open(_feedback_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[feedback] 写入日志失败: {e}")

    logger.info(f"[feedback] {request.event_type} card={request.card_id} user={request.user_id}")

    return FeedbackEventResponse(
        data={
            "feedback_event_id": feedback_id,
            "accepted": True
        }
    )

@app.get("/agent/v1/tasks/recent")
async def get_recent_tasks(limit: int = 20, enrich_status: bool = False):
    """返回最近确认的任务列表，可选实时查询飞书任务完成状态"""
    tasks = load_recent_confirmed_tasks(limit=limit)
    if enrich_status and tasks:
        app_id = settings.feishu_app_id
        app_secret = settings.feishu_app_secret
        if app_id and app_secret:
            for t in tasks:
                guid = t.get("task_id", "")
                t["live_status"] = get_feishu_task_status(app_id, app_secret, guid)
    return {"code": 200, "data": {"tasks": tasks, "total": len(tasks)}}


@app.get("/agent/v1/feedback/stats")
async def feedback_stats():
    """反馈统计 — 按事件类型汇总"""
    from collections import Counter
    counts = Counter(e["event_type"] for e in _feedback_log)
    ratings = [e["rating"] for e in _feedback_log if e.get("rating") is not None]
    return {
        "code": 200,
        "data": {
            "total": len(_feedback_log),
            "by_event_type": dict(counts),
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        }
    }

# B-API-05 SSE流式输出接口
async def sse_event_generator(scenario_type: str, project_id: str, dry_run: bool = True) -> AsyncGenerator[str, None]:
    """SSE事件生成器，流式输出执行过程"""
    # 发送开始事件
    yield f"data: {json.dumps({'type': 'start', 'message': '开始执行场景流程', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
    await asyncio.sleep(0.5)
    
    # 发送触发事件
    yield f"data: {json.dumps({'type': 'trigger', 'message': f'触发{scenario_type}场景', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
    await asyncio.sleep(0.5)
    
    # 发送调用A端接口事件
    yield f"data: {json.dumps({'type': 'call_a_api', 'message': '调用子系统A接口获取数据', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
    
    # 执行实际流程
    trigger_context = trigger_engine.manual_trigger(
        scenario_type=ScenarioType(scenario_type),
        project_id=project_id,
        dry_run=dry_run
    )
    
    yield f"data: {json.dumps({'type': 'data_received', 'message': '收到子系统A返回数据', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
    await asyncio.sleep(0.5)
    
    # 发送生成内容事件
    yield f"data: {json.dumps({'type': 'generate_content', 'message': '生成卡片/任务内容', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
    
    result = await workflow_orchestrator.execute(trigger_context)
    
    # 发送完成事件
    complete_payload = json.dumps({
        'type': 'complete',
        'message': '流程执行完成',
        'timestamp': asyncio.get_event_loop().time(),
        'data': {
            'trace_id': result['trace_id'],
            'preview_id': result['preview_id'],
            'requires_confirmation': result['requires_confirmation']
        }
    })
    yield f"data: {complete_payload}\n\n"

@app.get("/agent/v1/stream/trigger", response_class=StreamingResponse)
async def stream_trigger(scenario_type: str, project_id: str, dry_run: Optional[bool] = True):
    """SSE流式触发接口，实时返回执行过程"""
    return StreamingResponse(
        sse_event_generator(scenario_type, project_id, dry_run),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

# B-API-02 卡片预览接口
@app.get("/agent/v1/cards/preview/{preview_id}")
async def get_card_preview(preview_id: str):
    """获取卡片预览内容"""
    preview_data = get_preview_result(preview_id)
    return {
        "code": 200,
        "data": preview_data
    }

# B-API-02-1 任务预览接口
@app.get("/agent/v1/tasks/preview/{preview_id}")
async def get_task_preview(preview_id: str):
    """获取任务预览内容"""
    preview_data = get_preview_result(preview_id)
    return {
        "code": 200,
        "data": preview_data
    }

# B-API-02-2 风险预警预览接口
@app.get("/agent/v1/alerts/preview/{preview_id}")
async def get_alert_preview(preview_id: str):
    """获取风险预警预览内容"""
    preview_data = get_preview_result(preview_id)
    return {
        "code": 200,
        "data": preview_data
    }


# ============== 飞书回调接口 ==============

def _parse_message_text(content_str: str) -> str:
    """解析飞书消息内容 JSON，提取纯文本"""
    try:
        content = json.loads(content_str)
        return content.get("text", content_str)
    except Exception:
        return content_str


def _detect_scenario(text: str) -> Optional[str]:
    """根据消息关键词判断要触发的场景"""
    text = text.lower()
    if any(k in text for k in ["会前", "会议背景", "会前准备", "pre_meeting", "pre-meeting"]):
        return "pre_meeting"
    if any(k in text for k in ["会后", "action item", "会议纪要", "post_meeting", "post-meeting"]):
        return "post_meeting"
    if any(k in text for k in ["周报", "本周进展", "weekly", "每周"]):
        return "weekly_insight"
    if any(k in text for k in ["风险", "预警", "延期", "risk", "alert"]):
        return "risk_alert"
    if any(k in text for k in ["对账", "跟进", "落实", "review", "key_review"]):
        return "key_review"
    return None


async def _run_scenario(scenario: str, project_id: str):
    """后台异步执行场景，结果存入 preview_cache"""
    try:
        trigger_context = trigger_engine.manual_trigger(
            scenario_type=ScenarioType(scenario),
            project_id=project_id,
            dry_run=False,
        )
        result = await workflow_orchestrator.execute(trigger_context)
        if result.get("preview_id"):
            preview_cache[result["preview_id"]] = result
        logger.info(f"[callback] scenario={scenario} preview_id={result.get('preview_id')}")
    except Exception as e:
        logger.error(f"[callback] scenario={scenario} failed: {e}")


@app.post("/feishu/callback")
async def feishu_callback(request: Request, background_tasks: BackgroundTasks):
    """
    飞书事件回调入口。
    - URL 验证：飞书首次配置时发 challenge，直接回传。
    - 消息事件：解析文本关键词 → 触发对应场景 → 后台执行。
    """
    body = await request.json()

    # 1. URL 验证握手（飞书第一次调通时发的）
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge", "")})

    # 2. 事件处理（schema 2.0）
    event_type = body.get("header", {}).get("event_type", "")
    if event_type == "im.message.receive_v1":
        event = body.get("event", {})
        msg = event.get("message", {})
        msg_type = msg.get("message_type", "")
        content_str = msg.get("content", "{}")
        sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "unknown")

        if msg_type == "text":
            text = _parse_message_text(content_str)
            logger.info(f"[callback] received text from {sender_id}: {text[:80]}")
            scenario = _detect_scenario(text)
            if scenario:
                project_id = settings.demo_project_id
                logger.info(f"[callback] triggering scenario={scenario} project={project_id}")
                background_tasks.add_task(_run_scenario, scenario, project_id)
                return JSONResponse({"code": 0, "msg": f"触发 {scenario} 场景"})
            else:
                return JSONResponse({"code": 0, "msg": "未识别关键词，忽略"})

    # 其余事件一律返回 200
    return JSONResponse({"code": 0})


@app.post("/feishu/card_callback")
async def feishu_card_callback(request: Request, background_tasks: BackgroundTasks):
    """
    飞书卡片交互回调。
    用户点击卡片按钮时飞书会 POST 到这里。
    需要在飞书开放平台 → 机器人 → 卡片回调URL 里填写此地址。
    """
    body = await request.json()

    # URL 验证握手
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge", "")})

    action = body.get("action", {})
    value = action.get("value", {})
    act = value.get("action", "")
    preview_id = value.get("preview_id", "")
    operator = body.get("operator", {}).get("open_id", "unknown")

    logger.info(f"[card_callback] action={act} preview_id={preview_id} operator={operator}")

    # 记录反馈
    import uuid as _uuid
    from datetime import datetime as _dt
    entry = {
        "feedback_event_id": f"fb_{_uuid.uuid4().hex[:8]}",
        "card_id": preview_id,
        "event_type": f"card_click:{act}",
        "user_id": operator,
        "timestamp": _dt.now().isoformat(),
    }
    _feedback_log.append(entry)
    try:
        with open(_feedback_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # 确认创建全部任务
    if act == "confirm_create_all" and preview_id:
        try:
            preview_data = get_preview_result(preview_id)
            preview_result = preview_data.get("preview_result", {})
            processed_items = preview_result.get("processed_items", [])
            item_ids = [it["id"] for it in processed_items]
            background_tasks.add_task(_confirm_tasks_background, preview_id, item_ids, operator)
            return JSONResponse({"toast": {"type": "info", "content": f"正在创建 {len(item_ids)} 个任务…"}})
        except Exception as e:
            logger.error(f"[card_callback] confirm_create_all failed: {e}")
            return JSONResponse({"toast": {"type": "error", "content": "任务创建失败，请重试"}})

    if act == "cancel_create":
        return JSONResponse({"toast": {"type": "info", "content": "已取消"}})

    # 默认：返回 200 让飞书不报错
    return JSONResponse({})


async def _confirm_tasks_background(preview_id: str, item_ids: list, operator: str):
    """后台执行任务确认创建"""
    try:
        app_id = settings.feishu_app_id
        app_secret = settings.feishu_app_secret
        tasklist_guid = settings.feishu_tasklist_guid
        preview_data = get_preview_result(preview_id)
        preview_result = preview_data.get("preview_result", {})
        processed_items = preview_result.get("processed_items", [])
        item_map = {it["id"]: it for it in processed_items}
        created = []
        for item_id in item_ids:
            item = item_map.get(item_id)
            if not item:
                continue
            summary = item.get("title", item_id)
            due_date = item.get("deadline")
            owner_name = item.get("owner_name", "")
            source_url = item.get("source_url", "")
            description = f"负责人：{owner_name}\n来源：{source_url}".strip(" \n：")
            if app_id and app_secret:
                task = create_feishu_task(app_id=app_id, app_secret=app_secret,
                                          summary=summary, due_date=due_date,
                                          description=description, tasklist_guid=tasklist_guid or None)
                task_id = task.get("guid", item_id)
            else:
                task_id = f"mock_{item_id}"
            created.append({"task_id": task_id, "title": summary, "owner": owner_name, "source_url": source_url})
        append_confirmed_tasks(created)
        bitable_app_token = settings.feishu_bitable_app_token
        bitable_table_id = settings.feishu_bitable_table_id
        if app_id and app_secret and bitable_app_token and bitable_table_id and created:
            sync_tasks_to_bitable(app_id=app_id, app_secret=app_secret,
                                  bitable_app_token=bitable_app_token, table_id=bitable_table_id,
                                  tasks=[{"title": t["title"], "owner_name": t["owner"],
                                          "task_id": t["task_id"], "source_url": t.get("source_url", "")}
                                         for t in created],
                                  meeting_source=preview_id)
        logger.info(f"[card_callback] confirm_create_all done: {len(created)} tasks operator={operator}")
    except Exception as e:
        logger.error(f"[card_callback] _confirm_tasks_background failed: {e}")
