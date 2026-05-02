"""
OpenClaw Demo Script — 演示完整会议闭环流程

用法:
    python demo.py                      # 运行所有场景
    python demo.py --scenario pre       # 只运行会前场景
    python demo.py --scenario post      # 会后任务抽取
    python demo.py --scenario weekly    # 周报洞察
    python demo.py --scenario risk      # 风险预警
    python demo.py --scenario review    # 重点事项对账
    python demo.py --scenario all       # 所有场景 + 完整闭环说明

环境要求:
    B 端 API 运行在 http://localhost:8200
    A 端 API 运行在 http://localhost:8100
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import httpx

B_BASE = "http://localhost:8200"
A_BASE = "http://localhost:8100"
PROJECT_ID = "openclaw_project"

SCENARIOS = {
    "pre":     ("pre_meeting",    "会前背景提醒"),
    "post":    ("post_meeting",   "会后任务抽取"),
    "weekly":  ("weekly_insight", "周报洞察"),
    "risk":    ("risk_alert",     "风险预警"),
    "review":  ("key_review",     "重点事项对账"),
}


def _sep(title: str = ""):
    width = 60
    if title:
        pad = (width - len(title) - 2) // 2
        print("─" * pad + f" {title} " + "─" * pad)
    else:
        print("─" * width)


def check_services():
    """检查 A/B 端服务是否就绪"""
    _sep("服务健康检查")
    ok = True
    for name, base in [("B 端(8200)", B_BASE), ("A 端(8100)", A_BASE)]:
        try:
            r = httpx.get(f"{base}/health", timeout=5)
            status = r.json().get("status", "unknown")
            mock = r.json().get("mock_mode", "?")
            print(f"  ✅ {name} — status={status}  mock_mode={mock}")
        except Exception as e:
            print(f"  ❌ {name} 无法连接: {e}")
            ok = False
    return ok


def run_scenario(key: str) -> dict | None:
    """触发一个场景，返回结果 dict"""
    scenario_type, label = SCENARIOS[key]
    _sep(label)
    print(f"  触发场景: {scenario_type}")

    try:
        r = httpx.post(
            f"{B_BASE}/agent/v1/triggers/run",
            json={
                "trigger_type": "manual",
                "scenario_type": scenario_type,
                "project_id": PROJECT_ID,
                "dry_run": False,
            },
            timeout=120,
        )
        data = r.json().get("data", {})
        preview_id = data.get("preview_id", "")
        requires_confirm = data.get("requires_confirmation", False)
        print(f"  ✅ 完成  preview_id={preview_id}  needs_confirm={requires_confirm}")
    except Exception as e:
        print(f"  ❌ 触发失败: {e}")
        return None

    # 获取卡片预览
    try:
        r2 = httpx.get(f"{B_BASE}/agent/v1/cards/preview/{preview_id}", timeout=30)
        card_data = r2.json().get("data", {})
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

        if card_json:
            header = card_json.get("header", {}).get("title", {}).get("content", "")
            n_elements = len(card_json.get("elements", []))
            print(f"  卡片标题: 《{header}》  元素数: {n_elements}")
        elif markdown:
            print(f"  Markdown 预览 ({len(markdown)} 字符)")
        else:
            print("  ⚠️  未获取到卡片内容")

        return {"preview_id": preview_id, "card_data": card_data, "requires_confirmation": requires_confirm}
    except Exception as e:
        print(f"  ⚠️  获取预览失败: {e}")
        return {"preview_id": preview_id, "card_data": {}, "requires_confirmation": requires_confirm}


def demo_confirm_tasks(preview_id: str):
    """演示任务确认 — 从预览中取出所有任务并确认创建"""
    _sep("确认创建任务")
    # 获取任务列表
    try:
        r = httpx.get(f"{B_BASE}/agent/v1/tasks/preview/{preview_id}", timeout=30)
        preview_data = r.json().get("data", {})
        preview_result = preview_data.get("preview_result", {})
        items = preview_result.get("processed_items", [])
        if not items:
            print("  ⚠️  未找到可确认的任务，跳过")
            return
        item_ids = [it["id"] for it in items]
        print(f"  待确认任务数: {len(item_ids)}")
        for it in items:
            print(f"    - [{it['id']}] {it.get('title', '')}  负责人: {it.get('owner_name','待分配')}")
    except Exception as e:
        print(f"  ⚠️  获取任务列表失败: {e}")
        return

    # 确认创建
    try:
        r2 = httpx.post(
            f"{B_BASE}/agent/v1/tasks/confirm-create",
            json={
                "preview_id": preview_id,
                "confirmed_items": item_ids,
                "target_task_group": "default",
            },
            timeout=60,
        )
        result = r2.json().get("data", {})
        created = result.get("created_tasks", [])
        bitable = result.get("bitable_updated", False)
        print(f"  ✅ 已创建 {len(created)} 个飞书任务  Bitable 同步: {'是' if bitable else '否（未配置）'}")
        for t in created:
            print(f"    - {t.get('title','')}  task_id={t.get('task_id','')}")
    except Exception as e:
        print(f"  ❌ 确认创建失败: {e}")


def demo_feedback(preview_id: str):
    """演示反馈上报"""
    _sep("反馈上报")
    try:
        r = httpx.post(
            f"{B_BASE}/agent/v1/feedback/events",
            json={
                "card_id": preview_id,
                "event_type": "rate",
                "user_id": "demo_user",
                "rating": 5,
            },
            timeout=10,
        )
        fb_id = r.json().get("data", {}).get("feedback_event_id", "")
        print(f"  ✅ 反馈已记录  feedback_id={fb_id}")
    except Exception as e:
        print(f"  ⚠️  反馈上报失败: {e}")


def demo_feedback_stats():
    """打印反馈统计"""
    try:
        r = httpx.get(f"{B_BASE}/agent/v1/feedback/stats", timeout=10)
        stats = r.json().get("data", {})
        print(f"  反馈总数: {stats.get('total', 0)}  平均评分: {stats.get('avg_rating', 'N/A')}")
    except Exception:
        pass


def run_full_closed_loop():
    """完整会议闭环演示"""
    _sep("完整会议闭环演示")
    print("""
  流程说明:
  1. 会前  → 生成背景卡片（上次决议 + 风险 + 待决问题）
  2. 会中  → 群里分享会议纪要文档，系统自动检测
  3. 会后  → 自动抽取 Action Items → 人工确认 → 飞书任务 + Bitable
  4. 对账  → 查看本周期任务完成情况
  5. 下次会前 → 卡片展示上次任务完成率，形成闭环
    """)

    # Step 1: 会前
    pre_result = run_scenario("pre")
    if pre_result:
        demo_feedback(pre_result["preview_id"])
    time.sleep(1)

    # Step 2: 会后（模拟分享会议纪要后自动触发）
    post_result = run_scenario("post")
    if post_result and post_result.get("requires_confirmation"):
        demo_confirm_tasks(post_result["preview_id"])
        demo_feedback(post_result["preview_id"])
    time.sleep(1)

    # Step 3: 对账
    review_result = run_scenario("review")
    if review_result:
        demo_feedback(review_result["preview_id"])
    time.sleep(1)

    _sep("反馈统计")
    demo_feedback_stats()


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Demo Script")
    parser.add_argument("--scenario", default="all",
                        choices=list(SCENARIOS.keys()) + ["all"],
                        help="要演示的场景，默认 all（完整闭环）")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  OpenClaw — 飞书会议全生命周期智能 Agent  Demo")
    print("═" * 60 + "\n")

    if not check_services():
        print("\n  ⚠️  请先启动 A 端和 B 端服务再运行 Demo")
        sys.exit(1)

    if args.scenario == "all":
        run_full_closed_loop()
    else:
        result = run_scenario(args.scenario)
        if result and args.scenario == "post" and result.get("requires_confirmation"):
            demo_confirm_tasks(result["preview_id"])
        if result:
            demo_feedback(result["preview_id"])

    print("\n" + "═" * 60)
    print("  Demo 完成！")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
