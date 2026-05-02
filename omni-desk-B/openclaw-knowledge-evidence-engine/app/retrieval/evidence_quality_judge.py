"""A08 — Relevance & evidence quality judge."""
import json
from datetime import datetime, timezone
from app.models import Evidence
from app import llm_client


_JUDGE_PROMPT = """你是一个证据质量评估助手。对于给定的查询和证据列表，判断每条证据的：
1. 相关性（0-1，越高越相关）
2. 是否过期（基于时间戳和当前日期）
3. 是否与其他证据冲突

返回 JSON 数组，每项格式：
{
  "evidence_id": "...",
  "relevance": 0.0-1.0,
  "is_stale": true/false,
  "stale_reason": "说明或null",
  "conflict_with": ["冲突的evidence_id列表，没有则空"],
  "final_support_level": "high|medium|low|unverified"
}

规则：
- relevance < 0.4 的证据不应进入最终结果
- 超过 30 天未更新的证据标记为 stale
- 没有来源（source_id 为空）的结论标记为 unverified
只返回 JSON 数组。
"""


def judge(
    query: str,
    evidence_list: list[Evidence],
    current_date: str | None = None,
) -> tuple[list[Evidence], list[dict], list[dict]]:
    """Judge evidence quality.

    Returns (verified_evidence, conflict_report, usage_traces).
    """
    if not evidence_list:
        return [], [], []

    if current_date is None:
        current_date = datetime.now().strftime("%Y-%m-%d")

    ev_summaries = [
        {"evidence_id": ev.evidence_id, "summary": ev.summary, "timestamp": ev.timestamp}
        for ev in evidence_list
    ]

    messages = [
        {"role": "system", "content": _JUDGE_PROMPT},
        {"role": "user", "content": f"当前日期：{current_date}\n查询：{query}\n\n证据列表：\n{json.dumps(ev_summaries, ensure_ascii=False, indent=2)}"},
    ]
    try:
        judgements, usage = llm_client.chat_json(messages, prompt_name="evidence_judge")
    except Exception as e:
        # Fallback: pass everything through as medium
        judgements = [{"evidence_id": ev.evidence_id, "relevance": 0.7, "is_stale": False,
                       "conflict_with": [], "final_support_level": "medium"} for ev in evidence_list]
        usage = {"error": str(e)}

    judge_map = {j["evidence_id"]: j for j in judgements}
    verified = []
    conflict_report = []

    for ev in evidence_list:
        j = judge_map.get(ev.evidence_id, {})
        relevance = float(j.get("relevance", 0.7))
        if relevance < 0.4:
            continue
        if not ev.source_id:
            ev.support_level = "unverified"
            continue

        ev.is_stale = j.get("is_stale", False)
        level = j.get("final_support_level", ev.support_level)
        # 有来源的证据不应被标为 unverified，最低给 low
        if level == "unverified" and ev.source_id:
            level = "low"
        ev.support_level = level
        ev.confidence = relevance

        if j.get("conflict_with"):
            conflict_report.append({
                "evidence_id": ev.evidence_id,
                "conflict_with": j["conflict_with"],
                "summary": ev.summary,
            })

        verified.append(ev)

    return verified, conflict_report, [usage]
