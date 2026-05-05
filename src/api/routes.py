"""HTTP API routes — mirrors MCP tool interface for Docker service access."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.ingest.push import Push
from src.ingest.oracle_paths import validate_doc_type, validate_trace_relation
from src.retrieve.hybrid_search import HybridSearch

router = APIRouter(prefix="/api", tags=["synapse"])

pg: PgStore | None = None
qdrant: QdrantStore | None = None
embedder: OllamaEmbedder | None = None
push: Push | None = None
search: HybridSearch | None = None


def init_routes(pg_store: PgStore, qdrant_store: QdrantStore | None,
                embedder_client: OllamaEmbedder | None):
    global pg, qdrant, embedder, push, search
    pg = pg_store
    qdrant = qdrant_store
    embedder = embedder_client
    push = Push(pg, qdrant, embedder)
    search = HybridSearch(pg, qdrant, embedder)


# --- Search ---

class SearchRequest:
    def __init__(self, query: str, scope: str | None = None, doc_type: str | None = None,
                 oracle: str | None = None, source_project: str | None = None,
                 concepts: list[str] | None = None, limit: int = 10, mode: str = "hybrid"):
        self.query = query
        self.scope = scope
        self.doc_type = doc_type
        self.oracle = oracle
        self.source_project = source_project
        self.concepts = concepts
        self.limit = limit
        self.mode = mode


@router.post("/search")
async def api_search(body: dict):
    results = await search.search(
        query=body["query"],
        scope=body.get("scope"),
        doc_type=body.get("doc_type"),
        oracle=body.get("oracle"),
        source_project=body.get("source_project"),
        concepts=body.get("concepts"),
        limit=body.get("limit", 10),
        mode=body.get("mode", "hybrid"),
    )
    return results


# --- Push ---

@router.post("/push")
async def api_push(body: dict):
    result = await push.push_text(
        title=body["title"],
        content=body["content"],
        scope=body.get("scope", "shared"),
        doc_type=body.get("doc_type", "learning"),
        source_file=body.get("source_file"),
        source_type=body.get("source_type", "api"),
        source_project=body.get("source_project"),
        concepts=body.get("concepts"),
        tags=body.get("tags"),
        oracle_name=body.get("oracle_name"),
        brain_path=body.get("brain_path"),
        brain_tier=body.get("brain_tier"),
    )
    return result


# --- Webhook (for external projects) ---

@router.post("/webhook")
async def api_webhook(body: dict):
    body.setdefault("source_type", "webhook")
    return await api_push(body)


# --- Supersede ---

@router.post("/supersede")
async def api_supersede(body: dict):
    result = await pg.supersede(
        old_id=body["old_id"],
        new_content=body["new_content"],
        reason=body.get("reason", "updated"),
        new_title=body.get("new_title"),
    )
    if qdrant:
        await qdrant.mark_superseded(body["old_id"])
    return result


# --- Trace ---

@router.post("/trace")
async def api_trace(body: dict):
    validate_trace_relation(body["relation"])
    result = await pg.add_trace(
        source_id=body["source_id"],
        target_id=body["target_id"],
        relation=body["relation"],
        confidence=body.get("confidence", 1.0),
    )
    return result


@router.get("/trace/{doc_id}")
async def api_trace_chain(doc_id: str, direction: str = "both",
                          max_depth: int = 5, relation: str | None = None):
    results = await pg.get_trace_chain(doc_id, direction, max_depth, relation)
    return results


# --- Concepts ---

@router.get("/concepts")
async def api_concepts(search: str | None = None, limit: int = 50):
    results = await pg.list_concepts(search, limit)
    return results


# --- Get ---

@router.get("/documents/{doc_id}")
async def api_get(doc_id: str, include_chain: bool = True):
    doc = await pg.get(doc_id, include_chain=include_chain)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# --- Scope ---

@router.get("/scopes")
async def api_scopes():
    return await pg.list_scopes()


# --- Stats ---

@router.get("/stats")
async def api_stats():
    return await pg.stats()


# --- List ---

@router.get("/documents")
async def api_list(scope: str | None = None, doc_type: str | None = None,
                   oracle: str | None = None, limit: int = 20, offset: int = 0,
                   order: str = "newest"):
    return await pg.list_docs(scope, doc_type, oracle, limit, offset, order)


# --- Health ---

@router.get("/health")
async def api_health():
    embedding_ok = False
    if embedder:
        embedding_ok = await embedder.check()
    qdrant_ok = qdrant is not None
    return {
        "status": "ok",
        "qdrant": qdrant_ok,
        "embedding": embedding_ok,
    }