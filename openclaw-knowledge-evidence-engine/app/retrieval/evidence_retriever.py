"""A07 — Multi-source retrieval & evidence recall (BM25 + semantic + RRF)."""
from __future__ import annotations
import re
from app.models import Evidence, KnowledgeAtom
from app.graph.evidence_graph import EvidenceGraph
from app.indexing.page_index_builder import PageIndex, PageNode


def retrieve(
    query: str,
    graph: EvidenceGraph,
    indexes: list[PageIndex],
    atoms: list[KnowledgeAtom],
    source_scope: list[str] | None = None,
    top_k: int = 8,
    time_window_days: int | None = None,
    vector_index=None,
) -> tuple[list[Evidence], list[dict]]:
    """Retrieve relevant evidence chunks via BM25 + semantic RRF fusion.

    Returns (evidence_list, retrieval_trace).
    """
    query_tokens = _tokenize(query)

    # --- BM25 path ---
    bm25_candidates: list[tuple[float, Evidence]] = []

    for index in indexes:
        _search_index(index.root, query_tokens, graph, bm25_candidates)

    for ev_id, ev in graph.evidence_store.items():
        if source_scope:
            if ev.source_type not in source_scope and ev.source_id not in source_scope:
                continue
        score = _bm25_score(query_tokens, _tokenize(ev.summary + " " + ev.chunk_text))
        if score > 0:
            bm25_candidates.append((score, ev))

    # Dedup BM25 by evidence_id, keep highest score
    bm25_seen: dict[str, float] = {}
    for score, ev in bm25_candidates:
        if ev.evidence_id not in bm25_seen or bm25_seen[ev.evidence_id] < score:
            bm25_seen[ev.evidence_id] = score

    bm25_ranked = sorted(bm25_seen.items(), key=lambda x: x[1], reverse=True)
    ev_map = {ev.evidence_id: ev for _, ev in bm25_candidates}

    # --- Semantic path ---
    semantic_ranked: list[tuple[str, float]] = []
    if vector_index is not None:
        try:
            from app.indexing.vector_index import embed_query
            q_vec = embed_query(query)
            sem_results = vector_index.search(q_vec, top_k=min(50, len(vector_index.evidence_ids)))
            for score, ev in sem_results:
                semantic_ranked.append((ev.evidence_id, score))
                if ev.evidence_id not in ev_map:
                    ev_map[ev.evidence_id] = ev
        except Exception:
            pass  # semantic path optional

    # --- RRF fusion ---
    rrf_scores = _rrf_fuse(
        [eid for eid, _ in bm25_ranked],
        [eid for eid, _ in semantic_ranked],
    )

    # If no results from either path
    if not rrf_scores and not bm25_ranked and not semantic_ranked:
        return [], [{"query": query, "result": "NO_RELEVANT_EVIDENCE"}]

    # Merge: RRF-ranked first, then any BM25-only remainder
    seen_ids = set()
    deduped_ev: list[Evidence] = []
    for eid, _ in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        ev = ev_map.get(eid)
        if ev and eid not in seen_ids:
            deduped_ev.append(ev)
            seen_ids.add(eid)
    for eid, _ in bm25_ranked:
        if eid not in seen_ids:
            ev = ev_map.get(eid)
            if ev:
                deduped_ev.append(ev)
                seen_ids.add(eid)

    # Content-similarity dedup
    final = _content_dedup(deduped_ev, threshold=0.65)

    # Graph expansion
    expanded = _graph_expand(final, graph, atoms, top_k)

    results = expanded[:top_k]
    trace = {
        "query": query,
        "source_scope": source_scope,
        "top_k": top_k,
        "bm25_candidates": len(bm25_ranked),
        "semantic_candidates": len(semantic_ranked),
        "after_rrf": len(deduped_ev),
        "after_content_dedup": len(final),
        "after_graph_expand": len(expanded),
        "returned": len(results),
    }
    return results, [trace]


def _rrf_fuse(
    bm25_ids: list[str],
    semantic_ids: list[str],
    k: int = 60,
) -> dict[str, float]:
    """Reciprocal Rank Fusion over two ranked lists."""
    scores: dict[str, float] = {}
    for rank, eid in enumerate(bm25_ids):
        scores[eid] = scores.get(eid, 0.0) + 1.0 / (k + rank + 1)
    for rank, eid in enumerate(semantic_ids):
        scores[eid] = scores.get(eid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _content_dedup(evidence_list: list[Evidence], threshold: float) -> list[Evidence]:
    kept = []
    for ev in evidence_list:
        duplicate = False
        for kept_ev in kept:
            if _text_overlap(ev.summary, kept_ev.summary) >= threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(ev)
    return kept


def _text_overlap(a: str, b: str) -> float:
    """Character bigram Jaccard similarity."""
    def bigrams(s):
        s = s.replace(" ", "")
        return set(s[i:i+2] for i in range(len(s) - 1))
    ba, bb = bigrams(a), bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / len(ba | bb)


def _graph_expand(
    evidence_list: list[Evidence],
    graph: EvidenceGraph,
    atoms: list[KnowledgeAtom],
    top_k: int,
) -> list[Evidence]:
    if len(evidence_list) >= top_k:
        return evidence_list

    retrieved_source_ids = {ev.source_id for ev in evidence_list}
    retrieved_ev_ids = {ev.evidence_id for ev in evidence_list}

    expansion_candidates: list[Evidence] = []
    for atom in atoms:
        if atom.atom_type not in ("Risk", "Blocker", "Decision", "ActionItem"):
            continue
        if atom.source_id not in retrieved_source_ids:
            continue
        for ev_id in atom.evidence_ids:
            if ev_id in retrieved_ev_ids:
                continue
            ev = graph.evidence_store.get(ev_id)
            if ev and ev.evidence_id not in retrieved_ev_ids:
                expansion_candidates.append(ev)
                retrieved_ev_ids.add(ev_id)

    all_summaries = {ev.summary for ev in evidence_list}
    filtered = []
    for ev in expansion_candidates:
        if not any(_text_overlap(ev.summary, s) >= 0.65 for s in all_summaries):
            filtered.append(ev)
            all_summaries.add(ev.summary)

    return evidence_list + filtered


def _search_index(node: PageNode, query_tokens: list[str], graph: EvidenceGraph, out: list):
    if node.chunk:
        score = _bm25_score(query_tokens, _tokenize(node.chunk + " " + node.summary))
        if score > 0:
            ev = graph.evidence_store.get(f"ev_{node.source_id}_chunk")
            if ev is None:
                ev = Evidence(
                    evidence_id=f"ev_idx_{node.node_id}",
                    summary=node.summary,
                    source_id=node.source_id,
                    source_type="docs",
                    source_url="",
                    chunk_text=node.chunk,
                    timestamp="",
                    support_level="medium",
                    confidence=0.7,
                )
            out.append((score, ev))
    for child in node.children:
        _search_index(child, query_tokens, graph, out)


def _tokenize(text: str) -> list[str]:
    try:
        import jieba
        tokens = [t for t in jieba.cut(text) if len(t.strip()) > 0
                  and not re.match(r'^[\s，。！？、：；""\'\'（）【】\[\]]+$', t)]
        return tokens
    except ImportError:
        return re.findall(r'[一-鿿]{2,}|[a-zA-Z0-9]+', text.lower())


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], k1=1.5, b=0.75) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    from collections import Counter
    doc_len = len(doc_tokens)
    avg_len = 100
    tf = Counter(doc_tokens)
    score = 0.0
    for token in set(query_tokens):
        freq = tf.get(token, 0)
        if freq == 0:
            continue
        score += (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * doc_len / avg_len))
    return score


def _infer_type(source_id: str) -> str:
    for t in ["docs", "minutes", "messages", "tasks", "calendar", "bitable"]:
        if t in source_id:
            return t
    return "unknown"
