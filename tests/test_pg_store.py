"""Tests for PgStore — CRUD, FTS search, supersession, concepts, trace."""

import pytest
import pytest_asyncio

from src.db.pg_store import PgStore


@pytest.mark.asyncio
class TestPgStoreCRUD:
    async def test_add_document(self, clean_pg):
        result = await clean_pg.add(
            title="Python Tips", content="Use list comprehensions for filtering",
            scope="shared", doc_type="learning",
        )
        assert result["status"] == "indexed"
        assert result["scope"] == "shared"
        assert result["id"]

    async def test_add_duplicate(self, clean_pg):
        await clean_pg.add(title="Test", content="same content", scope="shared")
        result = await clean_pg.add(title="Test", content="same content", scope="shared")
        assert result["status"] == "duplicate"

    async def test_get_document(self, clean_pg):
        add_result = await clean_pg.add(title="Get Test", content="some content", scope="shared")
        doc = await clean_pg.get(add_result["id"])
        assert doc is not None
        assert doc["title"] == "Get Test"
        assert doc["content"] == "some content"

    async def test_get_nonexistent(self, clean_pg):
        doc = await clean_pg.get("00000000-0000-0000-0000-000000000000")
        assert doc is None

    async def test_add_with_oracle_metadata(self, clean_pg):
        result = await clean_pg.add(
            title="Oracle Learning", content="emily discovered this",
            scope="emily", oracle_name="emily",
            brain_path="ψ/memory/learnings/test.md",
            brain_tier="extrinsic",
            source_project="emily-oracle",
        )
        assert result["status"] == "indexed"
        doc = await clean_pg.get(result["id"])
        assert doc["oracle_name"] == "emily"
        assert doc["brain_tier"] == "extrinsic"
        assert doc["source_project"] == "emily-oracle"


@pytest.mark.asyncio
class TestPgStoreFTS:
    async def test_search_basic(self, clean_pg):
        await clean_pg.add(title="Docker Setup", content="Use compose v2 for orchestration", scope="shared")
        await clean_pg.add(title="Python Tips", content="Use list comprehensions", scope="shared")
        results = await clean_pg.search_fts("docker", limit=5)
        assert len(results) >= 1
        assert any("Docker" in r["title"] for r in results)

    async def test_search_with_scope_filter(self, clean_pg):
        await clean_pg.add(title="Shared Doc", content="public knowledge", scope="shared")
        await clean_pg.add(title="Emily Doc", content="private knowledge", scope="emily", oracle_name="emily")
        results = await clean_pg.search_fts("knowledge", scope="emily", limit=10)
        assert len(results) >= 1
        assert all(r["scope"] == "emily" for r in results)

    async def test_search_with_doc_type_filter(self, clean_pg):
        await clean_pg.add(title="Learning", content="learned something", scope="shared", doc_type="learning")
        await clean_pg.add(title="Pattern", content="pattern discovered", scope="shared", doc_type="pattern")
        results = await clean_pg.search_fts("something", doc_type="learning", limit=10)
        assert len(results) >= 1
        assert all(r["doc_type"] == "learning" for r in results)

    async def test_search_excludes_superseded(self, clean_pg):
        add_result = await clean_pg.add(title="Old Doc", content="old knowledge", scope="shared")
        await clean_pg.supersede(add_result["id"], "new and improved knowledge", reason="updated")
        results = await clean_pg.search_fts("old", limit=10)
        # The old doc is superseded (excluded by WHERE superseded_by IS NULL)
        # but the new doc inherits title "Old Doc" which matches "old"
        # So we check that no superseded doc appears in results
        assert all(r["id"] != add_result["id"] for r in results)


@pytest.mark.asyncio
class TestPgStoreSupersede:
    async def test_supersede_creates_new(self, clean_pg):
        add_result = await clean_pg.add(title="Original", content="version 1", scope="shared")
        result = await clean_pg.supersede(add_result["id"], "version 2")
        assert result["status"] == "superseded"
        assert result["superseded"] == add_result["id"]

        old_doc = await clean_pg.get(add_result["id"])
        assert old_doc["superseded_by"] is not None

    async def test_supersede_already_superseded(self, clean_pg):
        add_result = await clean_pg.add(title="Test", content="content", scope="shared")
        await clean_pg.supersede(add_result["id"], "new content")
        with pytest.raises(ValueError, match="already superseded"):
            await clean_pg.supersede(add_result["id"], "another update")


@pytest.mark.asyncio
class TestPgStoreConcepts:
    async def test_add_with_concepts(self, clean_pg):
        result = await clean_pg.add(
            title="Pattern Doc", content="hybrid search pattern",
            scope="shared", concepts=["search", "hybrid"],
        )
        concepts = await clean_pg.list_concepts()
        names = [c["name"] for c in concepts]
        assert "search" in names
        assert "hybrid" in names

    async def test_search_concepts(self, clean_pg):
        await clean_pg.add(
            title="Test", content="content", scope="shared", concepts=["docker-compose"],
        )
        results = await clean_pg.list_concepts(search="docker")
        assert len(results) >= 1
        assert results[0]["name"] == "docker-compose"


@pytest.mark.asyncio
class TestPgStoreTrace:
    async def test_add_trace(self, clean_pg):
        doc_a = await clean_pg.add(title="A", content="source", scope="shared")
        doc_b = await clean_pg.add(title="B", content="derived from A", scope="shared")
        result = await clean_pg.add_trace(doc_a["id"], doc_b["id"], "derived_from")
        assert result["relation"] == "derived_from"

    async def test_trace_chain(self, clean_pg):
        doc_a = await clean_pg.add(title="A", content="original", scope="shared")
        doc_b = await clean_pg.add(title="B", content="refined", scope="shared")
        await clean_pg.add_trace(doc_a["id"], doc_b["id"], "refines")
        chain = await clean_pg.get_trace_chain(doc_a["id"], direction="downstream")
        assert len(chain) >= 1


@pytest.mark.asyncio
class TestPgStoreScopeStats:
    async def test_list_scopes(self, clean_pg):
        await clean_pg.add(title="Doc", content="test", scope="emily", oracle_name="emily")
        scopes = await clean_pg.list_scopes()
        assert len(scopes) >= 1
        assert any(s["name"] == "emily" for s in scopes)

    async def test_stats(self, clean_pg):
        await clean_pg.add(title="A", content="test a", scope="shared", doc_type="learning")
        await clean_pg.add(title="B", content="test b", scope="shared", doc_type="pattern")
        stats = await clean_pg.stats()
        assert stats["total_documents"] >= 2
        assert "learning" in stats["by_type"]

    async def test_list_docs(self, clean_pg):
        await clean_pg.add(title="First", content="content 1", scope="shared")
        await clean_pg.add(title="Second", content="content 2", scope="shared")
        docs = await clean_pg.list_docs(limit=10)
        assert len(docs) >= 2