"""
飞书长连接监听器 — 收到群消息后触发对应场景并把卡片发回群里。

运行方式：
    python listen.py

关键词触发规则：
    "会前"  → pre_meeting
    "会后"  → post_meeting
    "周报"  → weekly_insight
    "风险"  → risk_alert
"""
from __future__ import annotations
import json
import logging
import os
import time
import httpx
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger, P2CardActionTriggerResponse, CallBackToast
)
from collections import deque

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

APP_ID     = "cli_a97a69f02bf8dbdd"
APP_SECRET = "xpubXvVPMDXryNJMmJj0BdZhbIfPk2fF"
B_API_URL  = "http://localhost:8200/agent/v1/triggers/run"
PROJECT_ID = "openclaw_project"
FEISHU_API = "https://open.feishu.cn/open-apis"

# 超过这个秒数的消息认为是"历史消息"，直接忽略
MSG_MAX_AGE_SECONDS = 60

# 最近处理过的消息 ID，防止重复触发（最多保留 200 条）
_processed_ids: deque = deque(maxlen=200)

_token_cache = {"token": "", "expire": 0}


def _get_token() -> str:
    import time
    if _token_cache["token"] and time.time() < _token_cache["expire"] - 60:
        return _token_cache["token"]
    resp = httpx.post(
        f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    d = resp.json()
    _token_cache["token"] = d["tenant_access_token"]
    _token_cache["expire"] = __import__("time").time() + d.get("expire", 7200)
    return _token_cache["token"]


def _send_card_to_chat(chat_id: str, card_json: dict, fallback_text: str = ""):
    """把飞书卡片发送到指定群聊"""
    try:
        headers = {"Authorization": f"Bearer {_get_token()}"}
        body = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_json, ensure_ascii=False),
        }
        resp = httpx.post(
            f"{FEISHU_API}/im/v1/messages?receive_id_type=chat_id",
            headers=headers,
            json=body,
            timeout=30,
        )
        d = resp.json()
        if d.get("code") == 0:
            logger.info(f"卡片已发送到群 {chat_id}")
        else:
            logger.warning(f"发送卡片失败 code={d.get('code')} msg={d.get('msg','')}")
            # 卡片发送失败时用纯文本兜底
            if fallback_text:
                _send_text_to_chat(chat_id, fallback_text)
    except Exception as e:
        logger.error(f"发送卡片异常: {e}")


def _send_text_to_chat(chat_id: str, text: str):
    """发送纯文本消息到群"""
    try:
        headers = {"Authorization": f"Bearer {_get_token()}"}
        body = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        httpx.post(
            f"{FEISHU_API}/im/v1/messages?receive_id_type=chat_id",
            headers=headers,
            json=body,
            timeout=30,
        )
    except Exception as e:
        logger.error(f"发送文本异常: {e}")


def _parse_text(content_str: str) -> str:
    try:
        return json.loads(content_str).get("text", "")
    except Exception:
        return content_str


_MINUTES_KEYWORDS = ["会议纪要", "会后总结", "minutes", "会议记录", "meeting notes"]
_FEISHU_DOC_RE = __import__("re").compile(
    r'https?://[a-zA-Z0-9\-]+\.feishu\.cn/(docx|wiki|docs)/([A-Za-z0-9]+)'
)


def _is_meeting_minutes_share(text: str) -> bool:
    """消息里包含飞书文档链接，且上下文包含会议纪要关键词，认为是分享会议纪要。"""
    has_doc_link = bool(_FEISHU_DOC_RE.search(text))
    has_keyword = any(k in text.lower() for k in _MINUTES_KEYWORDS)
    return has_doc_link and has_keyword


def _detect_scenario(text: str):
    t = text.lower()
    if any(k in t for k in ["会前", "会议背景", "pre_meeting"]):
        return "pre_meeting"
    if any(k in t for k in ["会后", "action", "任务抽取", "post_meeting"]):
        return "post_meeting"
    if any(k in t for k in ["周报", "本周进展", "weekly"]):
        return "weekly_insight"
    if any(k in t for k in ["风险", "预警", "延期", "risk"]):
        return "risk_alert"
    if any(k in t for k in ["对账", "跟进", "落实", "review"]):
        return "key_review"
    if any(k in t for k in ["确认创建", "confirm task", "创建任务"]):
        return "confirm_tasks"
    return None


def on_message(data: P2ImMessageReceiveV1) -> None:
    msg = data.event.message
    if msg.message_type != "text":
        return

    # 去重：同一条消息 ID 只处理一次
    msg_id = msg.message_id
    if msg_id in _processed_ids:
        logger.info(f"重复消息 {msg_id}，跳过")
        return
    _processed_ids.append(msg_id)

    # 过滤历史消息：消息发送时间距现在超过 60 秒则忽略
    try:
        msg_ts = int(msg.create_time) / 1000  # 飞书返回毫秒
        age = time.time() - msg_ts
        if age > MSG_MAX_AGE_SECONDS:
            logger.info(f"历史消息（{age:.0f}s 前），跳过: {msg_id}")
            return
    except Exception:
        pass  # 拿不到时间戳就继续处理

    text = _parse_text(msg.content)
    chat_id = msg.chat_id
    sender = data.event.sender.sender_id.open_id

    # ── 特殊路径：分享会议纪要文档，无需@机器人直接触发会后场景 ──────────
    if _is_meeting_minutes_share(text):
        logger.info(f"[{sender}] 分享了会议纪要，自动触发会后场景")
        doc_content = _fetch_minutes_content(text)
        if not doc_content:
            _send_text_to_chat(
                chat_id,
                "⚠️ 无法读取文档内容（可能缺少权限）。\n"
                "请在飞书开发者后台为 bot 添加权限：\n"
                "  • docx:document:readonly\n"
                "  • wiki:wiki:readonly\n"
                "发布后重启 listen.py 再试。\n\n"
                "如需立即测试，可直接把会议纪要文字粘贴到群里，同时 @OpenClaw 会后。"
            )
            return
        _run_scenario_and_reply(chat_id, "post_meeting", raw_text=doc_content)
        return

    # ── 普通路径：必须@机器人 ────────────────────────────────────────────
    mentions = getattr(msg, "mentions", None) or []
    mention_names = [getattr(m, "name", "") for m in mentions]
    if mention_names:
        logger.info(f"mentions: {mention_names}")
    bot_mentioned = any(
        name in ("OpenClaw MeetingOps Agent", "OpenClaw")
        for name in mention_names
    )
    if not bot_mentioned:
        logger.info("未@机器人，忽略")
        return

    logger.info(f"收到消息 [{sender}] 群[{chat_id}]: {text[:80]}")

    scenario = _detect_scenario(text)
    if not scenario:
        _send_text_to_chat(
            chat_id,
            "👋 你好！支持以下指令：\n"
            "【会议闭环流程】\n"
            "1️⃣  会议前：@OpenClaw 会前  → 背景摘要+上次任务完成率\n"
            "2️⃣  会议后：在群里分享会议纪要文档（消息含「会议纪要」）→ 自动抽取 Action Items\n"
            "3️⃣  确认任务：@OpenClaw 确认创建  → 写入飞书任务\n"
            "\n【其他指令】\n"
            "• @OpenClaw 周报  — 本周项目进展汇总\n"
            "• @OpenClaw 风险  — 扫描当前风险点\n"
            "• @OpenClaw 对账  — 重点事项完成情况"
        )
        return

    logger.info(f"触发场景: {scenario}，正在处理...")
    if scenario == "confirm_tasks":
        _confirm_latest_tasks(chat_id)
    elif scenario == "post_meeting":
        _run_scenario_and_reply(chat_id, "post_meeting", raw_text=text)
    else:
        _run_scenario_and_reply(chat_id, scenario)


def _fetch_minutes_content(text: str) -> str:
    """从消息文本中提取飞书文档链接并读取文档纯文本内容。失败返回空字符串。"""
    try:
        from app.feishu.doc_reader import fetch_doc_content
        m = _FEISHU_DOC_RE.search(text)
        if not m:
            return ""
        doc_type, token = m.group(1), m.group(2)
        logger.info(f"读取飞书文档: type={doc_type} token={token}")
        content = fetch_doc_content(doc_type, token, _get_token)
        if content:
            logger.info(f"成功读取文档内容，共 {len(content)} 字符")
        else:
            logger.warning("文档内容为空，将以消息原文兜底")
        return content
    except Exception as e:
        logger.error(f"_fetch_minutes_content 失败: {e}")
        return ""


def _run_scenario_and_reply(chat_id: str, scenario: str, raw_text: str = "") -> None:
    """触发 B 端场景并把卡片/文本发回群里。"""
    _send_text_to_chat(chat_id, f"⏳ 正在生成{_scenario_name(scenario)}，请稍候...")
    try:
        metadata = {}
        if raw_text:
            metadata["raw_text"] = raw_text
        resp = httpx.post(B_API_URL, json={
            "trigger_type": "event",
            "scenario_type": scenario,
            "project_id": PROJECT_ID,
            "dry_run": False,
            "metadata": metadata,
        }, timeout=300)
        data_payload = resp.json().get("data", {})
        preview_id = data_payload.get("preview_id", "")
        logger.info(f"场景执行完成: preview_id={preview_id}")

        card_resp = httpx.get(
            f"http://localhost:8200/agent/v1/cards/preview/{preview_id}", timeout=30
        )
        card_data = card_resp.json().get("data", {})
        block = (
            card_data.get("card_result") or
            card_data.get("alert_result") or
            card_data.get("preview_result") or {}
        )
        card_json = (
            card_data.get("card_json") or
            card_data.get("preview_card") or
            block.get("card_json") or
            block.get("preview_card")
        )
        markdown = card_data.get("markdown") or block.get("markdown") or ""

        # 会后场景：0 个任务时不发空卡片，直接给引导
        if scenario == "post_meeting":
            import os as _os, glob as _glob2
            cards_dir = _os.path.join(_os.path.dirname(__file__), "outputs", "cards")
            preview_id = data_payload.get("preview_id", "")
            items_path = _os.path.join(cards_dir, f"{preview_id}_items.json")
            item_count = 0
            if _os.path.exists(items_path):
                import json as _j2
                try:
                    item_count = len(_j2.loads(open(items_path, encoding="utf-8").read()))
                except Exception:
                    pass
            if item_count == 0:
                _send_text_to_chat(
                    chat_id,
                    "📄 未从文档中提取到 Action Items。\n\n"
                    "请在群里分享飞书文档，并在消息中包含「会议纪要」关键词，Agent 会自动识别文档并抽取任务。\n"
                    "例如：「这是今天的会议纪要 [文档链接]」",
                )
                return

        if card_json:
            _send_card_to_chat(chat_id, card_json)
        elif markdown:
            _send_text_to_chat(chat_id, markdown[:2000])
        else:
            _send_text_to_chat(chat_id, "处理完成，但无法生成卡片。")

        # 场景结束后给出下一步提示
        hint = _next_step_hint(scenario)
        if hint:
            _send_text_to_chat(chat_id, hint)
    except Exception as e:
        logger.error(f"场景执行失败: {e}")
        _send_text_to_chat(chat_id, f"❌ {_scenario_name(scenario)}生成失败: {e}")


def _confirm_latest_tasks(chat_id: str) -> None:
    """确认创建最近一次会后任务预览里的所有任务。"""
    _send_text_to_chat(chat_id, "⏳ 正在创建任务，请稍候...")
    try:
        import os, glob as _glob, json as _json
        cards_dir = os.path.join(os.path.dirname(__file__), "outputs", "cards")
        # 只匹配 _items.json，里面直接存的是 processed_items 列表
        pattern = os.path.join(cards_dir, "preview_task_*_items.json")
        files = sorted(_glob.glob(pattern), key=os.path.getmtime, reverse=True)
        if not files:
            _send_text_to_chat(chat_id, "❌ 没有找到待确认的任务预览，请先触发会后场景（分享会议纪要或发送 @OpenClaw 会后）。")
            return

        # 直接读 items 列表，不走 HTTP
        with open(files[0], encoding="utf-8") as f:
            items = _json.load(f)
        # 去掉路径得到 preview_id（去掉 _items.json 后缀）
        basename = os.path.basename(files[0])  # preview_task_xxx_items.json
        preview_id = basename.replace("_items.json", "")

        if not items:
            _send_text_to_chat(chat_id, "❌ 任务预览为空，请重新触发会后场景。")
            return

        item_ids = [it["id"] for it in items]
        confirm_resp = httpx.post(
            "http://localhost:8200/agent/v1/tasks/confirm-create",
            json={
                "preview_id": preview_id,
                "confirmed_items": item_ids,
                "target_task_group": "default",
            },
            timeout=60,
        )
        result = confirm_resp.json().get("data", {})
        created = result.get("created_tasks", [])
        bitable = result.get("bitable_updated", False)
        notified = result.get("notified_count", 0)

        header = f"✅ 已创建 {len(created)} 个飞书任务"
        if bitable:
            header += "，已同步 Bitable ✔"
        if notified:
            header += f"，已通知 {notified} 位负责人 ✉️"
        lines = [header]
        for t in created:
            lines.append(f"  • {t.get('title', '')}  👤 {t.get('owner', '待分配')}")
        lines.append("\n💡 下次会前发 @OpenClaw 会前，可查看这些任务的完成情况。")
        _send_text_to_chat(chat_id, "\n".join(lines))
    except Exception as e:
        logger.error(f"confirm_latest_tasks 失败: {e}")
        _send_text_to_chat(chat_id, f"❌ 任务创建失败: {e}")


def _next_step_hint(scenario: str) -> str:
    return {
        "pre_meeting": "📋 会议结束后，在群里分享会议纪要文档（消息包含「会议纪要」），我会自动抽取 Action Items。",
        "post_meeting": "✅ 确认无误后，发送 @OpenClaw 确认创建 即可将任务同步到飞书任务。",
        "weekly_insight": "⚠️ 如需查看具体风险，可发送 @OpenClaw 风险。",
        "risk_alert": "📋 如需追踪任务完成情况，可发送 @OpenClaw 对账。",
        "key_review": "🔔 下次会前发 @OpenClaw 会前，可查看任务完成率。",
    }.get(scenario, "")


def _scenario_name(scenario: str) -> str:
    return {
        "pre_meeting": "会前背景卡片",
        "post_meeting": "会后任务预览",
        "weekly_insight": "周报洞察",
        "risk_alert": "风险预警",
        "key_review": "重点事项对账",
    }.get(scenario, scenario)


def on_card_action(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    """处理卡片按钮点击——通过长连接接收，无需公网 URL。"""
    def _toast(t: str, msg: str) -> P2CardActionTriggerResponse:
        resp = P2CardActionTriggerResponse()
        resp.toast = CallBackToast()
        resp.toast.type = t
        resp.toast.content = msg
        return resp

    try:
        event = data.event
        action = event.action if event else None
        value: dict = (action.value or {}) if action else {}
        act = value.get("action", "")
        preview_id = value.get("preview_id", "")
        operator = event.operator.open_id if (event and event.operator) else "unknown"

        logger.info(f"[card] action={act} preview_id={preview_id} operator={operator} raw_value={value}")

        if act == "confirm_create_all" and preview_id:
            # 直接从磁盘读 _items.json，不依赖内存缓存
            items_path = os.path.join(
                os.path.dirname(__file__), "outputs", "cards",
                f"{preview_id}_items.json"
            )
            if not os.path.exists(items_path):
                return _toast("warning", "找不到任务预览，请重新触发会后场景")
            with open(items_path, encoding="utf-8") as f:
                items = json.load(f)
            item_ids = [it["id"] for it in items]
            if not item_ids:
                return _toast("warning", "任务列表为空，请重新触发会后场景")

            confirm_resp = httpx.post(
                "http://localhost:8200/agent/v1/tasks/confirm-create",
                json={
                    "preview_id": preview_id,
                    "confirmed_items": item_ids,
                    "target_task_group": "default",
                },
                timeout=60,
            )
            result = confirm_resp.json().get("data", {})
            created = result.get("created_tasks", [])
            bitable = result.get("bitable_updated", False)
            notified = result.get("notified_count", 0)
            msg = f"已创建 {len(created)} 个飞书任务"
            if bitable:
                msg += "，已同步 Bitable"
            if notified:
                msg += f"，已通知 {notified} 位负责人"
            return _toast("success", msg + " ✅")

        if act == "cancel_create":
            return _toast("info", "已取消")

        if act == "edit_and_create":
            return _toast("info", "请直接发送 @OpenClaw 确认创建 来同步任务")

        if act:
            return _toast("info", "请使用文字指令操作，发送 @OpenClaw 帮助 查看支持的命令")

    except Exception as e:
        logger.error(f"[card] 处理卡片动作失败: {e}")
        return _toast("error", f"处理失败：{e}")

    return P2CardActionTriggerResponse()


def main():
    # 启动主动推送调度器（后台线程）
    try:
        from scheduler import run_scheduler
        target_chat = os.environ.get(
            "FEISHU_TARGET_CHAT_ID",
            os.environ.get("FEISHU_CHAT_IDS", "").split(",")[0].strip()
        )
        calendar_id = os.environ.get("FEISHU_CALENDAR_ID", "")
        run_scheduler(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            chat_id=target_chat,
            project_id=PROJECT_ID,
            calendar_id=calendar_id,
        )
    except Exception as e:
        logger.warning(f"调度器启动失败（不影响监听）: {e}")

    handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message) \
        .register_p2_card_action_trigger(on_card_action) \
        .build()

    ws_client = lark.ws.Client(
        APP_ID,
        APP_SECRET,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )

    logger.info("飞书长连接监听器启动，等待群消息...")
    ws_client.start()


if __name__ == "__main__":
    main()
