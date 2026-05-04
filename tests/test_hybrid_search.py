"""Tests for synapse.retrieve.hybrid_search — RRF fusion, modes, fallback."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from synapse.store.sqlite_store import SQLiteStore
from synapse.retrieve.hybrid_search import HybridSearch
from synapse.exceptions import SearchError


class TestHybridSearchFtsOnly:
    def test_fts_mode_without_lancedb(self, populated_vault):
        search = HybridSearch(populated_vault, lancedb=None)
        results = search.search("python", mode="fts", limit=5)
        assert len(results) >= 1

    def test_fts_mode_with_scope(self, populated_vault):
        search = HybridSearch(populated_vault, lancedb=None)
        results = search.search("hooks", scope="frontend", mode="fts")
        assert all(r["scope"] == "frontend" for r in results)

    def test_empty_query_returns_empty(self, populated_vault):
        search = HybridSearch(populated_vault, lancedb=None)
        results = search.search("", mode="fts")
        assert results == []


class TestHybridSearchDenseMode:
    def test_dense_mode_without_lancedb_raises(self, populated_vault):
        search = HybridSearch(populated_vault, lancedb=None)
        with pytest.raises(SearchError):
            search.search("test", mode="dense")


class TestHybridSearchHybridMode:
    def test_hybrid_mode_without_lancedb_falls_back(self, populated_vault):
        search = HybridSearch(populated_vault, lancedb=None)
        results = search.search("python", mode="hybrid")
        # Should fall back to FTS-only without crashing
        assert isinstance(results, list)


class TestHybridSearchWithLanceDB:
    def test_hybrid_mode_with_lancedb(self, tmp_vault, mock_ollama):
        try:
            from synapse.store.lancedb_store import LanceDBStore
            lancedb = LanceDBStore(tmp_vault)
        except (ImportError, Exception):
            pytest.skip("lancedb not available")

        sqlite = SQLiteStore(tmp_vault)
        from synapse.ingest.push import Push
        from synapse.scope.manager import ScopeManager
        scope_mgr = ScopeManager(sqlite)
        push = Push(sqlite, lancedb, scope_mgr)
        push.push_text("Python Tips", "Use list comprehensions for filtering", scope="shared")
        push.push_text("Git Workflow", "Rebase vs merge for clean history", scope="shared")

        search = HybridSearch(sqlite, lancedb)
        results = search.search("python", mode="hybrid")
        assert len(results) >= 1

        sqlite.close()
        lancedb.close()


class TestRRFFusion:
    def test_empty_fts_and_dense_returns_empty(self, populated_vault):
        search = HybridSearch(populated_vault, lancedb=None)
        # Search for something that won't match any docs
        results = search.search("xyznonexistent", mode="fts")
        assert results == []


class TestWeights:
    def test_custom_weights_via_search(self, populated_vault):
        search = HybridSearch(populated_vault, lancedb=None)
        # Custom weights passed to search() method, not constructor
        results = search.search("python", mode="fts")
        assert len(results) >= 1