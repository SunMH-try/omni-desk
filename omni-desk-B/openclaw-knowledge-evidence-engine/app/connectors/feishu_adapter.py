"""A01 — Feishu read-only data adapter (fixture mode)."""
import json
import yaml
from pathlib import Path
from typing import Optional
from app.config import FIXTURES_DIR


_FIXTURE_MAP = {
    "docs":     "docs",
    "minutes":  "minutes",
    "messages": "messages",
    "tasks":    "tasks",
    "calendar": "calendar",
    "bitable":  "bitable",
}


def _load_all_fixtures(source_type: str) -> list[dict]:
    folder = FIXTURES_DIR / _FIXTURE_MAP[source_type]
    if not folder.exists():
        return []
    results = []
    for f in folder.glob("*.json"):
        results.append(json.loads(f.read_text(encoding="utf-8")))
    return results


def load_source(
    source_type: str,
    source_id: Optional[str] = None,
    tenant_id: str = "demo_tenant",
    project_id: Optional[str] = None,
    mode: str = "demo",
) -> list[dict]:
    """Load raw source objects from local fixtures.

    Returns list of raw source dicts matching filters.
    Writes read_trace to outputs/events/ for auditing.
    """
    all_sources = _load_all_fixtures(source_type)
    filtered = []
    for s in all_sources:
        if s.get("tenant_id") != tenant_id:
            continue
        if source_id and s.get("source_id") != source_id:
            continue
        if project_id and s.get("project_id") != project_id:
            continue
        filtered.append(s)

    _write_trace(source_type, source_id, tenant_id, project_id, len(filtered))
    return filtered


def load_manifest(tenant_id: str = "demo_tenant", project_id: Optional[str] = None) -> list[dict]:
    """Return lightweight source manifest (no content) for all types."""
    manifest = []
    for stype in _FIXTURE_MAP:
        for s in _load_all_fixtures(stype):
            if s.get("tenant_id") != tenant_id:
                continue
            if project_id and s.get("project_id") != project_id:
                continue
            manifest.append({
                "source_id": s["source_id"],
                "source_type": s["source_type"],
                "title": s.get("title", ""),
                "url": s.get("url", ""),
                "tenant_id": s.get("tenant_id", ""),
                "project_id": s.get("project_id", ""),
                "permission_scope": s.get("permission_scope", []),
                "updated_at": s.get("updated_at", ""),
            })
    return manifest


def _write_trace(source_type, source_id, tenant_id, project_id, count):
    from app.config import OUTPUTS_DIR
    import datetime
    trace = {
        "source_type": source_type,
        "source_id": source_id,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "source_count": count,
        "mode": "demo",
        "timestamp": datetime.datetime.now().isoformat(),
    }
    out_dir = OUTPUTS_DIR / "events"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    (out_dir / f"read_trace_{source_type}_{ts}.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8"
    )
