"""Semantic vector index using embeddings (Volcengine ARK or local fallback)."""
from __future__ import annotations
import json
import time
from pathlib import Path
from app.models import Evidence


_ARK_EMBED_MODEL = "doubao-embedding-large"
_LOCAL_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_BATCH_SIZE = 32


class VectorIndex:
    """Holds dense vectors for a list of Evidence objects and supports cosine search."""

    def __init__(self, evidence_ids: list[str], vectors, evidence_map: dict[str, Evidence]):
        self.evidence_ids = evidence_ids
        self.vectors = vectors  # numpy array, shape (N, D)
        self.evidence_map = evidence_map

    def search(self, query_vec, top_k: int = 20) -> list[tuple[float, Evidence]]:
        import numpy as np
        if len(self.evidence_ids) == 0:
            return []
        q = np.array(query_vec, dtype=np.float32)
        q /= (np.linalg.norm(q) + 1e-9)
        scores = self.vectors @ q  # cosine similarity (vectors are pre-normalised)
        top_indices = scores.argsort()[::-1][:top_k]
        results = []
        for idx in top_indices:
            eid = self.evidence_ids[idx]
            ev = self.evidence_map.get(eid)
            if ev is not None:
                results.append((float(scores[idx]), ev))
        return results

    def save(self, cache_dir: Path):
        import numpy as np
        cache_dir.mkdir(parents=True, exist_ok=True)
        np.save(str(cache_dir / "vectors.npy"), self.vectors)
        (cache_dir / "vector_evidence_ids.json").write_text(
            json.dumps(self.evidence_ids, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, cache_dir: Path, evidence_map: dict[str, Evidence]) -> "VectorIndex | None":
        import numpy as np
        vec_file = cache_dir / "vectors.npy"
        ids_file = cache_dir / "vector_evidence_ids.json"
        if not vec_file.exists() or not ids_file.exists():
            return None
        vectors = np.load(str(vec_file))
        evidence_ids = json.loads(ids_file.read_text(encoding="utf-8"))
        return cls(evidence_ids=evidence_ids, vectors=vectors, evidence_map=evidence_map)


def build_vector_index(evidence_map: dict[str, Evidence], verbose: bool = True) -> VectorIndex:
    """Embed all evidence chunks and return a VectorIndex."""
    import numpy as np

    evidence_ids = list(evidence_map.keys())
    texts = [
        (ev.summary + " " + ev.chunk_text)[:512]
        for ev in evidence_map.values()
    ]

    if verbose:
        print(f"[vector_index] Embedding {len(texts)} evidence chunks ...")

    vectors = _embed_batch(texts, verbose=verbose)
    # L2-normalise for cosine similarity via dot product
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / (norms + 1e-9)
    return VectorIndex(evidence_ids=evidence_ids, vectors=vectors, evidence_map=evidence_map)


def embed_query(text: str) -> list[float]:
    vecs = _embed_batch([text], verbose=False)
    return vecs[0].tolist()


def _embed_batch(texts: list[str], verbose: bool = True):
    import numpy as np
    all_vecs = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i: i + _BATCH_SIZE]
        try:
            vecs = _embed_volcengine(batch)
        except Exception as e:
            if verbose:
                print(f"[vector_index] ARK embed failed ({e}), using local model ...")
            vecs = _embed_local(batch)
        all_vecs.extend(vecs)
    return np.array(all_vecs, dtype=np.float32)


def _embed_volcengine(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    from app.config import API_KEY, ARK_BASE_URL

    client = OpenAI(api_key=API_KEY, base_url=ARK_BASE_URL)
    resp = client.embeddings.create(model=_ARK_EMBED_MODEL, input=texts)
    return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]


def _embed_local(texts: list[str]) -> list[list[float]]:
    from sentence_transformers import SentenceTransformer
    model = _get_local_model()
    return model.encode(texts, show_progress_bar=False).tolist()


_local_model_cache = None


def _get_local_model():
    global _local_model_cache
    if _local_model_cache is None:
        from sentence_transformers import SentenceTransformer
        _local_model_cache = SentenceTransformer(_LOCAL_MODEL)
    return _local_model_cache
