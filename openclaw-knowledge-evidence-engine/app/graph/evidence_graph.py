"""A06 — Evidence Graph builder."""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional
from app.models import KnowledgeAtom, Evidence


@dataclass
class GraphNode:
    node_id: str
    node_type: str   # source | atom | person | risk | task
    label: str
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    from_id: str
    to_id: str
    relation: str    # contains | assigned_to | blocks | supports | references


@dataclass
class EvidenceGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    evidence_store: dict[str, Evidence] = field(default_factory=dict)


def build_graph(
    atoms: list[KnowledgeAtom],
    source_manifest: list[dict],
    tasks: list[dict] | None = None,
) -> EvidenceGraph:
    graph = EvidenceGraph()
    node_ids: set[str] = set()

    def _add_node(node: GraphNode):
        if node.node_id not in node_ids:
            graph.nodes.append(node)
            node_ids.add(node.node_id)

    # Add source nodes
    for src in source_manifest:
        _add_node(GraphNode(
            node_id=src["source_id"],
            node_type="source",
            label=src.get("title", src["source_id"]),
            metadata={"source_type": src.get("source_type"), "url": src.get("url")},
        ))

    # Add atom nodes and edges
    for atom in atoms:
        _add_node(GraphNode(
            node_id=atom.atom_id,
            node_type="atom",
            label=atom.summary[:60],
            metadata={"atom_type": atom.atom_type, "confidence": atom.confidence},
        ))
        graph.edges.append(GraphEdge(atom.source_id, atom.atom_id, "contains"))

        # Person nodes
        for owner in atom.owner_candidates:
            _add_node(GraphNode(node_id=owner, node_type="person", label=owner))
            graph.edges.append(GraphEdge(atom.atom_id, owner, "assigned_to"))

        # Evidence node per evidence_id
        for ev_id in atom.evidence_ids:
            evidence = Evidence(
                evidence_id=ev_id,
                summary=atom.summary,
                source_id=atom.source_id,
                source_type=_source_type(atom.source_id, source_manifest),
                source_url=_source_url(atom.source_id, source_manifest),
                chunk_text=atom.summary,
                timestamp=_source_updated(atom.source_id, source_manifest),
                support_level="high" if atom.confidence >= 0.85 else "medium" if atom.confidence >= 0.65 else "low",
                confidence=atom.confidence,
            )
            graph.evidence_store[ev_id] = evidence

    # Add task nodes and merge duplicates
    if tasks:
        for task in tasks:
            task_node_id = f"task_{task['task_id']}"
            _add_node(GraphNode(
                node_id=task_node_id,
                node_type="task",
                label=task["title"],
                metadata={"status": task.get("status"), "deadline": task.get("deadline")},
            ))
            src_id = task.get("source_minutes_id") or task.get("source_message_id")
            if src_id and src_id in node_ids:
                graph.edges.append(GraphEdge(src_id, task_node_id, "references"))
            if task.get("assignee"):
                owner = task["assignee"]
                _add_node(GraphNode(node_id=owner, node_type="person", label=owner))
                graph.edges.append(GraphEdge(task_node_id, owner, "assigned_to"))

    return graph


def _source_type(source_id: str, manifest: list[dict]) -> str:
    for s in manifest:
        if s["source_id"] == source_id:
            return s.get("source_type", "unknown")
    return "unknown"


def _source_url(source_id: str, manifest: list[dict]) -> str:
    for s in manifest:
        if s["source_id"] == source_id:
            return s.get("url", "")
    return ""


def _source_updated(source_id: str, manifest: list[dict]) -> str:
    for s in manifest:
        if s["source_id"] == source_id:
            return s.get("updated_at", "")
    return ""


def graph_to_dict(graph: EvidenceGraph) -> dict:
    return {
        "nodes": [{"node_id": n.node_id, "node_type": n.node_type, "label": n.label, "metadata": n.metadata} for n in graph.nodes],
        "edges": [{"from": e.from_id, "to": e.to_id, "relation": e.relation} for e in graph.edges],
        "evidence_count": len(graph.evidence_store),
    }
