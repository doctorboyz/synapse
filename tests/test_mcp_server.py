"""Tests for MCP server tool handlers."""

import json
import pytest
import pytest_asyncio

from src.config import Settings
from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.ingest.push import Push
from src.retrieve.hybrid_search import HybridSearch
from src.mcp.server import create_app


@pytest_asyncio.fixture
async def app_components():
    settings = Settings()
    settings.database_url = "postgresql://admin:88888888@localhost:5432/mysynapse"
    pg = PgStore(settings)
    await pg.connect()
    await pg.init_schema()

    qdrant = None  # No Qdrant in tests
    embedder = None  # No Ollama in tests

    push = Push(pg, qdrant, embedder)
    search = HybridSearch(pg, qdrant, embedder)

    yield pg, push, search
    await pg.close()


@pytest_asyncio.fixture
async def clean_components(app_components):
    pg, push, search = app_components
    async with pg.pool.acquire() as conn:
        await conn.execute("DELETE FROM document_concepts")
        await conn.execute("DELETE FROM trace")
        await conn.execute("DELETE FROM supersede_log")
        await conn.execute("DELETE FROM knowledge_documents")
        await conn.execute("DELETE FROM concepts")
        await conn.execute("DELETE FROM scope_registry")
    return app_components


class TestMCPSearch:
    @pytest.mark.asyncio
    async def test_search_fts_mode(self, clean_components):
        pg, push, search = clean_components
        await push.push_text(title="Python Patterns", content="list comprehensions and generators", scope="shared")
        results = await search.search("python", mode="fts")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_with_scope(self, clean_components):
        pg, push, search = clean_components
        await push.push_text(title="Shared", content="public knowledge", scope="shared")
        await push.push_text(title="Emily", content="private knowledge", scope="emily")
        results = await search.search("knowledge", scope="emily", mode="fts")
        assert len(results) >= 1
        assert all(r["scope"] == "emily" for r in results)

    @pytest.mark.asyncio
    async def test_search_with_doc_type(self, clean_components):
        pg, push, search = clean_components
        await push.push_text(title="Tip", content="use venv", scope="shared", doc_type="learning")
        await push.push_text(title="Pattern", content="factory pattern", scope="shared", doc_type="pattern")
        results = await search.search("pattern", doc_type="pattern", mode="fts")
        assert len(results) >= 1
        assert all(r["doc_type"] == "pattern" for r in results)

    @pytest.mark.asyncio
    async def test_search_no_results(self, clean_components):
        pg, push, search = clean_components
        results = await search.search("xyznonexistent123", mode="fts")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_hybrid_fallback_fts(self, clean_components):
        pg, push, search = clean_components
        await push.push_text(title="Docker Tips", content="Use compose v2", scope="shared")
        results = await search.search("docker", mode="hybrid")
        assert len(results) >= 1


class TestMCPPush:
    @pytest.mark.asyncio
    async def test_push_and_get(self, clean_components):
        pg, push, search = clean_components
        result = await push.push_text(
            title="Test Doc", content="hello world", scope="shared", doc_type="learning",
        )
        assert result["status"] == "indexed"

        doc = await pg.get(result["id"])
        assert doc["title"] == "Test Doc"
        assert doc["content"] == "hello world"
        assert doc["doc_type"] == "learning"

    @pytest.mark.asyncio
    async def test_push_supersede_and_get_chain(self, clean_components):
        pg, push, search = clean_components
        add_result = await push.push_text(title="Original", content="version 1", scope="shared")
        supersede_result = await pg.supersede(add_result["id"], "version 2")

        doc = await pg.get(add_result["id"], include_chain=True)
        assert doc["superseded_by"] is not None

    @pytest.mark.asyncio
    async def test_push_with_concepts(self, clean_components):
        pg, push, search = clean_components
        result = await push.push_text(
            title="Hybrid Search", content="combines dense and keyword",
            scope="shared", concepts=["search", "hybrid"],
        )
        concepts = await pg.list_concepts()
        names = [c["name"] for c in concepts]
        assert "search" in names


class TestMCPTrace:
    @pytest.mark.asyncio
    async def test_add_trace(self, clean_components):
        pg, push, search = clean_components
        doc_a = await push.push_text(title="Source", content="original", scope="shared")
        doc_b = await push.push_text(title="Derived", content="derived from source", scope="shared")
        result = await pg.add_trace(doc_a["id"], doc_b["id"], "derived_from")
        assert result["relation"] == "derived_from"

    @pytest.mark.asyncio
    async def test_trace_chain(self, clean_components):
        pg, push, search = clean_components
        doc_a = await push.push_text(title="A", content="original", scope="shared")
        doc_b = await push.push_text(title="B", content="refined", scope="shared")
        await pg.add_trace(doc_a["id"], doc_b["id"], "refines")
        chain = await pg.get_trace_chain(doc_a["id"], direction="downstream")
        assert len(chain) >= 1


class TestMCPScopeStats:
    @pytest.mark.asyncio
    async def test_scopes(self, clean_components):
        pg, push, search = clean_components
        await push.push_text(title="Doc", content="test", scope="emily", oracle_name="emily")
        scopes = await pg.list_scopes()
        assert len(scopes) >= 1

    @pytest.mark.asyncio
    async def test_stats(self, clean_components):
        pg, push, search = clean_components
        await push.push_text(title="A", content="test a", scope="shared", doc_type="learning")
        stats = await pg.stats()
        assert stats["total_documents"] >= 1

    @pytest.mark.asyncio
    async def test_list_docs(self, clean_components):
        pg, push, search = clean_components
        await push.push_text(title="First", content="content 1", scope="shared")
        await push.push_text(title="Second", content="content 2", scope="shared")
        docs = await pg.list_docs(limit=10)
        assert len(docs) >= 2