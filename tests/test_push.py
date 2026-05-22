"""Integration tests — Push pipeline with dual-store write and oracle path detection."""

import pytest

from src.ingest.oracle_paths import extract_metadata


@pytest.mark.asyncio
class TestPushPipeline:
    async def test_push_text_basic(self, push, clean_pg):
        result = await push.push_text(
            title="Docker Setup", content="Use compose v2 for orchestration",
            scope="shared", doc_type="learning",
        )
        assert result["status"] == "indexed"
        assert result["scope"] == "shared"

    async def test_push_text_with_oracle_metadata(self, push, clean_pg):
        result = await push.push_text(
            title="Pattern Found", content="RRF fusion works well",
            scope="emily", doc_type="pattern",
            oracle_name="emily", brain_path="ψ/memory/learnings/pattern-001.md",
            brain_tier="extrinsic", source_project="emily-oracle",
        )
        assert result["status"] == "indexed"
        doc = await clean_pg.get(result["id"])
        assert doc["oracle_name"] == "emily"
        assert doc["brain_tier"] == "extrinsic"
        assert doc["source_project"] == "emily-oracle"

    async def test_push_text_with_concepts(self, push, clean_pg):
        result = await push.push_text(
            title="Search Patterns", content="hybrid search combines dense and keyword",
            scope="shared", concepts=["search", "hybrid", "fusion"],
        )
        assert result["status"] == "indexed"
        doc = await clean_pg.get(result["id"])
        assert "search" in doc["concepts"]

    async def test_push_duplicate(self, push, clean_pg):
        r1 = await push.push_text(title="Test", content="same content here", scope="shared")
        r2 = await push.push_text(title="Test Again", content="same content here", scope="shared")
        assert r1["status"] == "indexed"
        assert r2["status"] == "duplicate"
        assert r1["id"] == r2["id"]

    async def test_push_different_scope_same_content(self, push, clean_pg):
        r1 = await push.push_text(title="A", content="unique content", scope="shared")
        r2 = await push.push_text(title="B", content="unique content", scope="emily")
        assert r1["status"] == "indexed"
        assert r2["status"] == "indexed"
        assert r1["id"] != r2["id"]

    async def test_push_without_embed(self, push, clean_pg):
        result = await push.push_text(
            title="FTS Only", content="this is keyword searchable",
            scope="shared", embed=False,
        )
        assert result["status"] == "indexed"

    async def test_push_text_source_type_default(self, push, clean_pg):
        result = await push.push_text(title="Manual", content="manual push", scope="shared")
        doc = await clean_pg.get(result["id"])
        assert doc["source_type"] == "manual"

    async def test_push_text_webhook_source(self, push, clean_pg):
        result = await push.push_text(
            title="Webhook", content="from external project",
            scope="maw-js", source_type="webhook", source_project="maw-js",
        )
        doc = await clean_pg.get(result["id"])
        assert doc["source_type"] == "webhook"
        assert doc["source_project"] == "maw-js"


class TestPushOraclePathDetection:
    def test_extract_from_learnings(self):
        meta = extract_metadata(
            "/Users/doctorboyz/Code/github.com/doctorboyz/emily-oracle/ψ/memory/learnings/pattern-001.md",
            "/Users/doctorboyz/Code/github.com/doctorboyz/emily-oracle",
        )
        assert meta["doc_type"] == "learning"
        assert meta["oracle_name"] == "emily"
        assert meta["brain_tier"] == "extrinsic"

    def test_extract_from_retrospectives(self):
        meta = extract_metadata(
            "/code/broky-oracle/ψ/memory/retrospectives/2026/05/test.md",
            "/code/broky-oracle",
        )
        assert meta["doc_type"] == "retro"
        assert meta["oracle_name"] == "broky"

    def test_extract_from_kappa_intrinsic(self):
        meta = extract_metadata(
            "/code/pm-oracle/κ/intrinsic/instinct/oracle.md",
            "/code/pm-oracle",
        )
        assert meta["doc_type"] == "instinct"
        assert meta["brain_tier"] == "intrinsic"

    def test_extract_from_outbox(self):
        meta = extract_metadata(
            "/code/emily-oracle/ψ/outbox/MSG-001.md",
            "/code/emily-oracle",
        )
        assert meta["doc_type"] == "handoff"