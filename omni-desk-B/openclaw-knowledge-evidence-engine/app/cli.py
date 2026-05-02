"""CLI entry point: python -m tkp_a <command>"""
import json
import sys
import click
from app.engine import KnowledgeEngine, get_engine
from app.config import DEFAULT_PROJECT_ID, DEFAULT_TENANT_ID


def _print_json(data):
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


@click.group()
def cli():
    """OpenClaw Knowledge Evidence Engine CLI"""
    pass


@cli.command("build-index")
@click.option("--project", default=DEFAULT_PROJECT_ID, help="Project ID")
def build_index_cmd(project):
    """Build PageIndex, extract atoms, and construct evidence graph."""
    engine = KnowledgeEngine(project_id=project)
    engine.build(verbose=True)
    click.echo(f"\n[done] Index built. Atoms: {len(engine.atoms)}, Graph nodes: {len(engine.graph.nodes)}")


@cli.command("seed-demo-data")
def seed_demo_data():
    """Verify that fixture files are present and readable."""
    from app.connectors.feishu_adapter import load_manifest
    manifest = load_manifest(DEFAULT_TENANT_ID, DEFAULT_PROJECT_ID)
    click.echo(f"[seed] Found {len(manifest)} fixture sources:")
    for s in manifest:
        click.echo(f"  [{s['source_type']}] {s['source_id']} — {s['title']}")
    click.echo("[seed] Demo data ready.")


@cli.command("query")
@click.option("--q", required=True, help="Query string")
@click.option("--project", default=DEFAULT_PROJECT_ID)
@click.option("--top-k", default=8, type=int)
def query_cmd(q, project, top_k):
    """Retrieve and display verified evidence for a query."""
    from app.retrieval import evidence_retriever, evidence_quality_judge
    engine = _load_engine(project)
    evidence_list, trace = evidence_retriever.retrieve(
        query=q, graph=engine.graph, indexes=engine.indexes,
        atoms=engine.atoms, top_k=top_k, vector_index=engine.vector_index,
    )
    if not evidence_list:
        click.echo("NO_RELEVANT_EVIDENCE")
        return
    verified, conflicts, _ = evidence_quality_judge.judge(q, evidence_list)
    click.echo(f"\n[query] '{q}'")
    click.echo(f"Verified evidence ({len(verified)}):\n")
    for ev in verified:
        click.echo(f"  [{ev.evidence_id}] [{ev.support_level}] {ev.summary}")
        if ev.source_url:
            click.echo(f"    source: {ev.source_url}")
    if conflicts:
        click.echo(f"\nConflicts detected: {len(conflicts)}")


@cli.command("meeting-context")
@click.option("--meeting-id", required=True)
@click.option("--project", default=DEFAULT_PROJECT_ID)
def meeting_context_cmd(meeting_id, project):
    """Generate pre-meeting context package."""
    from app.ingestion import meeting_context
    engine = _load_engine(project)
    result = meeting_context.generate(
        meeting_id=meeting_id,
        graph=engine.graph,
        indexes=engine.indexes,
        atoms=engine.atoms,
        vector_index=engine.vector_index,
    )
    click.echo(f"\n[meeting-context] {meeting_id}\n")
    click.echo("Background Facts:")
    for f in result["background_facts"]:
        click.echo(f"  - {f}")
    click.echo("\nLast Decisions:")
    for d in result["last_decisions"]:
        click.echo(f"  - {d}")
    click.echo("\nOpen Risks:")
    for r in result["open_risks"]:
        click.echo(f"  - {r}")
    click.echo(f"\nEvidence IDs: {result['evidence_ids']}")


@cli.command("extract-actions")
@click.option("--minutes-id", required=True)
@click.option("--project", default=DEFAULT_PROJECT_ID)
def extract_actions_cmd(minutes_id, project):
    """Extract action items from meeting minutes."""
    from app.atoms.action_item_extractor import extract, items_to_dict
    from app.ingestion.document_parser import parse
    from app.connectors.feishu_adapter import load_source
    engine = _load_engine(project)
    raws = load_source("minutes", source_id=minutes_id,
                       tenant_id=engine.tenant_id, project_id=engine.project_id)
    if not raws:
        click.echo(f"Minutes {minutes_id} not found", err=True)
        sys.exit(1)
    parsed = parse(raws[0])
    items, missing, _ = extract(minutes_id, raws[0].get("url", ""), parsed)
    click.echo(f"\n[extract-actions] {minutes_id} — {len(items)} items\n")
    for item in items_to_dict(items):
        owner = item["owner"] or "⚠ 待确认"
        dl = item["deadline"] or "待确认"
        click.echo(f"  [{item['item_id']}] {item['title']}")
        click.echo(f"    owner={owner}  deadline={dl}  priority={item['priority']}  conf={item['confidence']:.2f}")
    if missing:
        click.echo(f"\nMissing fields / duplicates: {len(missing)}")


@cli.command("weekly-window")
@click.option("--project", default=DEFAULT_PROJECT_ID)
@click.option("--week", required=True, help="ISO week e.g. 2026-W17 or date range start")
def weekly_window_cmd(project, week):
    """Aggregate weekly knowledge window."""
    from app.ingestion import weekly_aggregator
    # Parse week: accept 2026-W17 or 2026-04-20
    if week.count("-") == 1 and "W" in week:
        import datetime
        year, wnum = week.split("-W")
        # Use ISO week (Monday = day 1)
        monday = datetime.datetime.fromisocalendar(int(year), int(wnum), 1)
        week_start = monday.strftime("%Y-%m-%d")
        week_end = (monday + datetime.timedelta(days=6)).strftime("%Y-%m-%d")
    else:
        import datetime
        start = datetime.datetime.strptime(week, "%Y-%m-%d")
        week_start = start.strftime("%Y-%m-%d")
        week_end = (start + datetime.timedelta(days=6)).strftime("%Y-%m-%d")

    engine = _load_engine(project)
    result = weekly_aggregator.aggregate(
        project_id=project,
        week_start=week_start,
        week_end=week_end,
        graph=engine.graph,
        indexes=engine.indexes,
        atoms=engine.atoms,
        vector_index=engine.vector_index,
    )
    click.echo(f"\n[weekly-window] {week_start} ~ {week_end}\n")
    click.echo(f"Progress: {result['progress_summary']}")
    click.echo(f"\nRisks: {result['risk_summary']}")
    click.echo(f"\nKey Insights:")
    for ins in result.get("key_insights", []):
        click.echo(f"  - {ins}")
    click.echo(f"\nEvidence IDs: {result['evidence_ids']}")


@cli.command("evaluate")
@click.option("--dataset", default=None, help="Path to golden dataset JSON")
@click.option("--project", default=DEFAULT_PROJECT_ID)
def evaluate_cmd(dataset, project):
    """Run evaluation metrics against golden dataset."""
    from app.evaluation.metrics_engine import evaluate
    from app.atoms.action_item_extractor import extract, items_to_dict
    from app.ingestion.document_parser import parse
    from app.connectors.feishu_adapter import load_source
    from app.retrieval import evidence_retriever, evidence_quality_judge

    engine = _load_engine(project)

    # Get agent outputs
    evidence_list, _ = evidence_retriever.retrieve(
        "Alpha 项目周会需要关注哪些延期风险？",
        graph=engine.graph, indexes=engine.indexes, atoms=engine.atoms, top_k=10,
        vector_index=engine.vector_index,
    )
    verified, _, _ = evidence_quality_judge.judge("风险查询", evidence_list)

    raws = load_source("minutes", source_id="minutes_alpha_review",
                       tenant_id=engine.tenant_id, project_id=engine.project_id)
    action_items = []
    if raws:
        parsed = parse(raws[0])
        items, _, _ = extract("minutes_alpha_review", raws[0].get("url", ""), parsed)
        action_items = items_to_dict(items)

    report = evaluate(
        agent_action_items=action_items,
        agent_evidence=[{"evidence_id": ev.evidence_id, "source_id": ev.source_id,
                         "support_level": ev.support_level} for ev in verified],
        golden_dataset_path=dataset,
    )

    click.echo("\n[evaluate] Metrics Report\n")
    for m in report["metrics"]:
        status = "✓" if m["passed"] else "✗"
        click.echo(f"  {status} {m['metric']}: {m['value']:.3f} (threshold={m['threshold']})")
    click.echo(f"\nOverall: {'PASS' if report['overall_pass'] else 'FAIL'}")


def _load_engine(project: str) -> KnowledgeEngine:
    engine = KnowledgeEngine(project_id=project)
    if engine.load_from_cache(verbose=True):
        return engine
    click.echo(f"[engine] No cache found, building index (this may take a few minutes) ...")
    engine.build(verbose=True)
    return engine
