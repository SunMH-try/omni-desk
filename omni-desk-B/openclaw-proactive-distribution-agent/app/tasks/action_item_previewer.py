import json
from pathlib import Path
from typing import Dict, Any, List
from app.triggers.trigger_engine import TriggerContext

class ActionItemPreviewer:
    def __init__(self):
        self.output_dir = Path(__file__).parent.parent.parent / "outputs" / "cards"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_preview(self, action_items_data: Dict[str, Any], trigger_context: TriggerContext) -> Dict[str, Any]:
        """生成Action Items任务预览，包含缺失字段提醒和重复检测"""
        preview_id = f"preview_task_{trigger_context.trace_id.split('_')[-1]}"
        
        # 适配A端返回结构
        if "action_items" in action_items_data:
            # A端真实返回格式
            action_items = action_items_data["action_items"]
            member_map = action_items_data.get("project_member_map", {})
            # 转换字段
            converted_items = []
            for idx, item in enumerate(action_items, 1):
                converted_item = {
                    "id": item.get("id", f"task_{idx}"),
                    "title": item.get("content", item.get("title", "待完成任务")),
                    "owner": item.get("assignee", item.get("owner")),
                    "deadline": item.get("due_date", item.get("deadline")),
                    "priority": item.get("priority", "medium"),
                    "missing_fields": [],
                    "evidence_id": item.get("evidence_id", ""),
                    "source_url": item.get("source_url", "#"),
                    "confidence": item.get("confidence", 0.8)
                }
                # 检查缺失字段
                if not converted_item["owner"]:
                    converted_item["missing_fields"].append("owner")
                if not converted_item["deadline"]:
                    converted_item["missing_fields"].append("deadline")
                converted_items.append(converted_item)
            action_items = converted_items
        else:
            # Mock格式
            action_items = action_items_data["action_item_list"]
            member_map = action_items_data["project_member_map"]
        
        # 处理每个Action Item，检查缺失字段
        processed_items = []
        missing_fields_count = 0
        duplicate_warnings = []
        
        # 检测重复任务（简单判断标题相似度）
        task_titles = []
        for item in action_items:
            processed_item = item.copy()
            processed_item["owner_name"] = member_map.get(item["owner"], "待分配") if item["owner"] else "待分配"
            
            # 检查缺失字段
            if item.get("missing_fields"):
                missing_fields_count += len(item["missing_fields"])
                processed_item["needs_confirmation"] = True
            else:
                processed_item["needs_confirmation"] = False
            
            # 检测重复
            if item["title"] in task_titles:
                duplicate_warnings.append(f"检测到重复任务：{item['title']}")
            task_titles.append(item["title"])
            
            processed_items.append(processed_item)
        
        # 生成预览卡片
        preview_card = self._build_preview_card(processed_items, preview_id, missing_fields_count, duplicate_warnings)
        
        # 生成Markdown预览
        markdown = self._build_markdown_preview(processed_items, missing_fields_count, duplicate_warnings)
        
        # 保存到文件
        self._save_to_file(preview_id, preview_card, markdown, processed_items)
        
        return {
            "preview_id": preview_id,
            "processed_items": processed_items,
            "missing_fields_count": missing_fields_count,
            "duplicate_warnings": duplicate_warnings,
            "preview_card": preview_card,
            "markdown": markdown,
            "requires_confirmation": missing_fields_count > 0 or len(duplicate_warnings) > 0,
            "dry_run": trigger_context.dry_run,
            "trace_id": trigger_context.trace_id
        }

    def _build_preview_card(self, items: List[Dict[str, Any]], preview_id: str, missing_count: int, duplicates: List[str]) -> Dict[str, Any]:
        """构建任务预览飞书卡片"""
        elements = []
        
        # 头部
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📋 会议Action Items预览**\n共抽取到 {len(items)} 个待办任务"
            }
        })
        
        if missing_count > 0:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⚠️ 有 {missing_count} 个字段需要补充，请确认后再创建"
                }
            })
        
        if duplicates:
            for warn in duplicates:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"⚠️ {warn}"
                    }
                })
        
        elements.append({"tag": "hr"})
        
        # 任务列表
        for idx, item in enumerate(items, 1):
            priority_icon = "🔴" if item["priority"] == "high" else "🟠" if item["priority"] == "medium" else "🟢"
            status_tag = "⚠️ 需要确认" if item["needs_confirmation"] else "✅ 信息完整"
            confidence = f"置信度: {int(item['confidence'] * 100)}%"
            
            src = item['source_url']
            src_link = f" [📎来源]({src})" if src and src != "#" and src.startswith("http") else ""
            line_content = f"{priority_icon} {idx}. **{item['title']}**\n"
            line_content += f"👤 负责人: {item['owner_name']} | 📅 截止时间: {item.get('deadline', '未设置')}\n"
            line_content += f"ℹ️ {confidence} | {status_tag}{src_link}"
            
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": line_content
                }
            })
            
            if item.get("missing_fields"):
                missing_text = "缺失字段: " + ", ".join(item["missing_fields"])
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"<font color='red'>  ❌ {missing_text}</font>"
                    }
                })
            
            elements.append({"tag": "hr"})
        
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "_确认无误后，发送 @OpenClaw 确认创建 即可将任务同步到飞书任务_",
            },
        })
        
        return {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📋 会议待办任务预览"
                },
                "template": "green" if missing_count == 0 else "orange"
            },
            "elements": elements
        }

    def _build_markdown_preview(self, items: List[Dict[str, Any]], missing_count: int, duplicates: List[str]) -> str:
        """构建Markdown格式的任务预览"""
        md_lines = []
        md_lines.append("# 会议Action Items预览")
        md_lines.append(f"- 共抽取到 **{len(items)}** 个待办任务")
        if missing_count > 0:
            md_lines.append(f"- ⚠️ 有 **{missing_count}** 个字段需要补充")
        if duplicates:
            for warn in duplicates:
                md_lines.append(f"- ⚠️ {warn}")
        md_lines.append("")

        for idx, item in enumerate(items, 1):
            priority = "高" if item["priority"] == "high" else "中" if item["priority"] == "medium" else "低"
            status = "需要确认" if item["needs_confirmation"] else "信息完整"
            
            md_lines.append(f"## {idx}. {item['title']}")
            md_lines.append(f"- **优先级**: {priority}")
            md_lines.append(f"- **负责人**: {item['owner_name']}")
            md_lines.append(f"- **截止时间**: {item.get('deadline', '未设置')}")
            md_lines.append(f"- **置信度**: {int(item['confidence'] * 100)}%")
            md_lines.append(f"- **状态**: {status}")
            md_lines.append(f"- **来源**: [会议纪要]({item['source_url']})")
            
            if item.get("missing_fields"):
                md_lines.append(f"- **缺失字段**: {', '.join(item['missing_fields'])}")
            
            md_lines.append("")

        return "\n".join(md_lines)

    def _save_to_file(self, preview_id: str, card_json: Dict[str, Any], markdown: str, items: List[Dict[str, Any]]):
        """保存预览到文件"""
        # 保存卡片JSON
        json_path = self.output_dir / f"{preview_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(card_json, f, ensure_ascii=False, indent=2)
        
        # 保存Markdown
        md_path = self.output_dir / f"{preview_id}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        
        # 保存任务数据
        data_path = self.output_dir / f"{preview_id}_items.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

# 全局预览器实例
action_item_previewer = ActionItemPreviewer()
