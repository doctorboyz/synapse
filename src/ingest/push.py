"""Knowledge push — manual and auto ingestion with dual-store write."""

import hashlib
import json
import logging
from pathlib import Path

from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.ingest.oracle_paths import extract_metadata, validate_doc_type
from src.ingest.obsidian_links import create_traces_from_links
from src.ingest.concepts import extract_concepts

log = logging.getLogger("synapse.ingest.push")


class Push:
    """Push knowledge into both PostgreSQL and Qdrant."""

    def __init__(self, pg: PgStore, qdrant: QdrantStore | None = None,
                 embedder: OllamaEmbedder | None = None):
        self.pg = pg
        self.qdrant = qdrant
        self.embedder = embedder

    async def _summarize(self, content: str, model: str | None = None) -> str:
        """Summarize long content using OpenRouter (fallback to Ollama)."""
        from src.llm.openrouter_client import OpenRouterClient

        settings = self.embedder.settings if self.embedder else __import__("src.config").Settings()
        client = OpenRouterClient(settings)
        try:
            return await client.summarize(
                content,
                model=model or settings.openrouter_summary_model,
            )
        except Exception as e:
            log.warning("Summarization failed: %s", e)
            return content[:2000]

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
        trace_content: str | None = None,
    ) -> dict:
        validate_doc_type(doc_type)

        if concepts is None:
            concepts = extract_concepts(content)

        summary = None
        if len(content) > 3000 and self.embedder:
            summary = await self._summarize(content)

        result = await self.pg.add(
            title=title, content=content, scope=scope, doc_type=doc_type,
            source_file=source_file, source_type=source_type,
            source_project=source_project, oracle_name=oracle_name,
            brain_path=brain_path, brain_tier=brain_tier,
            concepts=concepts, tags=tags, summary=summary,
        )

        # Create traces from Obsidian-style [[links]] in content
        if result["status"] != "duplicate":
            try:
                trace_result = await create_traces_from_links(
                    self.pg, result["id"], trace_content or content, scope=scope
                )
                if trace_result["traces_created"] > 0:
                    log.info("Created %d traces from obsidian links in '%s'",
                             trace_result["traces_created"], title)
            except Exception as e:
                log.warning("Obsidian link trace creation failed: %s", e)

        if embed and self.qdrant and self.embedder:
            try:
                text_for_embedding = summary or content
                vector = await self.embedder.embed(text_for_embedding)
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