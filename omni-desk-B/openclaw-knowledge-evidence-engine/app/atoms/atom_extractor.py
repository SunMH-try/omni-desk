"""A05 — Knowledge atom extractor."""
import json
import uuid
from app import llm_client
from app.indexing.page_index_builder import PageIndex, PageNode
from app.models import KnowledgeAtom


_ATOM_PROMPT = """你是一个知识原子抽取助手。请从以下文本中抽取结构化知识原子，返回 JSON 数组。

每个原子格式：
{
  "atom_type": "Fact|Decision|ActionItem|Risk|Blocker|Change|Question|Insight",
  "summary": "一句话概括（不超过80字）",
  "owner_candidates": ["负责人ID，没有则空列表"],
  "deadline": "YYYY-MM-DD 或 null",
  "confidence": 0.0-1.0,
  "risk_level": "high|medium|low 仅 Risk/Blocker 类型填写，否则 null",
  "risk_reason": "风险原因，仅 Risk/Blocker 类型填写，否则 null"
}

规则：
- 只抽取文本中明确存在的信息，不推测
- ActionItem 必须有可识别的动作
- Risk 必须有风险原因和等级
- 每个原子必须有 confidence >= 0.5 才保留

只返回 JSON 数组，不要额外说明。
"""


def extract_atoms(index: PageIndex, source_id: str) -> tuple[list[KnowledgeAtom], list[dict]]:
    """Extract knowledge atoms from a PageIndex. Returns (atoms, usage_traces)."""
    usage_traces = []
    all_atoms = []
    evidence_counter = [0]

    def _process_node(node: PageNode):
        if node.chunk is None:
            for child in node.children:
                _process_node(child)
            return

        raw_atoms, usage = _call_llm(node.chunk, node.node_id)
        usage_traces.append(usage)
        for raw in raw_atoms:
            evidence_counter[0] += 1
            ev_id = f"ev_{source_id}_{evidence_counter[0]:04d}"
            atom = KnowledgeAtom(
                atom_id=f"atom_{uuid.uuid4().hex[:8]}",
                atom_type=raw.get("atom_type", "Fact"),
                summary=raw.get("summary", ""),
                source_id=source_id,
                evidence_ids=[ev_id],
                confidence=float(raw.get("confidence", 0.7)),
                owner_candidates=raw.get("owner_candidates", []),
                deadline=raw.get("deadline"),
                risk_level=raw.get("risk_level"),
                risk_reason=raw.get("risk_reason"),
            )
            if atom.confidence >= 0.5 and atom.summary:
                all_atoms.append(atom)

    _process_node(index.root)
    return all_atoms, usage_traces


def _call_llm(text: str, prompt_name: str) -> tuple[list[dict], dict]:
    messages = [
        {"role": "system", "content": _ATOM_PROMPT},
        {"role": "user", "content": text},
    ]
    try:
        result, usage = llm_client.chat_json(messages, prompt_name=f"atom_extract_{prompt_name}")
        if isinstance(result, list):
            return result, usage
        return [], usage
    except Exception as e:
        return [], {"error": str(e), "prompt_name": prompt_name}


def atoms_to_dict(atoms: list[KnowledgeAtom]) -> list[dict]:
    return [
        {
            "atom_id": a.atom_id,
            "atom_type": a.atom_type,
            "summary": a.summary,
            "source_id": a.source_id,
            "evidence_ids": a.evidence_ids,
            "confidence": a.confidence,
            "owner_candidates": a.owner_candidates,
            "deadline": a.deadline,
            "risk_level": a.risk_level,
            "risk_reason": a.risk_reason,
        }
        for a in atoms
    ]
