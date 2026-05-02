import json
from pathlib import Path
from typing import Dict, Any
from app.triggers.trigger_engine import TriggerContext

class WeeklyCardGenerator:
    def __init__(self):
        self.output_dir = Path(__file__).parent.parent.parent / "outputs" / "cards"
        self.report_dir = Path(__file__).parent.parent.parent / "outputs" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, weekly_material: Dict[str, Any], trigger_context: TriggerContext) -> Dict[str, Any]:
        """生成周报洞察卡片和完整飞书文档"""
        preview_id = f"preview_weekly_{trigger_context.trace_id.split('_')[-1]}"
        
        # 适配A端返回结构
        week_start = weekly_material.get("week_start", "")
        week_end = weekly_material.get("week_end", "")
        week_range = f"{week_start} 至 {week_end}" if week_start and week_end else "本周"
        adapted_material = {
            "week_range": week_range,
            "project_id": trigger_context.project_id,
            "weekly_progress": [],
            "delayed_tasks": [],
            "risk_warnings": [],
            "next_week_plan": []
        }

        # evidence_id -> source_url 映射（A端新增字段）
        evidence_sources: dict = weekly_material.get("evidence_sources", {})
        evidence_ids: list = weekly_material.get("evidence_ids", [])

        def _url(idx: int) -> str:
            """按顺序取第 idx 条 evidence 的 source_url，找不到返回 '#'"""
            if idx < len(evidence_ids):
                eid = evidence_ids[idx]
                url = evidence_sources.get(eid, "")
                return url if url else "#"
            return "#"

        # 转换A端返回的内容
        if "progress_summary" in weekly_material and weekly_material["progress_summary"] != "待确认":
            adapted_material["weekly_progress"].append({
                "id": "progress_1",
                "content": weekly_material["progress_summary"],
                "source_url": _url(0)
            })

        if "risk_summary" in weekly_material and weekly_material["risk_summary"] != "待确认":
            adapted_material["risk_warnings"].append({
                "id": "risk_1",
                "content": weekly_material["risk_summary"],
                "level": "high" if "风险" in weekly_material["risk_summary"] or "延期" in weekly_material["risk_summary"] else "medium",
                "source_url": _url(1)
            })

        # 转换key_insights
        if "key_insights" in weekly_material:
            for idx, insight in enumerate(weekly_material["key_insights"], 1):
                adapted_material["weekly_progress"].append({
                    "id": f"insight_{idx}",
                    "content": insight if isinstance(insight, str) else insight.get("content", str(insight)),
                    "source_url": _url(idx + 1)
                })
        
        # 生成飞书卡片JSON
        card_json = self._build_feishu_card(adapted_material, preview_id)
        
        # 生成Markdown预览和完整报告
        markdown_preview = self._build_markdown_preview(adapted_material)
        full_report = self._build_full_report(adapted_material)
        
        # 保存到文件
        self._save_to_file(preview_id, card_json, markdown_preview, full_report)
        
        return {
            "preview_id": preview_id,
            "card_title": f"{adapted_material['week_range']} 项目周报洞察",
            "card_json": card_json,
            "markdown": markdown_preview,
            "full_report": full_report,
            "dry_run": trigger_context.dry_run,
            "trace_id": trigger_context.trace_id
        }

    def _build_feishu_card(self, weekly_material: Dict[str, Any], preview_id: str) -> Dict[str, Any]:
        """构建周报飞书卡片"""
        elements = []
        
        # 头部
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📊 {weekly_material['week_range']} 项目周报洞察**\n项目: {weekly_material['project_id']}"
            }
        })
        
        elements.append({"tag": "hr"})
        
        # 本周进展
        if weekly_material.get("weekly_progress"):
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**✅ 本周进展**"
                }
            })
            for idx, item in enumerate(weekly_material["weekly_progress"], 1):
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{idx}. {item['content']} [来源]({item['source_url']})"
                    }
                })
            elements.append({"tag": "hr"})
        
        # 延期任务
        if weekly_material.get("delayed_tasks"):
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**⚠️ 延期任务**"
                }
            })
            for idx, task in enumerate(weekly_material["delayed_tasks"], 1):
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{idx}. {task['title']}\n👤 {task['owner']} | 📅 延期 {task['delay_days']} 天 [来源]({task['source_url']})"
                    }
                })
            elements.append({"tag": "hr"})
        
        # 风险总结
        if weekly_material.get("risk_summary"):
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**🚨 风险提醒**"
                }
            })
            for idx, risk in enumerate(weekly_material["risk_summary"], 1):
                level_color = "red" if risk["level"] == "high" else "orange"
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{idx}. <font color='{level_color}'>{risk['content']}</font> [来源]({risk['source_url']})"
                    }
                })
            elements.append({"tag": "hr"})
        
        # 下周重点
        if weekly_material.get("next_week_focus"):
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**🎯 下周重点**"
                }
            })
            for idx, item in enumerate(weekly_material["next_week_focus"], 1):
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{idx}. {item['content']} [来源]({item['source_url']})"
                    }
                })
        
        
        return {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📊 项目周报洞察"
                },
                "template": "purple"
            },
            "elements": elements
        }

    def _build_markdown_preview(self, weekly_material: Dict[str, Any]) -> str:
        """构建Markdown预览"""
        md_lines = []
        md_lines.append(f"# {weekly_material['week_range']} 项目周报洞察")
        md_lines.append(f"- **项目**: {weekly_material['project_id']}")
        md_lines.append("")

        # 本周进展
        if weekly_material.get("weekly_progress"):
            md_lines.append("## ✅ 本周进展")
            for idx, item in enumerate(weekly_material["weekly_progress"], 1):
                md_lines.append(f"{idx}. {item['content']} [来源]({item['source_url']})")
            md_lines.append("")

        # 延期任务
        if weekly_material.get("delayed_tasks"):
            md_lines.append("## ⚠️ 延期任务")
            for idx, task in enumerate(weekly_material["delayed_tasks"], 1):
                md_lines.append(f"{idx}. **{task['title']}**")
                md_lines.append(f"  - 负责人: {task['owner']}")
                md_lines.append(f"  - 延期: {task['delay_days']}天")
                md_lines.append(f"  - 来源: [飞书任务]({task['source_url']})")
            md_lines.append("")

        # 风险总结
        if weekly_material.get("risk_summary"):
            md_lines.append("## 🚨 风险提醒")
            for idx, risk in enumerate(weekly_material["risk_summary"], 1):
                level = "高风险" if risk["level"] == "high" else "中风险"
                md_lines.append(f"{idx}. **{level}**: {risk['content']}")
                md_lines.append(f"  - 来源: [飞书群聊]({risk['source_url']})")
            md_lines.append("")

        # 下周重点
        if weekly_material.get("next_week_focus"):
            md_lines.append("## 🎯 下周重点")
            for idx, item in enumerate(weekly_material["next_week_focus"], 1):
                md_lines.append(f"{idx}. {item['content']} [来源]({item['source_url']})")
            md_lines.append("")

        return "\n".join(md_lines)

    def _build_full_report(self, weekly_material: Dict[str, Any]) -> str:
        """构建完整的周报报告"""
        md_lines = []
        md_lines.append(f"# {weekly_material['week_range']} {weekly_material['project_id']} 项目周报")
        md_lines.append("")
        md_lines.append("## 一、本周整体进展")
        md_lines.append("")
        
        # 进展部分
        if weekly_material.get("weekly_progress"):
            md_lines.append("### 1.1 完成事项")
            for idx, item in enumerate(weekly_material["weekly_progress"], 1):
                md_lines.append(f"{idx}. {item['content']}")
                md_lines.append(f"  - 证据来源: [{item.get('evidence_id', item.get('id', ''))}]({item['source_url']})")
            md_lines.append("")
        
        # 延期任务
        if weekly_material.get("delayed_tasks"):
            md_lines.append("### 1.2 延期任务")
            for idx, task in enumerate(weekly_material["delayed_tasks"], 1):
                md_lines.append(f"{idx}. {task['title']}")
                md_lines.append(f"  - 负责人: {task['owner']}")
                md_lines.append(f"  - 原截止日期: {task['deadline']}")
                md_lines.append(f"  - 延期天数: {task['delay_days']}天")
                md_lines.append(f"  - 证据来源: [{task['evidence_id']}]({task['source_url']})")
            md_lines.append("")
        
        # 风险部分
        if weekly_material.get("risk_summary"):
            md_lines.append("## 二、风险与问题")
            for idx, risk in enumerate(weekly_material["risk_summary"], 1):
                level = "高" if risk["level"] == "high" else "中"
                md_lines.append(f"### 2.{idx} 风险{idx} (优先级: {level})")
                md_lines.append(f"- 风险描述: {risk['content']}")
                md_lines.append(f"- 证据来源: [{risk['evidence_id']}]({risk['source_url']})")
                md_lines.append(f"- 建议处理方案: 请相关负责人尽快跟进处理")
            md_lines.append("")
        
        # 下周计划
        if weekly_material.get("next_week_focus"):
            md_lines.append("## 三、下周工作计划")
            for idx, item in enumerate(weekly_material["next_week_focus"], 1):
                md_lines.append(f"{idx}. {item['content']}")
                md_lines.append(f"  - 证据来源: [{item.get('evidence_id', item.get('id', ''))}]({item['source_url']})")
            md_lines.append("")
        
        md_lines.append("## 四、证据清单")
        md_lines.append("所有结论均来自以下证据：")
        for eid in weekly_material.get("evidence_ids", []):
            md_lines.append(f"- {eid}")
        
        return "\n".join(md_lines)

    def _save_to_file(self, preview_id: str, card_json: Dict[str, Any], markdown: str, full_report: str):
        """保存卡片和报告到文件"""
        # 保存卡片JSON
        json_path = self.output_dir / f"{preview_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(card_json, f, ensure_ascii=False, indent=2)
        
        # 保存Markdown预览
        md_path = self.output_dir / f"{preview_id}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        
        # 保存完整报告
        report_path = self.report_dir / f"{preview_id}_full_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(full_report)

# 全局生成器实例
weekly_card_generator = WeeklyCardGenerator()
