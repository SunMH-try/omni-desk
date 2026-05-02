"""A10 — Action item extractor & field completer."""
from __future__ import annotations
import json
import uuid
from app import llm_client
from app.ingestion.document_parser import ParsedMinutes, ParsedMessages
from app.models import ActionItem


_EXTRACT_PROMPT = """你是一个待办事项抽取助手。从以下文本（会议纪要或群聊）中识别所有待办事项。
对每条待办补齐：负责人（owner）、截止时间（deadline，YYYY-MM-DD）、优先级（high/medium/low）、置信度（0-1）。

返回 JSON 数组，每项格式：
{
  "title": "待办标题",
  "owner": "负责人ID 或 null（需确认）",
  "deadline": "YYYY-MM-DD 或 null",
  "priority": "high|medium|low",
  "confidence": 0.0-1.0,
  "needs_confirmation": true/false
}

规则：
- 如果负责人不明确，owner 为 null，needs_confirmation 为 true
- Action Item Precision 目标 >= 85%，只抽取真实的行动项
- 相似任务提示 is_duplicate_candidate

只返回 JSON 数组。
"""


def extract(
    source_id: str,
    source_url: str,
    parsed,
    owner_dict: dict | None = None,
) -> tuple[list[ActionItem], list[dict], list[dict]]:
    """Extract action items from minutes or messages.

    Returns (action_items, missing_field_report, usage_traces).
    """
    if isinstance(parsed, ParsedMinutes):
        text = _minutes_to_text(parsed)
        # Use raw action items as ground truth hints
        raw_hints = parsed.action_items_raw
    elif isinstance(parsed, ParsedMessages):
        text = _messages_to_text(parsed)
        raw_hints = []
    else:
        return [], [], []

    messages = [
        {"role": "system", "content": _EXTRACT_PROMPT},
        {"role": "user", "content": text},
    ]
    try:
        raw_items, usage = llm_client.chat_json(messages, prompt_name=f"action_items_{source_id}")
    except Exception as e:
        # Fallback: use raw hints if available
        raw_items = [
            {"title": h["content"], "owner": h.get("assignee"), "deadline": h.get("deadline"),
             "priority": "medium", "confidence": 0.85, "needs_confirmation": not h.get("assignee")}
            for h in raw_hints
        ]
        usage = {"error": str(e)}

    items = []
    missing = []
    counter = [0]

    for raw in raw_items:
        counter[0] += 1
        item_id = f"ai_{source_id}_{counter[0]:03d}"
        ev_id = f"ev_ai_{source_id}_{counter[0]:03d}"

        owner = raw.get("owner")
        if owner and owner_dict:
            owner = owner_dict.get(owner, owner)

        deadline = raw.get("deadline")
        # 从 fixture raw_hints 补全缺失的 deadline
        if not deadline and raw_hints:
            hint = _match_hint(raw.get("title", ""), raw_hints)
            if hint:
                deadline = hint.get("deadline")
                owner = owner or hint.get("assignee")

        item = ActionItem(
            item_id=item_id,
            title=raw.get("title", ""),
            evidence_id=ev_id,
            confidence=float(raw.get("confidence", 0.8)),
            owner=owner,
            deadline=deadline,
            priority=raw.get("priority", "medium"),
            source_url=source_url,
            needs_confirmation=raw.get("needs_confirmation", owner is None),
        )
        items.append(item)

        missing_fields = []
        if not item.owner:
            missing_fields.append("owner")
        if not item.deadline:
            missing_fields.append("deadline")
        if missing_fields:
            missing.append({"item_id": item_id, "title": item.title, "missing": missing_fields})

    # Duplicate detection
    titles = [i.title for i in items]
    duplicates = []
    for i in range(len(titles)):
        for j in range(i+1, len(titles)):
            if _similar(titles[i], titles[j]):
                duplicates.append({"a": items[i].item_id, "b": items[j].item_id,
                                   "note": "可能重复，请确认"})

    return items, missing + duplicates, [usage]


def _minutes_to_text(m: ParsedMinutes) -> str:
    lines = [f"会议纪要：{m.title}", f"时间：{m.start_time} - {m.end_time}"]
    for t in m.transcript:
        lines.append(f"{t['speaker']}: {t['text']}")
    for d in m.decisions:
        lines.append(f"决议: {d['content']}")
    return "\n".join(lines)


def _messages_to_text(m: ParsedMessages) -> str:
    return "\n".join(f"{msg['sender']}: {msg['text']}" for msg in m.messages)


def _match_hint(title: str, hints: list[dict]) -> dict | None:
    """Find the best matching raw hint for a given title."""
    best, best_score = None, 0.0
    for hint in hints:
        score = _overlap(title, hint.get("content", ""))
        if score > best_score and score > 0.3:
            best, best_score = hint, score
    return best


def _overlap(a: str, b: str) -> float:
    a_set = set(a.replace(" ", ""))
    b_set = set(b.replace(" ", ""))
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def _similar(a: str, b: str) -> bool:
    a_tokens = set(a)
    b_tokens = set(b)
    if not a_tokens or not b_tokens:
        return False
    overlap = len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))
    return overlap > 0.6


def items_to_dict(items: list[ActionItem]) -> list[dict]:
    return [
        {
            "item_id": i.item_id,
            "title": i.title,
            "owner": i.owner,
            "deadline": i.deadline,
            "priority": i.priority,
            "evidence_id": i.evidence_id,
            "confidence": i.confidence,
            "source_url": i.source_url,
            "needs_confirmation": i.needs_confirmation,
        }
        for i in items
    ]
