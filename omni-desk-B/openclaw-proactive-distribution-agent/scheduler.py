"""主动推送调度器 — 定时生成周报/风险预警并推送到飞书群。

触发规则：
    每周一 09:00  → weekly_insight 周报
    工作日 18:00  → risk_alert    风险预警

启动方式：在 listen.py 的 main() 里调用 run_scheduler()，作为后台线程运行。
"""
from __future__ import annotations
import datetime
import json
import logging
import threading
import time
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
FEISHU_API = "https://open.feishu.cn/open-apis"

_sched_token: dict = {"token": "", "expire": 0.0}


def run_scheduler(
    app_id: str,
    app_secret: str,
    chat_id: str,
    b_api_base: str = "http://localhost:8200",
    project_id: str = "openclaw_project",
    calendar_id: str = "",
) -> None:
    """在守护线程里启动调度循环。"""
    if not chat_id:
        logger.warning("[scheduler] 未配置 FEISHU_TARGET_CHAT_ID，跳过主动推送调度")
        return
    t = threading.Thread(
        target=_loop,
        args=(app_id, app_secret, chat_id, b_api_base, project_id, calendar_id),
        daemon=True,
        name="proactive-scheduler",
    )
    t.start()
    cal_info = f"，日历轮询已启用 ({calendar_id})" if calendar_id else "，未配置日历 ID（跳过会前自动提醒）"
    logger.info(f"[scheduler] 主动推送调度器已启动，目标群 {chat_id}{cal_info}")


def _loop(
    app_id: str, app_secret: str, chat_id: str,
    b_api_base: str, project_id: str, calendar_id: str = ""
) -> None:
    fired: set = set()

    while True:
        try:
            now = datetime.datetime.now()
            hour_key = now.strftime("%Y%m%d%H")
            today = now.strftime("%Y%m%d")

            # 每周一 09:00 推送周报
            if now.weekday() == 0 and now.hour == 9 and f"weekly_{hour_key}" not in fired:
                logger.info("[scheduler] 触发周一周报")
                _push(app_id, app_secret, chat_id, b_api_base, project_id,
                      "weekly_insight", "📅 每周项目周报（自动推送）")
                fired.add(f"weekly_{hour_key}")

            # 工作日 18:00 推送风险预警
            if now.weekday() < 5 and now.hour == 18 and f"risk_{hour_key}" not in fired:
                logger.info("[scheduler] 触发每日风险扫描")
                _push(app_id, app_secret, chat_id, b_api_base, project_id,
                      "risk_alert", "⚠️ 每日风险扫描（自动推送）")
                fired.add(f"risk_{hour_key}")

            # 每 5 分钟检查即将开始的会议（需配置 calendar_id）
            min_key = f"cal_{today}_{now.hour}_{now.minute // 5}"
            if calendar_id and min_key not in fired:
                _check_calendar_and_push_pre_meeting(
                    app_id, app_secret, chat_id, b_api_base, project_id,
                    calendar_id, today, fired
                )
                fired.add(min_key)

            # 清理旧 key，只保留今天的
            fired = {k for k in fired if today in k}

        except Exception as exc:
            logger.error(f"[scheduler] 调度循环异常: {exc}")

        time.sleep(60)


def _push(
    app_id: str,
    app_secret: str,
    chat_id: str,
    b_api_base: str,
    project_id: str,
    scenario: str,
    label: str,
) -> None:
    try:
        resp = httpx.post(
            f"{b_api_base}/agent/v1/triggers/run",
            json={"trigger_type": "schedule", "scenario_type": scenario,
                  "project_id": project_id, "dry_run": False},
            timeout=300,
        )
        preview_id = resp.json().get("data", {}).get("preview_id", "")
        if not preview_id:
            logger.warning(f"[scheduler] {scenario} 无 preview_id，跳过推送")
            return

        card_resp = httpx.get(f"{b_api_base}/agent/v1/cards/preview/{preview_id}", timeout=30)
        card_data = card_resp.json().get("data", {})
        block = (
            card_data.get("card_result") or
            card_data.get("alert_result") or
            card_data.get("preview_result") or {}
        )
        card_json = (
            card_data.get("card_json") or
            block.get("card_json") or
            block.get("preview_card")
        )
        markdown = card_data.get("markdown") or block.get("markdown") or ""

        token = _get_token(app_id, app_secret)
        headers = {"Authorization": f"Bearer {token}"}

        if card_json:
            httpx.post(
                f"{FEISHU_API}/im/v1/messages?receive_id_type=chat_id",
                headers=headers,
                json={"receive_id": chat_id, "msg_type": "interactive",
                      "content": json.dumps(card_json, ensure_ascii=False)},
                timeout=30,
            )
            logger.info(f"[scheduler] {label} 卡片已推送到群 {chat_id}")
        elif markdown:
            httpx.post(
                f"{FEISHU_API}/im/v1/messages?receive_id_type=chat_id",
                headers=headers,
                json={"receive_id": chat_id, "msg_type": "text",
                      "content": json.dumps({"text": f"{label}\n{markdown[:1000]}"}, ensure_ascii=False)},
                timeout=30,
            )
            logger.info(f"[scheduler] {label} 文本已推送到群 {chat_id}")
        else:
            logger.warning(f"[scheduler] {scenario} 无卡片也无 markdown，放弃推送")

    except Exception as exc:
        logger.error(f"[scheduler] {scenario} 推送失败: {exc}")


def _check_calendar_and_push_pre_meeting(
    app_id: str,
    app_secret: str,
    chat_id: str,
    b_api_base: str,
    project_id: str,
    calendar_id: str,
    today: str,
    fired: set,
) -> None:
    """检查飞书日历中 30 分钟内即将开始的会议，自动触发会前卡片（每个会议只触发一次）。"""
    try:
        token = _get_token(app_id, app_secret)
        headers = {"Authorization": f"Bearer {token}"}

        now_ts = int(datetime.datetime.now().timestamp())
        window_end_ts = now_ts + 30 * 60  # 30 分钟窗口

        resp = httpx.get(
            f"{FEISHU_API}/calendar/v4/calendars/{calendar_id}/events",
            headers=headers,
            params={
                "start_time": str(now_ts),
                "end_time": str(window_end_ts),
            },
            timeout=15,
        )
        d = resp.json()
        if d.get("code") != 0:
            logger.warning(f"[scheduler] 日历查询失败: code={d.get('code')} msg={d.get('msg')}")
            return

        events = d.get("data", {}).get("items", [])
        for event in events:
            event_id = event.get("event_id", "")
            summary = event.get("summary", "未命名会议")
            start_ts_str = event.get("start_time", {}).get("timestamp", "0")
            start_ts = int(start_ts_str)

            fire_key = f"pre_cal_{today}_{event_id}"
            if fire_key in fired:
                continue

            minutes_until = max(0, (start_ts - now_ts) // 60)
            logger.info(f"[scheduler] 即将开始的会议: 「{summary}」，约 {minutes_until} 分钟后")
            _push(
                app_id, app_secret, chat_id, b_api_base, project_id,
                "pre_meeting",
                f"📅 会前提醒：{summary}（约 {minutes_until} 分钟后开始）",
            )
            fired.add(fire_key)

    except Exception as exc:
        logger.error(f"[scheduler] 日历检查失败: {exc}")


def _get_token(app_id: str, app_secret: str) -> str:
    if _sched_token["token"] and time.time() < _sched_token["expire"] - 60:
        return _sched_token["token"]
    resp = httpx.post(
        f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=15,
    )
    d = resp.json()
    _sched_token["token"] = d["tenant_access_token"]
    _sched_token["expire"] = time.time() + d.get("expire", 7200)
    return _sched_token["token"]
