"""FastAPI application — 4 evidence API endpoints."""
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.engine import get_engine
from app.retrieval import evidence_retriever, evidence_quality_judge
from app.ingestion import meeting_context, weekly_aggregator
from app.atoms.action_item_extractor import extract, items_to_dict
from app.ingestion.document_parser import parse
from app.connectors.feishu_adapter import load_source
from app.evaluation.metrics_engine import evaluate


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine(auto_build=True)
    yield


app = FastAPI(
    title="OpenClaw Knowledge Evidence Engine",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── Request / Response schemas ─────────────────────────────────────────────

class EvidenceQueryRequest(BaseModel):
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:12]}")
    project_id: str = "alpha_report_platform"
    query: str
    source_scope: Optional[list[str]] = None
    top_k: int = 8


class MeetingContextRequest(BaseModel):
    meeting_id: str
    lookback_days: int = 14
    include_unfinished_tasks: bool = True


class ActionItemsRequest(BaseModel):
    minutes_id: str
    need_owner_inference: bool = True
    need_deadline_inference: bool = True


class WeeklyWindowRequest(BaseModel):
    project_id: str = "alpha_report_platform"
    week_start: str
    week_end: str
    source_scope: Optional[list[str]] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.post("/evidence/v1/query")
def query_evidence(req: EvidenceQueryRequest):
    """A-API-01 证据检索接口"""
    engine = get_engine()
    engine.require_built()

    evidence_list, retrieval_trace = evidence_retriever.retrieve(
        query=req.query,
        graph=engine.graph,
        indexes=engine.indexes,
        atoms=engine.atoms,
        source_scope=req.source_scope,
        top_k=req.top_k,
        vector_index=engine.vector_index,
    )

    if not evidence_list:
        return {"code": 200, "trace_id": req.trace_id, "data": {"verified_evidence": [], "message": "NO_RELEVANT_EVIDENCE"}}

    verified, conflicts, _ = evidence_quality_judge.judge(req.query, evidence_list)

    return {
        "code": 200,
        "trace_id": req.trace_id,
        "data": {
            "verified_evidence": [
                {
                    "evidence_id": ev.evidence_id,
                    "summary": ev.summary,
                    "support_level": ev.support_level,
                    "confidence": round(ev.confidence, 3),
                    "source_type": ev.source_type,
                    "source_url": ev.source_url,
                    "is_stale": ev.is_stale,
                }
                for ev in verified
            ],
            "conflict_report": conflicts,
        },
    }


@app.post("/evidence/v1/meeting/context-package")
def meeting_context_package(req: MeetingContextRequest):
    """A-API-02 会议上下文包接口"""
    engine = get_engine()
    engine.require_built()

    result = meeting_context.generate(
        meeting_id=req.meeting_id,
        graph=engine.graph,
        indexes=engine.indexes,
        atoms=engine.atoms,
        lookback_days=req.lookback_days,
        include_unfinished_tasks=req.include_unfinished_tasks,
        vector_index=engine.vector_index,
    )

    return {
        "code": 200,
        "data": {
            "background_facts": result["background_facts"],
            "last_decisions": result["last_decisions"],
            "open_risks": result["open_risks"],
            "pending_questions": result.get("pending_questions", []),
            "evidence_ids": result["evidence_ids"],
        },
    }


@app.post("/evidence/v1/minutes/action-items")
def extract_action_items(req: ActionItemsRequest):
    """A-API-03 Action Item 抽取接口"""
    engine = get_engine()
    engine.require_built()

    raws = load_source("minutes", source_id=req.minutes_id,
                       tenant_id=engine.tenant_id, project_id=engine.project_id)
    if not raws:
        raise HTTPException(status_code=404, detail=f"Minutes {req.minutes_id} not found")

    parsed = parse(raws[0])
    src_url = raws[0].get("url", "")

    items, missing_report, _ = extract(
        source_id=req.minutes_id,
        source_url=src_url,
        parsed=parsed,
    )

    return {
        "code": 200,
        "data": {
            "action_items": items_to_dict(items),
            "missing_field_report": missing_report,
        },
    }


@app.post("/evidence/v1/weekly/window-summary")
def weekly_window_summary(req: WeeklyWindowRequest):
    """A-API-04 周报窗口聚合接口"""
    engine = get_engine()
    engine.require_built()

    result = weekly_aggregator.aggregate(
        project_id=req.project_id,
        week_start=req.week_start,
        week_end=req.week_end,
        graph=engine.graph,
        indexes=engine.indexes,
        atoms=engine.atoms,
        source_scope=req.source_scope,
        vector_index=engine.vector_index,
    )

    return {
        "code": 200,
        "data": {
            "weekly_atoms": result["weekly_atoms"],
            "progress_summary": result["progress_summary"],
            "risk_summary": result["risk_summary"],
            "key_insights": result.get("key_insights", []),
            "evidence_ids": result["evidence_ids"],
        },
    }


@app.get("/health")
def health():
    engine = get_engine(auto_build=False)
    return {"status": "ok", "built": engine._built if engine else False}
