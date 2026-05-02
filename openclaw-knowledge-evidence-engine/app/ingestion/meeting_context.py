"""A09 — Pre-meeting context package generator."""
from __future__ import annotations
import json
from app import llm_client
from app.models import Evidence, KnowledgeAtom
from app.retrieval import evidence_retriever, evidence_quality_judge
from app.graph.evidence_graph import EvidenceGraph
from app.indexing.page_index_builder import PageIndex


_CONTEXT_PROMPT = """你是一个会议准备助手。根据以下证据，生成会议前背景包，包含：
1. background_facts: 3-5条高密度背景事实（每条不超过60字）
2. last_decisions: 最近关键决议列表（每条不超过60字）
3. open_risks: 未关闭风险列表（每条必须包含具体风险原因，不超过80字）
4. pending_questions: 待确认问题列表

要求：
- 每条内容必须有对应证据支持
- open_risks 必须描述具体的风险事项，不能只说"存在风险"
- 没有证据支持的内容只能标记为"待确认"
- 输出 JSON 格式：{"background_facts":[],"last_decisions":[],"open_risks":[],"pending_questions":[]}
只返回 JSON，不要额外说明。
"""


def generate(
    meeting_id: str,
    graph: EvidenceGraph,
    indexes: list[PageIndex],
    atoms: list[KnowledgeAtom],
    lookback_days: int = 14,
    include_unfinished_tasks: bool = True,
    vector_index=None,
) -> dict:
    """Generate pre-meeting context package."""
    query = f"会议 {meeting_id} 需要关注哪些背景、风险、决议和待办？"

    evidence_list, retrieval_trace = evidence_retriever.retrieve(
        query=query,
        graph=graph,
        indexes=indexes,
        atoms=atoms,
        top_k=10,
        vector_index=vector_index,
    )

    verified, conflicts, judge_traces = evidence_quality_judge.judge(query, evidence_list)

    # 直接注入 Risk/Blocker 原子，确保 Open Risks 有具体内容
    risk_atoms = [a for a in atoms if a.atom_type in ("Risk", "Blocker")]
    risk_lines = [
        f"[RISK][{a.atom_id}] {a.summary}"
        + (f"（原因：{a.risk_reason}）" if a.risk_reason else "")
        + (f"[{a.evidence_ids[0]}]" if a.evidence_ids else "")
        for a in risk_atoms
    ]

    evidence_text = "\n".join(
        f"[{ev.evidence_id}] ({ev.source_type}) {ev.summary}" for ev in verified
    )
    if risk_lines:
        evidence_text += "\n\n【已识别风险原子】\n" + "\n".join(risk_lines)

    messages = [
        {"role": "system", "content": _CONTEXT_PROMPT},
        {"role": "user", "content": f"会议ID：{meeting_id}\n\n可用证据：\n{evidence_text}"},
    ]
    try:
        result, usage = llm_client.chat_json(messages, prompt_name="meeting_context")
    except Exception as e:
        result = {
            "background_facts": ["待确认"],
            "last_decisions": [],
            "open_risks": [a.summary for a in risk_atoms] or ["待确认"],
            "pending_questions": [],
        }
        usage = {"error": str(e)}

    evidence_ids = [ev.evidence_id for ev in verified]

    return {
        "meeting_id": meeting_id,
        "background_facts": result.get("background_facts", []),
        "last_decisions": result.get("last_decisions", []),
        "open_risks": result.get("open_risks", []),
        "pending_questions": result.get("pending_questions", []),
        "evidence_ids": evidence_ids,
        "evidence_sources": {ev.evidence_id: ev.source_url for ev in verified},
        "conflict_report": conflicts,
        "usage_traces": [usage],
    }
