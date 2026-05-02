from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List
from app.triggers.trigger_engine import TriggerContext


def _src(url: str) -> str:
    return f" [📎来源]({url})" if url and url != "#" and url.startswith("http") else ""


class KeyReviewGenerator:
    """重点事项对账卡片 — 展示本周期承诺 vs 实际完成情况"""

    def __init__(self):
        self.output_dir = Path(__file__).parent.parent.parent / "outputs" / "cards"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, review_data: Dict[str, Any], trigger_context: TriggerContext) -> Dict[str, Any]:
        preview_id = f"preview_review_{trigger_context.trace_id.split('_')[-1]}"

        evidence_sources: dict = review_data.get("evidence_sources", {})
        evidence_ids: list = review_data.get("evidence_ids", [])

        def _url(ev_id: str) -> str:
            return evidence_sources.get(ev_id, "") or "#"

        # 规范化每条 evidence 条目
        items: List[Dict] = []
        for ev in review_data.get("verified_evidence", []):
            ev_id = ev.get("evidence_id", "")
            items.append({
                "id": ev_id,
                "content": ev.get("summary", ev.get("content", "")),
                "source_url": ev.get("source_url") or _url(ev_id),
                "status": ev.get("status", "unknown"),
                "owner": ev.get("owner", ""),
                "deadline": ev.get("deadline", ""),
            })

        # 兼容旧格式 review_items
        for it in review_data.get("review_items", []):
            items.append({
                "id": it.get("id", ""),
                "content": it.get("content", it.get("title", "")),
                "source_url": it.get("source_url", "#"),
                "status": it.get("status", "unknown"),
                "owner": it.get("owner", it.get("owner_name", "")),
                "deadline": it.get("deadline", ""),
            })

        # 分类
        done = [i for i in items if i["status"] in ("completed", "done", "已完成")]
        in_progress = [i for i in items if i["status"] in ("in_progress", "进行中")]
        overdue = [i for i in items if i["status"] in ("overdue", "delayed", "延期", "逾期")]
        pending = [i for i in items if i["status"] not in (
            "completed", "done", "已完成", "in_progress", "进行中", "overdue", "delayed", "延期", "逾期"
        )]

        ctx = {
            "period": review_data.get("period", "本周期"),
            "project_id": trigger_context.project_id,
            "total": len(items),
            "done": done,
            "in_progress": in_progress,
            "overdue": overdue,
            "pending": pending,
        }

        card_json = self._build_card(ctx, preview_id)
        markdown = self._build_markdown(ctx)
        self._save(preview_id, card_json, markdown)

        return {
            "preview_id": preview_id,
            "card_title": f"{ctx['period']} 重点事项对账",
            "card_json": card_json,
            "markdown": markdown,
            "dry_run": trigger_context.dry_run,
            "trace_id": trigger_context.trace_id,
        }

    def _build_card(self, ctx: Dict[str, Any], preview_id: str) -> Dict[str, Any]:
        total = ctx["total"]
        done_n = len(ctx["done"])
        rate = f"{int(done_n/total*100)}%" if total else "N/A"

        elements = []
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**📋 {ctx['period']} 重点事项对账**\n"
                    f"项目：{ctx['project_id']}　｜　"
                    f"共 {total} 项，完成率 **{rate}**"
                ),
            },
        })
        elements.append({"tag": "hr"})

        if ctx["overdue"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🔴 逾期未完成**"}})
            for it in ctx["overdue"]:
                owner = f"👤 {it['owner']}" if it["owner"] else ""
                due = f"📅 {it['deadline']}" if it["deadline"] else ""
                meta = "  ".join(filter(None, [owner, due]))
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"❌ {it['content']}\n{meta}" + (f" [📎来源]({it['source_url']})" if it['source_url'] and it['source_url'] != '#' and it['source_url'].startswith('http') else ""),
                    },
                })
            elements.append({"tag": "hr"})

        if ctx["in_progress"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🟡 进行中**"}})
            for it in ctx["in_progress"]:
                owner = f"👤 {it['owner']}" if it["owner"] else ""
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"⏳ {it['content']} {owner}{_src(it['source_url'])}",
                    },
                })
            elements.append({"tag": "hr"})

        if ctx["done"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🟢 已完成**"}})
            for it in ctx["done"]:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"✅ {it['content']}{_src(it['source_url'])}",
                    },
                })
            elements.append({"tag": "hr"})

        if ctx["pending"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**⚪ 待处理**"}})
            for it in ctx["pending"]:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"○ {it['content']}{_src(it['source_url'])}",
                    },
                })

        header_color = "red" if ctx["overdue"] else "orange" if ctx["in_progress"] else "green"
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📋 重点事项对账"},
                "template": header_color,
            },
            "elements": elements,
        }

    def _build_markdown(self, ctx: Dict[str, Any]) -> str:
        total = ctx["total"]
        done_n = len(ctx["done"])
        rate = f"{int(done_n/total*100)}%" if total else "N/A"
        lines = [
            f"# {ctx['period']} 重点事项对账",
            f"- **项目**: {ctx['project_id']}",
            f"- **完成率**: {rate}（{done_n}/{total}）",
            "",
        ]
        if ctx["overdue"]:
            lines.append("## 🔴 逾期未完成")
            for it in ctx["overdue"]:
                lines.append(f"- ❌ {it['content']} [来源]({it['source_url']})")
            lines.append("")
        if ctx["in_progress"]:
            lines.append("## 🟡 进行中")
            for it in ctx["in_progress"]:
                lines.append(f"- ⏳ {it['content']} [来源]({it['source_url']})")
            lines.append("")
        if ctx["done"]:
            lines.append("## 🟢 已完成")
            for it in ctx["done"]:
                lines.append(f"- ✅ {it['content']} [来源]({it['source_url']})")
            lines.append("")
        if ctx["pending"]:
            lines.append("## ⚪ 待处理")
            for it in ctx["pending"]:
                lines.append(f"- ○ {it['content']} [来源]({it['source_url']})")
            lines.append("")
        return "\n".join(lines)

    def _save(self, preview_id: str, card_json: Dict[str, Any], markdown: str):
        (self.output_dir / f"{preview_id}.json").write_text(
            json.dumps(card_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.output_dir / f"{preview_id}.md").write_text(markdown, encoding="utf-8")


key_review_generator = KeyReviewGenerator()
