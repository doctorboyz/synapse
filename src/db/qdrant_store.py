"""Qdrant vector store — upsert, search, delete with payload filters."""

import uuid
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, PointStruct, VectorParams,
    Filter, FieldCondition, MatchValue,
    Query,
)

from src.config import Settings


class QdrantStore:
    """Async Qdrant vector store with payload filtering."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._client: AsyncQdrantClient | None = None

    async def connect(self) -> None:
        self._client = AsyncQdrantClient(url=self._settings.qdrant_url)
        try:
            await self._client.get_collection(self._settings.qdrant_collection)
        except Exception:
            await self._client.create_collection(
                collection_name=self._settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=self._settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            raise RuntimeError("QdrantStore not connected — call connect() first")
        return self._client

    async def upsert(
        self,
        doc_id: str,
        vector: list[float],
        title: str,
        scope: str,
        doc_type: str = "learning",
        oracle_name: str | None = None,
        brain_tier: str | None = None,
        concepts: list[str] | None = None,
    ) -> None:
        payload = {
            "title": title,
            "scope": scope,
            "doc_type": doc_type,
            "superseded": False,
            "created_at": "",
        }
        if oracle_name:
            payload["oracle_name"] = oracle_name
        if brain_tier:
            payload["brain_tier"] = brain_tier
        if concepts:
            payload["concepts"] = concepts

        point = PointStruct(
            id=uuid.UUID(doc_id).hex,
            vector=vector,
            payload=payload,
        )
        await self.client.upsert(
            collection_name=self._settings.qdrant_collection,
            points=[point],
        )

    async def search(
        self,
        vector: list[float],
        scope: str | None = None,
        doc_type: str | None = None,
        oracle: str | None = None,
        source_project: str | None = None,
        concepts: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        conditions = [FieldCondition(key="superseded", match=MatchValue(value=False))]

        if scope:
            conditions.append(FieldCondition(key="scope", match=MatchValue(value=scope)))
        if doc_type:
            conditions.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
        if oracle:
            conditions.append(FieldCondition(key="oracle_name", match=MatchValue(value=oracle)))
        if source_project:
            conditions.append(FieldCondition(key="source_project", match=MatchValue(value=source_project)))
        if concepts:
            for concept in concepts:
                conditions.append(FieldCondition(key="concepts", match=MatchValue(value=concept)))

        search_filter = Filter(must=conditions) if conditions else None

        results = await self.client.query_points(
            collection_name=self._settings.qdrant_collection,
            query=vector,
            query_filter=search_filter,
            limit=limit,
            with_payload=True,
        )

        return [
            {
                "id": str(r.id),
                "title": r.payload.get("title", "") if r.payload else "",
                "scope": r.payload.get("scope", "") if r.payload else "",
                "doc_type": r.payload.get("doc_type", "") if r.payload else "",
                "oracle_name": r.payload.get("oracle_name") if r.payload else None,
                "score": r.score,
            }
            for r in results.points
        ]

    async def mark_superseded(self, doc_id: str) -> None:
        try:
            await self.client.set_payload(
                collection_name=self._settings.qdrant_collection,
                payload={"superseded": True},
                points=[uuid.UUID(doc_id).hex],
            )
        except Exception:
            pass

    async def delete(self, doc_id: str) -> None:
        try:
            await self.client.delete(
                collection_name=self._settings.qdrant_collection,
                points_selector=[uuid.UUID(doc_id).hex],
            )
        except Exception:
            pass