"""A12 — Evaluation data & metrics engine."""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass, field
from app.config import FIXTURES_DIR, OUTPUTS_DIR


@dataclass
class EvalResult:
    metric: str
    value: float
    passed: bool
    threshold: float
    details: dict = field(default_factory=dict)


THRESHOLDS = {
    "citation_accuracy": 0.90,
    "evidence_coverage": 0.85,
    "action_item_precision": 0.85,
    "action_item_recall": 0.85,
    "hallucination_rate": 0.05,
}


def evaluate(
    agent_action_items: list[dict],
    agent_evidence: list[dict],
    golden_dataset_path: str | None = None,
) -> dict:
    """Compute evaluation metrics against golden dataset."""
    golden = _load_golden(golden_dataset_path)
    results = []

    # Action Item Precision & Recall
    if golden.get("action_items"):
        precision, recall, details = _action_item_metrics(
            agent_action_items, golden["action_items"]
        )
        results.append(EvalResult(
            "action_item_precision", precision,
            precision >= THRESHOLDS["action_item_precision"],
            THRESHOLDS["action_item_precision"], details,
        ))
        results.append(EvalResult(
            "action_item_recall", recall,
            recall >= THRESHOLDS["action_item_recall"],
            THRESHOLDS["action_item_recall"], details,
        ))

    # Citation Accuracy
    cited_with_source = sum(1 for ev in agent_evidence if ev.get("source_id") or ev.get("evidence_id"))
    citation_acc = cited_with_source / len(agent_evidence) if agent_evidence else 0.0
    results.append(EvalResult(
        "citation_accuracy", citation_acc,
        citation_acc >= THRESHOLDS["citation_accuracy"],
        THRESHOLDS["citation_accuracy"],
    ))

    # Hallucination Rate
    unverified = sum(1 for ev in agent_evidence if ev.get("support_level") == "unverified")
    hallucination_rate = unverified / len(agent_evidence) if agent_evidence else 0.0
    results.append(EvalResult(
        "hallucination_rate", hallucination_rate,
        hallucination_rate <= THRESHOLDS["hallucination_rate"],
        THRESHOLDS["hallucination_rate"],
    ))

    report = {
        "metrics": [
            {
                "metric": r.metric,
                "value": round(r.value, 3),
                "threshold": r.threshold,
                "passed": r.passed,
            }
            for r in results
        ],
        "overall_pass": all(r.passed for r in results),
        "case_analysis": golden.get("cases", []),
    }

    _save_report(report)
    return report


def _action_item_metrics(predicted: list[dict], golden: list[dict]) -> tuple[float, float, dict]:
    pred_titles = [_normalize(p.get("title", "")) for p in predicted]
    gold_titles = [_normalize(g.get("title", "")) for g in golden]

    matched_pred = set()
    matched_gold = set()
    for gi, gt in enumerate(gold_titles):
        for pi, pt in enumerate(pred_titles):
            if pi in matched_pred:
                continue
            if _title_match(pt, gt):
                matched_pred.add(pi)
                matched_gold.add(gi)
                break

    tp = len(matched_gold)
    precision = tp / len(pred_titles) if pred_titles else 0.0
    recall = tp / len(gold_titles) if gold_titles else 0.0

    missed = [gold_titles[i] for i in range(len(gold_titles)) if i not in matched_gold]
    extra = [pred_titles[i] for i in range(len(pred_titles)) if i not in matched_pred]

    return precision, recall, {
        "true_positives": tp,
        "predicted": len(pred_titles),
        "golden": len(gold_titles),
        "missed": missed,
        "extra": extra,
    }


def _title_match(a: str, b: str, threshold: float = 0.5) -> bool:
    """Fuzzy match: check if a contains b or vice versa, or char-set overlap >= threshold."""
    if b in a or a in b:
        return True
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return False
    overlap = len(sa & sb) / len(sa | sb)
    return overlap >= threshold


def _normalize(text: str) -> str:
    return "".join(text.split()).lower()


def _load_golden(path: str | None) -> dict:
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    # Default golden dataset from fixtures
    default = FIXTURES_DIR / "golden" / "demo_alpha.json"
    if default.exists():
        return json.loads(default.read_text(encoding="utf-8"))
    return {
        "action_items": [
            {"title": "完成测试环境权限开通"},
            {"title": "权限开通后验证测试环境可用"},
            {"title": "完成数据接入层接口联调"},
            {"title": "提交接口压测报告"},
            {"title": "更新里程碑文档记录延期"},
        ],
        "cases": [
            {"name": "会前背景", "query": "Alpha 项目周会需要关注哪些延期风险？", "expected_evidence": "测试环境权限未开通导致联调延期"},
            {"name": "会后任务", "query": "会议纪要中的 Action Items", "expected_items": 5},
            {"name": "周报风险", "query": "本周主要风险", "expected_risk": "测试环境权限"},
        ],
    }


def _save_report(report: dict):
    import datetime
    out_dir = OUTPUTS_DIR / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    (out_dir / f"eval_report_{ts}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
