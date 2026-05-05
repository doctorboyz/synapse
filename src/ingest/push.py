"""Knowledge push — manual and auto ingestion with dual-store write."""

import hashlib
import json
import logging
from pathlib import Path

from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.ingest.oracle_paths import extract_metadata, validate_doc_type

log = logging.getLogger("synapse.ingest.push")


class Push:
    """Push knowledge into both PostgreSQL and Qdrant."""

    def __init__(self, pg: PgStore, qdrant: QdrantStore | None = None,
                 embedder: OllamaEmbedder | None = None):
        self.pg = pg
        self.qdrant = qdrant
        self.embedder = embedder

    async def push_text(
        self,
        title: str,
        content: str,
        scope: str = "shared",
        doc_type: str = "learning",
        source_file: str | None = None,
        source_type: str = "manual",
        source_project: str | None = None,
        oracle_name: str | None = None,
        brain_path: str | None = None,
        brain_tier: str | None = None,
        concepts: list[str] | None = None,
        tags: list[str] | None = None,
        embed: bool = True,
    ) -> dict:
        validate_doc_type(doc_type)

        result = await self.pg.add(
            title=title, content=content, scope=scope, doc_type=doc_type,
            source_file=source_file, source_type=source_type,
            source_project=source_project, oracle_name=oracle_name,
            brain_path=brain_path, brain_tier=brain_tier,
            concepts=concepts, tags=tags,
        )

        if result["status"] == "duplicate":
            return result

        if embed and self.qdrant and self.embedder:
            try:
                vector = await self.embedder.embed(content)
                await self.qdrant.upsert(
                    doc_id=result["id"], vector=vector, title=title,
                    scope=scope, doc_type=doc_type,
                    oracle_name=oracle_name, brain_tier=brain_tier,
                    concepts=concepts,
                )
            except Exception as e:
                log.warning("Vector indexing failed: %s", e)
                result["status"] = "indexed_pg_only"

        return result

    async def push_file(self, file_path: str, scope: str | None = None,
                        doc_type: str | None = None, embed: bool = True) -> dict:
        path = Path(file_path)
        title = path.stem
        content = path.read_text(encoding="utf-8")

        meta = {}
        if scope is None:
            meta = extract_metadata(str(path), str(path.parent))
            scope = meta.get("scope", "shared")
        if doc_type is None and "doc_type" in meta:
            doc_type = meta["doc_type"]

        return await self.push_text(
            title=title, content=content, scope=scope,
            doc_type=doc_type or "learning",
            source_file=str(path), source_type="manual",
            oracle_name=meta.get("oracle_name"),
            brain_path=meta.get("brain_path"),
            brain_tier=meta.get("brain_tier"),
            embed=embed,
        )