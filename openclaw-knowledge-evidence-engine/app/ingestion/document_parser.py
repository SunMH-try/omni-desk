"""A03 — Office document & meeting parser."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedDocument:
    source_id: str
    source_type: str
    title: str
    url: str
    updated_at: str
    sections: list[dict] = field(default_factory=list)   # {heading, level, content}
    comments: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedMinutes:
    source_id: str
    title: str
    url: str
    updated_at: str
    meeting_id: str
    attendees: list[str]
    start_time: str
    end_time: str
    agenda: list[str]
    transcript: list[dict]   # {speaker, timestamp, text}
    decisions: list[dict]    # {decision_id, content, confirmed_by, timestamp}
    action_items_raw: list[dict]


@dataclass
class ParsedMessages:
    source_id: str
    url: str
    updated_at: str
    messages: list[dict]  # {msg_id, sender, timestamp, text}


@dataclass
class ParsedTasks:
    source_id: str
    url: str
    updated_at: str
    tasks: list[dict]


def parse(raw: dict) -> Any:
    """Dispatch to the right parser based on source_type."""
    stype = raw.get("source_type")
    if stype == "docs":
        return _parse_doc(raw)
    if stype == "minutes":
        return _parse_minutes(raw)
    if stype == "messages":
        return _parse_messages(raw)
    if stype == "tasks":
        return _parse_tasks(raw)
    raise ValueError(f"Unsupported source_type: {stype}")


def _parse_doc(raw: dict) -> ParsedDocument:
    return ParsedDocument(
        source_id=raw["source_id"],
        source_type=raw["source_type"],
        title=raw.get("title", ""),
        url=raw.get("url", ""),
        updated_at=raw.get("updated_at", ""),
        sections=raw.get("sections", []),
        comments=raw.get("comments", []),
        metadata={
            "tenant_id": raw.get("tenant_id"),
            "project_id": raw.get("project_id"),
            "permission_scope": raw.get("permission_scope", []),
        },
    )


def _parse_minutes(raw: dict) -> ParsedMinutes:
    return ParsedMinutes(
        source_id=raw["source_id"],
        title=raw.get("title", ""),
        url=raw.get("url", ""),
        updated_at=raw.get("updated_at", ""),
        meeting_id=raw.get("meeting_id", ""),
        attendees=raw.get("attendees", []),
        start_time=raw.get("start_time", ""),
        end_time=raw.get("end_time", ""),
        agenda=raw.get("agenda", []),
        transcript=raw.get("transcript", []),
        decisions=raw.get("decisions", []),
        action_items_raw=raw.get("action_items_raw", []),
    )


def _parse_messages(raw: dict) -> ParsedMessages:
    return ParsedMessages(
        source_id=raw["source_id"],
        url=raw.get("url", ""),
        updated_at=raw.get("updated_at", ""),
        messages=raw.get("messages", []),
    )


def _parse_tasks(raw: dict) -> ParsedTasks:
    return ParsedTasks(
        source_id=raw["source_id"],
        url=raw.get("url", ""),
        updated_at=raw.get("updated_at", ""),
        tasks=raw.get("tasks", []),
    )


def full_text(parsed: Any) -> str:
    """Flatten any parsed object to plain text for indexing."""
    if isinstance(parsed, ParsedDocument):
        parts = [parsed.title]
        for s in parsed.sections:
            parts.append(s.get("heading", ""))
            parts.append(s.get("content", ""))
        for c in parsed.comments:
            parts.append(c.get("content", ""))
        return "\n".join(parts)

    if isinstance(parsed, ParsedMinutes):
        parts = [parsed.title] + parsed.agenda
        for t in parsed.transcript:
            parts.append(f"{t['speaker']}: {t['text']}")
        for d in parsed.decisions:
            parts.append(f"决议: {d['content']}")
        for a in parsed.action_items_raw:
            parts.append(f"待办: {a['content']} 负责人:{a.get('assignee','')} 截止:{a.get('deadline','')}")
        return "\n".join(parts)

    if isinstance(parsed, ParsedMessages):
        return "\n".join(f"{m['sender']}: {m['text']}" for m in parsed.messages)

    if isinstance(parsed, ParsedTasks):
        parts = []
        for t in parsed.tasks:
            parts.append(f"任务:{t['title']} 负责人:{t.get('assignee','')} 状态:{t.get('status','')} 截止:{t.get('deadline','')}")
            for c in t.get("comments", []):
                parts.append(f"  评论: {c.get('text','')}")
        return "\n".join(parts)

    return str(parsed)
