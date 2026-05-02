"""A04 — PageIndex tree index builder."""
import json
import uuid
import re
from dataclasses import dataclass, field
from typing import Optional
from app import llm_client
from app.ingestion.document_parser import full_text, ParsedDocument, ParsedMinutes


CHUNK_SIZE = 600
OVERLAP = 80


@dataclass
class PageNode:
    node_id: str
    source_id: str
    title: str
    summary: str
    chunk: Optional[str]   # None for internal nodes
    children: list["PageNode"] = field(default_factory=list)
    depth: int = 0


@dataclass
class PageIndex:
    source_id: str
    root: PageNode
    all_nodes: list[PageNode] = field(default_factory=list)
    doc_description: str = ""
    usage_traces: list[dict] = field(default_factory=list)


def build(parsed, source_id: str) -> PageIndex:
    """Build PageIndex from any parsed document object."""
    if isinstance(parsed, ParsedDocument):
        return _build_from_doc(parsed, source_id)
    text = full_text(parsed)
    return _build_from_text(text, source_id, title=getattr(parsed, "title", source_id))


def _build_from_doc(doc: ParsedDocument, source_id: str) -> PageIndex:
    usage_traces = []
    root_children = []
    all_nodes = []

    for sec in doc.sections:
        heading = sec.get("heading", "")
        content = sec.get("content", "")
        if not content.strip():
            continue
        chunks = _chunk_text(content, CHUNK_SIZE, OVERLAP)
        section_children = []
        for i, chunk in enumerate(chunks):
            summary, usage = _summarize(chunk, f"chunk_{source_id}_{i}")
            usage_traces.append(usage)
            node = PageNode(
                node_id=f"node_{uuid.uuid4().hex[:8]}",
                source_id=source_id,
                title=f"{heading} [{i+1}/{len(chunks)}]" if len(chunks) > 1 else heading,
                summary=summary,
                chunk=chunk,
                depth=2,
            )
            section_children.append(node)
            all_nodes.append(node)

        sec_summary = section_children[0].summary if section_children else heading
        sec_node = PageNode(
            node_id=f"node_{uuid.uuid4().hex[:8]}",
            source_id=source_id,
            title=heading,
            summary=sec_summary,
            chunk=None,
            children=section_children,
            depth=1,
        )
        root_children.append(sec_node)
        all_nodes.append(sec_node)

    doc_desc, usage = _describe_doc(doc.title, [n.summary for n in root_children], f"doc_desc_{source_id}")
    usage_traces.append(usage)

    root = PageNode(
        node_id=f"root_{source_id}",
        source_id=source_id,
        title=doc.title,
        summary=doc_desc,
        chunk=None,
        children=root_children,
        depth=0,
    )
    all_nodes.insert(0, root)
    return PageIndex(source_id=source_id, root=root, all_nodes=all_nodes,
                     doc_description=doc_desc, usage_traces=usage_traces)


def _build_from_text(text: str, source_id: str, title: str) -> PageIndex:
    usage_traces = []
    chunks = _chunk_text(text, CHUNK_SIZE, OVERLAP)
    leaf_nodes = []
    for i, chunk in enumerate(chunks):
        summary, usage = _summarize(chunk, f"chunk_{source_id}_{i}")
        usage_traces.append(usage)
        node = PageNode(
            node_id=f"node_{uuid.uuid4().hex[:8]}",
            source_id=source_id,
            title=f"{title} [{i+1}]",
            summary=summary,
            chunk=chunk,
            depth=1,
        )
        leaf_nodes.append(node)

    doc_desc, usage = _describe_doc(title, [n.summary for n in leaf_nodes], f"doc_desc_{source_id}")
    usage_traces.append(usage)

    root = PageNode(
        node_id=f"root_{source_id}",
        source_id=source_id,
        title=title,
        summary=doc_desc,
        chunk=None,
        children=leaf_nodes,
        depth=0,
    )
    return PageIndex(source_id=source_id, root=root, all_nodes=[root] + leaf_nodes,
                     doc_description=doc_desc, usage_traces=usage_traces)


def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def _summarize(chunk: str, prompt_name: str) -> tuple[str, dict]:
    messages = [
        {"role": "system", "content": "你是一个文档摘要助手。请用一句话（30字以内）精炼地概括以下内容的核心信息，不要添加原文中不存在的事实。"},
        {"role": "user", "content": chunk},
    ]
    return llm_client.chat(messages, prompt_name=prompt_name)


def _describe_doc(title: str, section_summaries: list[str], prompt_name: str) -> tuple[str, dict]:
    summaries_text = "\n".join(f"- {s}" for s in section_summaries[:10])
    messages = [
        {"role": "system", "content": "你是一个文档描述生成助手。根据章节摘要，用一句话描述整篇文档的核心主题和关键结论，不超过60字，不添加原文不存在的事实。"},
        {"role": "user", "content": f"文档标题：{title}\n\n章节摘要：\n{summaries_text}"},
    ]
    return llm_client.chat(messages, prompt_name=prompt_name)


def to_dict(index: PageIndex) -> dict:
    def node_to_dict(n: PageNode) -> dict:
        d = {
            "node_id": n.node_id,
            "source_id": n.source_id,
            "title": n.title,
            "summary": n.summary,
            "depth": n.depth,
        }
        if n.chunk:
            d["chunk"] = n.chunk
        if n.children:
            d["children"] = [node_to_dict(c) for c in n.children]
        return d

    return {
        "source_id": index.source_id,
        "doc_description": index.doc_description,
        "node_count": len(index.all_nodes),
        "tree": node_to_dict(index.root),
        "usage_traces": index.usage_traces,
    }
