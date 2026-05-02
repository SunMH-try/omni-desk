"""Central engine: loads fixtures, builds indexes, exposes query methods."""
import json
import dataclasses
from app.connectors.feishu_adapter import load_source, load_manifest
from app.ingestion.document_parser import parse
from app.indexing.page_index_builder import build as build_index, PageIndex, PageNode
from app.atoms.atom_extractor import extract_atoms
from app.graph.evidence_graph import build_graph, EvidenceGraph, GraphNode, GraphEdge
from app.models import KnowledgeAtom, Evidence
from app.config import DEFAULT_TENANT_ID, DEFAULT_PROJECT_ID, OUTPUTS_DIR

_CACHE_DIR = OUTPUTS_DIR / "cache"
_VECTOR_CACHE_DIR = _CACHE_DIR / "vectors"


class KnowledgeEngine:
    def __init__(self, tenant_id=DEFAULT_TENANT_ID, project_id=DEFAULT_PROJECT_ID):
        self.tenant_id = tenant_id
        self.project_id = project_id
        self.indexes: list[PageIndex] = []
        self.atoms: list[KnowledgeAtom] = []
        self.graph: EvidenceGraph | None = None
        self.manifest: list[dict] = []
        self.vector_index = None
        self._built = False

    def build(self, verbose=True, incremental=True):
        """Load fixtures, build indexes, extract atoms, build graph.

        With incremental=True, skips sources whose updated_at hasn't changed
        since the last build, loading them from cache instead.
        """
        if verbose:
            print(f"[engine] Loading sources for project={self.project_id} ...")

        self.manifest = load_manifest(self.tenant_id, self.project_id)
        if verbose:
            print(f"[engine] Found {len(self.manifest)} sources")

        # Load existing cache for incremental mode
        cached_timestamps: dict[str, str] = {}
        cached_indexes: dict[str, object] = {}
        cached_atoms: dict[str, list] = {}
        if incremental and self.load_from_cache(verbose=False):
            ts_file = _CACHE_DIR / "source_timestamps.json"
            if ts_file.exists():
                cached_timestamps = json.loads(ts_file.read_text(encoding="utf-8"))
            # Index and atom lookup by source_id
            cached_indexes = {idx.source_id: idx for idx in self.indexes}
            cached_atoms = {}
            for a in self.atoms:
                cached_atoms.setdefault(a.source_id, []).append(a)
            # Reset for rebuild
            self.indexes = []
            self.atoms = []

        all_atoms: list[KnowledgeAtom] = []
        tasks_raw = []

        for src_meta in self.manifest:
            src_id = src_meta["source_id"]
            src_type = src_meta["source_type"]
            updated_at = src_meta.get("updated_at", "")

            raws = load_source(src_type, source_id=src_id,
                               tenant_id=self.tenant_id, project_id=self.project_id)
            if not raws:
                continue
            raw = raws[0]

            if src_type == "tasks":
                tasks_raw = raw.get("tasks", [])
                continue
            if src_type in ("calendar", "bitable"):
                continue

            # Incremental: reuse cache if source unchanged
            if incremental and cached_timestamps.get(src_id) == updated_at and src_id in cached_indexes:
                if verbose:
                    print(f"[engine] Skipping {src_id} (unchanged, loaded from cache)")
                self.indexes.append(cached_indexes[src_id])
                all_atoms.extend(cached_atoms.get(src_id, []))
                continue

            try:
                parsed = parse(raw)
            except Exception as e:
                if verbose:
                    print(f"[engine] Parse error for {src_id}: {e}")
                continue

            if verbose:
                print(f"[engine] Building index for {src_id} ...")
            try:
                index = build_index(parsed, src_id)
                self.indexes.append(index)
            except Exception as e:
                if verbose:
                    print(f"[engine] Index error for {src_id}: {e}")
                continue

            if verbose:
                print(f"[engine] Extracting atoms for {src_id} ...")
            try:
                atoms, _ = extract_atoms(index, src_id)
                all_atoms.extend(atoms)
                if verbose:
                    print(f"[engine]   -> {len(atoms)} atoms")
            except Exception as e:
                if verbose:
                    print(f"[engine] Atom extraction error for {src_id}: {e}")

        self.atoms = all_atoms
        if verbose:
            print(f"[engine] Total atoms: {len(self.atoms)}")
            print(f"[engine] Building evidence graph ...")

        self.graph = build_graph(self.atoms, self.manifest, tasks_raw)
        self._built = True

        if verbose:
            print(f"[engine] Building vector index ...")
        try:
            from app.indexing.vector_index import build_vector_index
            self.vector_index = build_vector_index(self.graph.evidence_store, verbose=verbose)
            self.vector_index.save(_VECTOR_CACHE_DIR)
        except Exception as e:
            if verbose:
                print(f"[engine] Vector index build failed ({e}), semantic search disabled")
            self.vector_index = None

        self._save_cache()

        # Save timestamps for next incremental run
        timestamps = {s["source_id"]: s.get("updated_at", "") for s in self.manifest}
        (_CACHE_DIR / "source_timestamps.json").write_text(
            json.dumps(timestamps, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if verbose:
            print(f"[engine] Build complete. Graph nodes: {len(self.graph.nodes)}")
            print(f"[engine] Cache saved to {_CACHE_DIR}")

    def load_from_cache(self, verbose=True) -> bool:
        """Load previously built state from disk. Returns True if successful."""
        meta_file = _CACHE_DIR / "meta.json"
        if not meta_file.exists():
            return False
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if meta.get("project_id") != self.project_id:
                return False

            # Load manifest
            self.manifest = json.loads((_CACHE_DIR / "manifest.json").read_text(encoding="utf-8"))

            # Load atoms
            atoms_data = json.loads((_CACHE_DIR / "atoms.json").read_text(encoding="utf-8"))
            self.atoms = [KnowledgeAtom(**a) for a in atoms_data]

            # Load evidence store
            ev_data = json.loads((_CACHE_DIR / "evidence_store.json").read_text(encoding="utf-8"))
            evidence_store = {k: Evidence(**v) for k, v in ev_data.items()}

            # Load indexes (leaf nodes only, enough for retrieval)
            index_data = json.loads((_CACHE_DIR / "indexes.json").read_text(encoding="utf-8"))
            self.indexes = []
            for idx_d in index_data:
                leaf_nodes = [
                    PageNode(node_id=n["node_id"], source_id=n["source_id"],
                             title=n["title"], summary=n["summary"],
                             chunk=n.get("chunk"), depth=n["depth"])
                    for n in idx_d["nodes"]
                ]
                root = PageNode(
                    node_id=f"root_{idx_d['source_id']}", source_id=idx_d["source_id"],
                    title=idx_d["source_id"], summary=idx_d["doc_description"],
                    chunk=None, children=leaf_nodes, depth=0,
                )
                self.indexes.append(PageIndex(
                    source_id=idx_d["source_id"], root=root,
                    all_nodes=[root] + leaf_nodes,
                    doc_description=idx_d["doc_description"],
                ))

            # Rebuild graph
            graph_data = json.loads((_CACHE_DIR / "graph.json").read_text(encoding="utf-8"))
            nodes = [GraphNode(node_id=n["node_id"], node_type=n["node_type"],
                               label=n["label"], metadata=n.get("metadata", {}))
                     for n in graph_data["nodes"]]
            edges = [GraphEdge(from_id=e["from"], to_id=e["to"], relation=e["relation"])
                     for e in graph_data["edges"]]
            self.graph = EvidenceGraph(nodes=nodes, edges=edges, evidence_store=evidence_store)

            # Load vector index if available
            try:
                from app.indexing.vector_index import VectorIndex
                self.vector_index = VectorIndex.load(_VECTOR_CACHE_DIR, evidence_store)
            except Exception:
                self.vector_index = None

            self._built = True
            if verbose:
                vec_status = f", vector_index={'yes' if self.vector_index else 'no'}"
                print(f"[engine] Loaded from cache: {len(self.atoms)} atoms, {len(self.graph.nodes)} nodes{vec_status}")
            return True
        except Exception as e:
            if verbose:
                print(f"[engine] Cache load failed ({e}), will rebuild ...")
            return False

    def require_built(self):
        if not self._built:
            raise RuntimeError("Engine not built. Run `python -m app build-index` first.")

    def _save_cache(self):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Meta
        (_CACHE_DIR / "meta.json").write_text(
            json.dumps({"tenant_id": self.tenant_id, "project_id": self.project_id}, ensure_ascii=False),
            encoding="utf-8")

        # Manifest
        (_CACHE_DIR / "manifest.json").write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        # Atoms
        (_CACHE_DIR / "atoms.json").write_text(
            json.dumps([dataclasses.asdict(a) for a in self.atoms], ensure_ascii=False, indent=2),
            encoding="utf-8")

        # Evidence store
        ev_data = {k: dataclasses.asdict(v) for k, v in self.graph.evidence_store.items()}
        (_CACHE_DIR / "evidence_store.json").write_text(
            json.dumps(ev_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Indexes (leaf nodes only)
        index_data = []
        for idx in self.indexes:
            leaf_nodes = [
                {"node_id": n.node_id, "source_id": n.source_id, "title": n.title,
                 "summary": n.summary, "chunk": n.chunk, "depth": n.depth}
                for n in idx.all_nodes if n.chunk is not None
            ]
            index_data.append({
                "source_id": idx.source_id,
                "doc_description": idx.doc_description,
                "nodes": leaf_nodes,
            })
        (_CACHE_DIR / "indexes.json").write_text(
            json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Graph (without evidence_store, saved separately)
        from app.graph.evidence_graph import graph_to_dict
        graph_dict = graph_to_dict(self.graph)
        (_CACHE_DIR / "graph.json").write_text(
            json.dumps(graph_dict, ensure_ascii=False, indent=2), encoding="utf-8")

        # Summary
        (OUTPUTS_DIR / "demo" / "index_summary.json").write_text(
            json.dumps({
                "tenant_id": self.tenant_id, "project_id": self.project_id,
                "source_count": len(self.manifest), "index_count": len(self.indexes),
                "atom_count": len(self.atoms),
                "graph_node_count": len(self.graph.nodes),
                "graph_edge_count": len(self.graph.edges),
            }, ensure_ascii=False, indent=2), encoding="utf-8")


_engine_instance: KnowledgeEngine | None = None


def get_engine(auto_build=True) -> KnowledgeEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = KnowledgeEngine()
        if auto_build:
            # Try cache first — avoids LLM calls
            if not _engine_instance.load_from_cache(verbose=False):
                _engine_instance.build(verbose=False)
    return _engine_instance