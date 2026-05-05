"""Hybrid search — Qdrant dense + PostgreSQL tsvector → Reciprocal Rank Fusion."""

import logging
from typing import Optional

from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder, EmbeddingError

log = logging.getLogger("mysynapse.retrieve.hybrid")


def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    weights: list[float] | None = None,
    k: int = 60,
) -> list[dict]:
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
                    "oracle_name": doc.get("oracle_name"),
                    "source_project": doc.get("source_project"),
                }

    return [
        {**doc_info[doc_id], "score": score}
        for doc_id, score in sorted(rrf_scores.items(), key=lambda x: -x[1])
    ]


class HybridSearch:
    """Qdrant dense + PostgreSQL tsvector → RRF fusion."""

    def __init__(self, pg: PgStore, qdrant: QdrantStore | None = None,
                 embedder: OllamaEmbedder | None = None,
                 weights: list[float] | None = None, rrf_k: int = 60):
        self.pg = pg
        self.qdrant = qdrant
        self.embedder = embedder
        self._weights = weights or [0.6, 0.4]
        self._rrf_k = rrf_k

    async def search(
        self,
        query: str,
        scope: str | None = None,
        doc_type: str | None = None,
        oracle: str | None = None,
        source_project: str | None = None,
        concepts: list[str] | None = None,
        limit: int = 10,
        mode: str = "hybrid",
    ) -> list[dict]:
        if mode == "dense":
            if not self.qdrant or not self.embedder:
                raise SearchError("Dense search requires Qdrant and OllamaEmbedder")
            vector = await self.embedder.embed(query)
            return await self.qdrant.search(
                vector, scope=scope, doc_type=doc_type, oracle=oracle,
                source_project=source_project, concepts=concepts, limit=limit,
            )

        if mode == "fts":
            return await self.pg.search_fts(
                query, scope=scope, doc_type=doc_type, oracle=oracle,
                source_project=source_project, limit=limit,
            )

        # Hybrid: both + RRF
        if not self.qdrant or not self.embedder:
            return await self.pg.search_fts(
                query, scope=scope, doc_type=doc_type, oracle=oracle,
                source_project=source_project, limit=limit,
            )

        try:
            vector = await self.embedder.embed(query)
            dense_results = await self.qdrant.search(
                vector, scope=scope, doc_type=doc_type, oracle=oracle,
                source_project=source_project, concepts=concepts, limit=limit * 2,
            )
        except EmbeddingError as e:
            log.warning("Dense search failed, falling back to FTS: %s", e)
            return await self.pg.search_fts(
                query, scope=scope, doc_type=doc_type, oracle=oracle,
                source_project=source_project, limit=limit,
            )

        fts_results = await self.pg.search_fts(
            query, scope=scope, doc_type=doc_type, oracle=oracle,
            source_project=source_project, limit=limit * 2,
        )

        if not dense_results and not fts_results:
            return []
        if not dense_results:
            return fts_results[:limit]
        if not fts_results:
            return dense_results[:limit]

        merged = reciprocal_rank_fusion(
            [dense_results, fts_results],
            weights=self._weights,
            k=self._rrf_k,
        )
        return merged[:limit]


class SearchError(Exception):
    pass