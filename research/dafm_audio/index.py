"""Nearest-neighbour indices for representation spaces.

Exact blocked search (numpy / sklearn) is the default and the scientifically
defensible baseline at this corpus size. Optional ``hnswlib`` is an accelerator
that must prove its recall against the exact index before being trusted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

logger = logging.getLogger(__name__)

Metric = Literal["euclidean", "cosine"]


@dataclass
class NearestNeighborIndex:
    """Opaque index handle returned by :func:`build_index`."""

    backend: str
    metric: Metric
    X: np.ndarray
    handle: Any = None
    meta: dict[str, Any] = field(default_factory=dict)


def _normalize_rows(X: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.where(norms > 0, norms, 1.0)
    return X / norms


def build_index(
    X: np.ndarray,
    metric: Metric = "euclidean",
    *,
    backend: str = "exact",
    space_params: dict[str, Any] | None = None,
) -> NearestNeighborIndex:
    """Build a nearest-neighbour index over rows of ``X``.

    Parameters
    ----------
    X:
        ``(n, d)`` float matrix.
    metric:
        ``euclidean`` for handcrafted / parameter spaces, ``cosine`` for embeddings.
    backend:
        ``exact`` (default) or ``hnsw`` when ``hnswlib`` is installed.
    """
    X = np.asarray(X, dtype=np.float32)
    if X.ndim != 2:
        raise ValueError(f"X must be 2-D, got shape {X.shape}")

    if backend == "hnsw":
        try:
            import hnswlib
        except ImportError:
            logger.warning("hnswlib not installed; falling back to exact index")
            backend = "exact"
        else:
            space = "l2" if metric == "euclidean" else "cosine"
            params = space_params or {}
            index = hnswlib.Index(space=space, dim=X.shape[1])
            index.init_index(
                max_elements=X.shape[0],
                ef_construction=int(params.get("ef_construction", 200)),
                M=int(params.get("M", 16)),
            )
            index.add_items(X, np.arange(X.shape[0]))
            index.set_ef(int(params.get("ef", 64)))
            return NearestNeighborIndex(
                backend="hnsw",
                metric=metric,
                X=X,
                handle=index,
                meta=params,
            )

    # Exact baseline: store matrix; cosine queries use L2 on L2-normalised rows.
    stored = _normalize_rows(X) if metric == "cosine" else X
    return NearestNeighborIndex(backend="exact", metric=metric, X=stored, handle=None)


def query(
    index: NearestNeighborIndex,
    q: np.ndarray,
    k: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(indices, distances)`` for one or more queries.

    Distances are Euclidean (or cosine distance = 1 - similarity) depending on the
    metric the index was built with.
    """
    q = np.asarray(q, dtype=np.float32)
    single = q.ndim == 1
    q = np.atleast_2d(q)
    k = min(int(k), index.X.shape[0])

    if index.backend == "hnsw" and index.handle is not None:
        labels, distances = index.handle.knn_query(q, k=k)
        if single:
            return labels[0], distances[0]
        return labels, distances

    if index.metric == "cosine":
        qn = _normalize_rows(q)
        # cosine distance = 1 - dot for unit vectors
        sims = qn @ index.X.T
        # argpartition then sort top-k
        idx_part = np.argpartition(-sims, kth=k - 1, axis=1)[:, :k]
        part_sims = np.take_along_axis(sims, idx_part, axis=1)
        order = np.argsort(-part_sims, axis=1)
        indices = np.take_along_axis(idx_part, order, axis=1)
        top_sims = np.take_along_axis(part_sims, order, axis=1)
        distances = 1.0 - top_sims
    else:
        # Exact Euclidean via sklearn when available, else numpy.
        try:
            from sklearn.metrics import pairwise_distances

            dists = pairwise_distances(q, index.X, metric="euclidean")
        except ImportError:
            dists = np.sqrt(
                np.maximum(
                    np.sum(q**2, axis=1)[:, None]
                    + np.sum(index.X**2, axis=1)[None, :]
                    - 2.0 * q @ index.X.T,
                    0.0,
                )
            )
        idx_part = np.argpartition(dists, kth=k - 1, axis=1)[:, :k]
        part = np.take_along_axis(dists, idx_part, axis=1)
        order = np.argsort(part, axis=1)
        indices = np.take_along_axis(idx_part, order, axis=1)
        distances = np.take_along_axis(part, order, axis=1)

    if single:
        return indices[0], distances[0]
    return indices, distances


def verify_ann_recall(
    X: np.ndarray,
    metric: Metric = "euclidean",
    *,
    n_queries: int = 100,
    k: int = 10,
    seed: int = 42,
    space_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare HNSW recall against the exact index on a random query sample.

    Returns a report dict. If ``hnswlib`` is absent, reports ``skipped``.
    """
    X = np.asarray(X, dtype=np.float32)
    n = X.shape[0]
    if n < 2:
        return {"skipped": True, "reason": "too_few_rows"}

    try:
        import hnswlib  # noqa: F401
    except ImportError:
        return {"skipped": True, "reason": "hnswlib_absent", "backend_default": "exact"}

    rng = np.random.default_rng(seed)
    n_queries = min(n_queries, n)
    q_idx = rng.choice(n, size=n_queries, replace=False)
    queries = X[q_idx]

    exact = build_index(X, metric=metric, backend="exact")
    ann = build_index(X, metric=metric, backend="hnsw", space_params=space_params)

    exact_idx, _ = query(exact, queries, k=k)
    ann_idx, _ = query(ann, queries, k=k)

    hits = []
    for i in range(n_queries):
        hits.append(len(set(exact_idx[i].tolist()) & set(ann_idx[i].tolist())) / float(k))
    recall = float(np.mean(hits))
    return {
        "skipped": False,
        "metric": metric,
        "n_queries": n_queries,
        "k": k,
        "recall_at_k": recall,
        "backend_ann": "hnsw",
        "backend_ref": "exact",
    }
