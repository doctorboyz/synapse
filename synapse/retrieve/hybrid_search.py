"""Hybrid search — Dense + FTS5 → Reciprocal Rank Fusion

Inspired by: SocratiCode (RRF), MemPalace (hybrid weights)
"""

import math
from typing import Optional

from synapse.store.sqlite_store import SQLiteStore
from synapse.store.lancedb_store import LanceDBStore


def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    weights: Optional[list[float]] = None,
    k: int = 60,
) -> list[dict]:
    """Merge multiple ranked result lists using RRF.

    RRF score = sum(weight_i * 1 / (k + rank_i)) for each list i.
    Inspired by SocratiCode's RRF implementation.

    Args:
        result_lists: List of result lists, each sorted by relevance
        weights: Weight per list (default: equal weights)
        k: RRF constant (default 60, standard value)

    Returns:
        Merged results sorted by RRF score
    """
    if weights is None:
        weights = [1.0 / len(result_lists)] * len(result_lists)

    rrf_scores: dict[str, float] = {}
    doc_info: dict[str, dict] = {}

    for weight, results in zip(weights, result_lists):
        for rank, doc in enumerate(results, start=1):
            doc_id = doc["id"]
            score = weight / (k + rank)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + score

            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    "id": doc_id,
                    "title": doc.get("title", ""),
                    "scope": doc.get("scope", "shared"),
                    "doc_type": doc.get("doc_type", ""),
                }

    merged = [
        {**doc_info[doc_id], "score": score}
        for doc_id, score in sorted(rrf_scores.items(), key=lambda x: -x[1])
    ]

    return merged


def normalize_fts_rank(rank: float) -> float:
    """Normalize FTS5 rank to 0-1 range using exponential decay.

    FTS5 rank is negative (lower = better). We convert to 0-1 (higher = better).
    Inspired by arra-oracle's normalization.
    """
    return math.exp(0.3 * rank)


class HybridSearch:
    """Hybrid search combining dense vectors + FTS5 keyword search via RRF."""

    def __init__(self, sqlite: SQLiteStore, lancedb: LanceDBStore):
        self.sqlite = sqlite
        self.lancedb = lancedb

    def search(
        self,
        query: str,
        scope: Optional[str] = None,
        limit: int = 10,
        mode: str = "hybrid",
        weights: Optional[list[float]] = None,
    ) -> list[dict]:
        """Search knowledge base.

        Args:
            query: Search query
            scope: Filter to scope (None = all scopes)
            limit: Max results
            mode: 'hybrid' (dense+FTS5), 'dense' (vectors only), 'fts' (keyword only)
            weights: [dense_weight, fts_weight] for hybrid mode

        Returns:
            List of {id, title, scope, doc_type, score}
        """
        if mode == "dense":
            return self.lancedb.search(query, scope=scope, limit=limit)

        if mode == "fts":
            return self._search_fts(query, scope=scope, limit=limit)

        # Hybrid: both searches + RRF
        dense_results = self.lancedb.search(query, scope=scope, limit=limit * 2)
        fts_results = self._search_fts(query, scope=scope, limit=limit * 2)

        if not dense_results and not fts_results:
            return []

        if not dense_results:
            return fts_results[:limit]

        if not fts_results:
            return dense_results[:limit]

        # Default weights: 60% dense, 40% FTS (SocratiCode-inspired)
        if weights is None:
            weights = [0.6, 0.4]

        merged = reciprocal_rank_fusion(
            [dense_results, fts_results],
            weights=weights,
        )

        return merged[:limit]

    def _search_fts(self, query: str, scope: Optional[str], limit: int) -> list[dict]:
        """FTS5 search with normalized scores."""
        raw = self.sqlite.search_fts5(query, scope=scope, limit=limit)
        for r in raw:
            r["score"] = normalize_fts_rank(r["score"])
        return raw