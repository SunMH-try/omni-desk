from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional


SourceType = Literal["docs", "minutes", "messages", "tasks", "calendar", "bitable"]
AtomType = Literal["Fact", "Decision", "ActionItem", "Risk", "Blocker", "Change", "Question", "Insight"]
SupportLevel = Literal["high", "medium", "low", "unverified"]


@dataclass
class KnowledgeSource:
    source_id: str
    source_type: SourceType
    title: str
    url: str
    tenant_id: str
    project_id: str
    permission_scope: list[str]
    updated_at: str
    content: dict  # raw parsed content


@dataclass
class KnowledgeAtom:
    atom_id: str
    atom_type: AtomType
    summary: str
    source_id: str
    evidence_ids: list[str]
    confidence: float
    owner_candidates: list[str] = field(default_factory=list)
    deadline: Optional[str] = None
    risk_level: Optional[str] = None
    risk_reason: Optional[str] = None


@dataclass
class Evidence:
    evidence_id: str
    summary: str
    source_id: str
    source_type: SourceType
    source_url: str
    chunk_text: str
    timestamp: str
    support_level: SupportLevel = "unverified"
    confidence: float = 0.0
    is_stale: bool = False


@dataclass
class ActionItem:
    item_id: str
    title: str
    evidence_id: str
    confidence: float
    owner: Optional[str] = None
    deadline: Optional[str] = None
    priority: Optional[str] = None
    source_url: Optional[str] = None
    needs_confirmation: bool = False
