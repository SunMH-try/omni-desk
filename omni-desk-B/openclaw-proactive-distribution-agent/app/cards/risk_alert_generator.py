from __future__ import annotations
import json
from datetime import date
from pathlib import Path
from typing import Dict, Any, List
from app.triggers.trigger_engine import TriggerContext


class RiskAlertGenerator:
    def __init__(self):
        self.output_dir = Path(__file__).parent.parent.parent / "outputs" / "cards"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, risk_data: Dict[str, Any], trigger_context: TriggerContext) -> Dict[str, Any]:
        preview_id = f"preview_risk_{trigger_context.trace_id.split('_')[-1]}"

        risk_atoms = self._extract_atoms(risk_data)

        risk_count = len(risk_atoms)
        if risk_count >= 5:
            risk_score, risk_level = 85, "high"
        elif risk_count >= 3:
            risk_score, risk_level = 70, "medium"
        elif risk_count >= 1:
            risk_score, risk_level = 55, "low"
        else:
            risk_score, risk_level = 20, "none"

        adapted = {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_atoms": risk_atoms,
        }

        card_json = self._build_feishu_card(adapted, preview_id)
        markdown = self._build_markdown(adapted)
        self._save_to_file(preview_id, card_json, markdown)

        return {
            "preview_id": preview_id,
            "card_title": f"风险预警：{risk_count} 项风险，评分 {risk_score}",
            "card_json": card_json,
            "markdown": markdown,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "dry_run": trigger_context.dry_run,
            "trace_id": trigger_context.trace_id,
        }

    def _extract_atoms(self, risk_data: Dict[str, Any]) -> List[Dict]:
        """适配 A 端 /evidence/v1/query 的真实返回格式。"""
        atoms: List[Dict] = []
        today = date.today().isoformat()

        # A 端真实格式: { "verified_evidence": [...] }
        for ev in risk_data.get("verified_evidence", []):
            atoms.append({
                "id": ev.get("evidence_id", f"ev_{len(atoms)}"),
                "content": ev.get("summary", ""),
                "count": 1,
                "first_mentioned_at": today,
                "source_url": ev.get("source_url", "#") or "#",
            })

        # 兼容旧格式
        if not atoms:
            for idx, item in enumerate(risk_data.get("risk_items", []), 1):
                atoms.append({
                    "id": f"risk_{idx}",
                    "content": item.get("content", str(item)),
                    "count": item.get("mention_count", 1),
                    "first_mentioned_at": item.get("first_mentioned_at", today),
                    "source_url": item.get("source_url", "#") or "#",
                })

        # 兼容纯文本 response 格式
        if not atoms and ("response" in risk_data or "answer" in risk_data):
            text = risk_data.get("response") or risk_data.get("answer", "")
            for idx, line in enumerate(str(text).splitlines(), 1):
                line = line.strip()
                if line:
                    atoms.append({
                        "id": f"risk_{idx}",
                        "content": line,
                        "count": 1,
                        "first_mentioned_at": today,
                        "source_url": "#",
                    })

        return atoms

    def _build_feishu_card(self, data: Dict[str, Any], preview_id: str) -> Dict[str, Any]:
        level = data["risk_level"]
        level_icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(level, "🟢")
        template = {"high": "red", "medium": "orange", "low": "yellow"}.get(level, "green")
        level_text = {"high": "高风险", "medium": "中风险", "low": "低风险", "none": "无明显风险"}.get(level, level)

        elements = []
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**{level_icon} 项目风险预警**\n"
                    f"风险评分：{data['risk_score']}/100　风险等级：{level_text}\n"
                    f"共发现 {len(data['risk_atoms'])} 项风险信号"
                ),
            },
        })
        elements.append({"tag": "hr"})

        if data["risk_atoms"]:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**⚠️ 风险明细**"}})
            for i, atom in enumerate(data["risk_atoms"], 1):
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"{i}. {atom['content']}\n"
                            f"   📅 首次发现：{atom['first_mentioned_at'][:10]}"
                            + (f"　[📎来源]({atom['source_url']})" if atom['source_url'] and atom['source_url'] != '#' and atom['source_url'].startswith('http') else "")
                        ),
                    },
                })
            elements.append({"tag": "hr"})
        else:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "✅ 未发现明显风险信号"},
            })

        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "_如需追踪任务完成情况，发送 @OpenClaw 对账_",
            },
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{level_icon} 项目风险预警"},
                "template": template,
            },
            "elements": elements,
        }

    def _build_markdown(self, data: Dict[str, Any]) -> str:
        level_text = {"high": "高风险", "medium": "中风险", "low": "低风险", "none": "无明显风险"}.get(
            data["risk_level"], data["risk_level"]
        )
        lines = [
            "# 项目风险预警",
            f"- **风险评分**: {data['risk_score']}/100",
            f"- **风险等级**: {level_text}",
            "",
        ]
        if data["risk_atoms"]:
            lines.append("## ⚠️ 风险明细")
            for i, atom in enumerate(data["risk_atoms"], 1):
                lines.append(f"{i}. {atom['content']}")
                lines.append(f"   - 首次发现: {atom['first_mentioned_at'][:10]}")
                lines.append(f"   - 来源: [证据链接]({atom['source_url']})")
            lines.append("")
        else:
            lines.append("✅ 未发现明显风险信号")
        return "\n".join(lines)

    def _save_to_file(self, preview_id: str, card_json: Dict[str, Any], markdown: str):
        (self.output_dir / f"{preview_id}.json").write_text(
            json.dumps(card_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.output_dir / f"{preview_id}.md").write_text(markdown, encoding="utf-8")


risk_alert_generator = RiskAlertGenerator()
