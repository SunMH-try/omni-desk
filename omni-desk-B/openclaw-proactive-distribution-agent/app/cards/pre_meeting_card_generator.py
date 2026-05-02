from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List
from app.triggers.trigger_engine import TriggerContext


def _src(url: str, label: str = "来源") -> str:
    """只有真实 URL 才渲染来源链接，避免 # 出现在卡片里。"""
    if url and url != "#" and url.startswith("http"):
        return f" [📎{label}]({url})"
    return ""


class PreMeetingCardGenerator:
    def __init__(self):
        self.output_dir = Path(__file__).parent.parent.parent / "outputs" / "cards"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, meeting_context: Dict[str, Any], trigger_context: TriggerContext) -> Dict[str, Any]:
        preview_id = f"preview_pre_meeting_{trigger_context.trace_id.split('_')[-1]}"

        # evidence_id -> source_url 映射
        evidence_sources: dict = meeting_context.get("evidence_sources", {})
        evidence_ids: list = meeting_context.get("evidence_ids", [])

        def _url(idx: int) -> str:
            if idx < len(evidence_ids):
                return evidence_sources.get(evidence_ids[idx], "") or "#"
            return "#"

        # ── 背景事实 ──────────────────────────────────────────────────
        background_facts: List[Dict] = []
        for i, fact in enumerate(meeting_context.get("background_facts", [])):
            background_facts.append({
                "id": f"fact_{i+1}",
                "content": fact if isinstance(fact, str) else fact.get("content", str(fact)),
                "source_url": _url(i),
            })

        # ── 上次决议 ──────────────────────────────────────────────────
        last_resolutions: List[Dict] = []
        for i, decision in enumerate(meeting_context.get("last_decisions", [])):
            content = decision if isinstance(decision, str) else decision.get("content", str(decision))
            status = "completed" if isinstance(decision, str) else decision.get("status", "completed")
            last_resolutions.append({
                "id": f"decision_{i+1}",
                "content": content,
                "status": status,
                "source_url": _url(i),
            })

        # ── 未关闭风险 ────────────────────────────────────────────────
        risk_reminders: List[Dict] = []
        for i, risk in enumerate(meeting_context.get("open_risks", [])):
            content = risk if isinstance(risk, str) else risk.get("content", str(risk))
            risk_reminders.append({
                "id": f"risk_{i+1}",
                "content": content,
                "level": "high" if any(k in content for k in ["阻塞", "P0", "紧急"]) else "medium",
                "source_url": _url(i),
            })

        # ── 待确认问题 ────────────────────────────────────────────────
        pending_questions: List[Dict] = []
        for i, q in enumerate(meeting_context.get("pending_questions", [])):
            content = q if isinstance(q, str) else q.get("content", str(q))
            raised_by = "项目成员" if isinstance(q, str) else q.get("raised_by", "项目成员")
            pending_questions.append({
                "id": f"q_{i+1}",
                "content": content,
                "raised_by": raised_by,
                "source_url": _url(i),
            })

        # ── 上次会议确认任务 + 实时完成情况 ─────────────────────────────
        previous_tasks: List[Dict] = []
        for t in meeting_context.get("previous_confirmed_tasks", []):
            live = t.get("live_status", "unknown")
            status_label = {
                "completed": "已完成",
                "in_progress": "进行中",
                "unknown": "未知",
            }.get(live, live)
            previous_tasks.append({
                "title": t.get("title", ""),
                "owner": t.get("owner", ""),
                "status": live,
                "status_label": status_label,
                "source_url": t.get("source_url", "#"),
            })

        adapted = {
            "meeting_title": meeting_context.get("meeting_title", "项目例会"),
            "meeting_time": meeting_context.get("meeting_time", "待确认"),
            "attendees": meeting_context.get("attendees", []),
            "background_facts": background_facts,
            "last_resolutions": last_resolutions,
            "risk_reminders": risk_reminders,
            "pending_questions": pending_questions,
            "previous_tasks": previous_tasks,
        }

        card_json = self._build_feishu_card(adapted, preview_id)
        markdown = self._build_markdown(adapted)
        self._save_to_file(preview_id, card_json, markdown)

        return {
            "preview_id": preview_id,
            "card_title": f"{adapted['meeting_title']} 会前背景",
            "card_json": card_json,
            "markdown": markdown,
            "dry_run": trigger_context.dry_run,
            "trace_id": trigger_context.trace_id,
        }

    def _build_feishu_card(self, ctx: Dict[str, Any], preview_id: str) -> Dict[str, Any]:
        elements = []

        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**📅 {ctx['meeting_title']}**\n"
                    f"⏰ {ctx['meeting_time']}\n"
                    f"👥 参会人数：{len(ctx['attendees'])}"
                ),
            },
        })
        elements.append({"tag": "hr"})

        if ctx["background_facts"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**📌 背景事实**"}})
            for i, item in enumerate(ctx["background_facts"], 1):
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"{i}. {item['content']}{_src(item['source_url'])}"},
                })
            elements.append({"tag": "hr"})

        if ctx["last_resolutions"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**✅ 上次会议决议**"}})
            for i, item in enumerate(ctx["last_resolutions"], 1):
                icon = "✅" if item["status"] == "completed" else "⏳"
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"{icon} {i}. {item['content']}{_src(item['source_url'])}"},
                })
            elements.append({"tag": "hr"})

        if ctx["risk_reminders"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🚨 未关闭风险**"}})
            for i, risk in enumerate(ctx["risk_reminders"], 1):
                color = "red" if risk["level"] == "high" else "orange"
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{i}. <font color='{color}'>{risk['content']}</font>{_src(risk['source_url'])}",
                    },
                })
            elements.append({"tag": "hr"})

        if ctx["pending_questions"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**❓ 待确认问题**"}})
            for i, q in enumerate(ctx["pending_questions"], 1):
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{i}. {q['content']}（{q['raised_by']}）{_src(q['source_url'])}",
                    },
                })
            elements.append({"tag": "hr"})

        if ctx.get("previous_tasks"):
            done_n = sum(1 for t in ctx["previous_tasks"] if t["status"] == "completed")
            total_n = len(ctx["previous_tasks"])
            rate = f"{int(done_n/total_n*100)}%" if total_n else "N/A"
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**📊 上次会议任务完成情况（{done_n}/{total_n}，{rate}）**",
                },
            })
            for t in ctx["previous_tasks"]:
                icon = "✅" if t["status"] == "completed" else "⏳" if t["status"] == "in_progress" else "❓"
                owner = f" 👤 {t['owner']}" if t["owner"] else ""
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{icon} {t['title']}{owner}（{t['status_label']}）",
                    },
                })
            elements.append({"tag": "hr"})

        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "_如需会后抽取任务，请在群里分享会议纪要文档（含「会议纪要」关键词）_",
            },
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🔔 会前背景提醒"},
                "template": "blue",
            },
            "elements": elements,
        }

    def _build_markdown(self, ctx: Dict[str, Any]) -> str:
        lines = [
            f"# {ctx['meeting_title']} 会前背景",
            f"- **会议时间**: {ctx['meeting_time']}",
            f"- **参会人数**: {len(ctx['attendees'])}",
            "",
        ]
        if ctx["background_facts"]:
            lines.append("## 📌 背景事实")
            for i, item in enumerate(ctx["background_facts"], 1):
                lines.append(f"{i}. {item['content']} [来源]({item['source_url']})")
            lines.append("")
        if ctx["last_resolutions"]:
            lines.append("## ✅ 上次会议决议")
            for i, item in enumerate(ctx["last_resolutions"], 1):
                lines.append(f"{i}. {item['content']} [来源]({item['source_url']})")
            lines.append("")
        if ctx["risk_reminders"]:
            lines.append("## 🚨 未关闭风险")
            for i, risk in enumerate(ctx["risk_reminders"], 1):
                lines.append(f"{i}. {risk['content']} [来源]({risk['source_url']})")
            lines.append("")
        if ctx["pending_questions"]:
            lines.append("## ❓ 待确认问题")
            for i, q in enumerate(ctx["pending_questions"], 1):
                lines.append(f"{i}. {q['content']}（{q['raised_by']}）[来源]({q['source_url']})")
            lines.append("")
        if ctx.get("previous_tasks"):
            done_n = sum(1 for t in ctx["previous_tasks"] if t["status"] == "completed")
            total_n = len(ctx["previous_tasks"])
            rate = f"{int(done_n/total_n*100)}%" if total_n else "N/A"
            lines.append(f"## 📊 上次会议任务完成情况（{done_n}/{total_n}，{rate}）")
            for t in ctx["previous_tasks"]:
                icon = "✅" if t["status"] == "completed" else "⏳"
                lines.append(f"- {icon} {t['title']}（{t['status_label']}）")
            lines.append("")
        return "\n".join(lines)

    def _save_to_file(self, preview_id: str, card_json: Dict[str, Any], markdown: str):
        (self.output_dir / f"{preview_id}.json").write_text(
            json.dumps(card_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.output_dir / f"{preview_id}.md").write_text(markdown, encoding="utf-8")


pre_meeting_card_generator = PreMeetingCardGenerator()
