"""A11 — Weekly time-window aggregator."""
import json
from datetime import datetime
from app import llm_client
from app.models import KnowledgeAtom, Evidence
from app.retrieval import evidence_retriever, evidence_quality_judge
from app.graph.evidence_graph import EvidenceGraph
from app.indexing.page_index_builder import PageIndex


_WEEKLY_PROMPT = """你是一个周报生成助手。根据本周证据，生成：
1. progress_summary：本周进展摘要（不超过120字）
2. risk_summary：本周风险摘要（不超过120字）
3. key_insights：2-4条关键洞察，每条不超过120字

要求：
- 区分本周新增与历史遗留
- 任务延期信息必须有来源
- 没有证据支持的结论标记为"待确认"

输出 JSON：{"progress_summary":"","risk_summary":"","key_insights":[]}
只返回 JSON。
"""


def aggregate(
    project_id: str,
    week_start: str,
    week_end: str,
    graph: EvidenceGraph,
    indexes: list[PageIndex],
    atoms: list[KnowledgeAtom],
    source_scope: list[str] | None = None,
    vector_index=None,
) -> dict:
    """Aggregate weekly knowledge window."""
    query = f"项目 {project_id} 在 {week_start} 到 {week_end} 期间的进展、风险和关键事件"

    evidence_list, _ = evidence_retriever.retrieve(
        query=query,
        graph=graph,
        indexes=indexes,
        atoms=atoms,
        source_scope=source_scope,
        top_k=12,
        vector_index=vector_index,
    )

    # Filter by time window
    filtered = _filter_by_window(evidence_list, week_start, week_end)
    if not filtered:
        filtered = evidence_list  # fallback to all if no time match

    verified, _, judge_traces = evidence_quality_judge.judge(query, filtered)

    # Classify atoms into this-week and historical
    this_week_atoms = [a for a in atoms if _in_window(a, week_start, week_end)]
    historical_atoms = [a for a in atoms if not _in_window(a, week_start, week_end)]

    weekly_atom_ids = [a.atom_id for a in this_week_atoms]
    evidence_text = "\n".join(
        f"[{ev.evidence_id}] {ev.summary}" for ev in verified
    )

    messages = [
        {"role": "system", "content": _WEEKLY_PROMPT},
        {"role": "user", "content": f"项目：{project_id}\n时间窗口：{week_start} 至 {week_end}\n\n本周证据：\n{evidence_text}"},
    ]
    try:
        result, usage = llm_client.chat_json(messages, prompt_name="weekly_aggregate")
    except Exception as e:
        result = {"progress_summary": "待确认", "risk_summary": "待确认", "key_insights": []}
        usage = {"error": str(e)}

    return {
        "project_id": project_id,
        "week_start": week_start,
        "week_end": week_end,
        "weekly_atoms": weekly_atom_ids,
        "progress_summary": result.get("progress_summary", ""),
        "risk_summary": result.get("risk_summary", ""),
        "key_insights": result.get("key_insights", []),
        "evidence_ids": [ev.evidence_id for ev in verified],
        "this_week_count": len(this_week_atoms),
        "historical_count": len(historical_atoms),
        "usage_traces": [usage],
    }


def _filter_by_window(evidence_list: list[Evidence], start: str, end: str) -> list[Evidence]:
    result = []
    for ev in evidence_list:
        if not ev.timestamp:
            continue
        try:
            ts = ev.timestamp[:10]
            if start <= ts <= end:
                result.append(ev)
        except Exception:
            pass
    return result


def _in_window(atom: KnowledgeAtom, start: str, end: str) -> bool:
    # Atoms don't have timestamps directly; use source evidence
    return True  # simplified: include all atoms in demo
