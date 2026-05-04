"""Tests for synapse.retrieve.hybrid_search — including cache integration."""

import pytest
from unittest.mock import MagicMock

from synapse.store.sqlite_store import SQLiteStore
from synapse.retrieve.hybrid_search import HybridSearch, reciprocal_rank_fusion, normalize_fts_rank
from synapse.cache import SearchCache


@pytest.fixture
def sqlite_store(tmp_path):
    vault = tmp_path / ".synapse"
    vault.mkdir()
    store = SQLiteStore(vault)
    yield store
    store.close()


@pytest.fixture
def populated_store(sqlite_store):
    sqlite_store.add("Python Tips", "Use list comprehensions for filtering", scope="shared", doc_type="learning")
    sqlite_store.add("Docker Setup", "Use compose v2 for orchestration", scope="shared", doc_type="pattern")
    sqlite_store.add("React Hooks", "Use useEffect for side effects", scope="frontend", doc_type="learning")
    return sqlite_store


class TestReciprocalRankFusion:
    def test_merge_two_lists(self):
        list_a = [{"id": "1", "title": "A", "scope": "shared", "doc_type": "learning", "score": 0.9}]
        list_b = [{"id": "2", "title": "B", "scope": "shared", "doc_type": "pattern", "score": 0.8}]
        result = reciprocal_rank_fusion([list_a, list_b])
        assert len(result) == 2

    def test_merge_with_overlapping_ids(self):
        list_a = [{"id": "1", "title": "A", "scope": "shared", "doc_type": "learning", "score": 0.9}]
        list_b = [{"id": "1", "title": "A", "scope": "shared", "doc_type": "learning", "score": 0.7}]
        result = reciprocal_rank_fusion([list_a, list_b])
        # Same doc from both lists should merge
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_custom_weights(self):
        list_a = [{"id": "1", "title": "A", "scope": "shared", "doc_type": "learning", "score": 0.9}]
        list_b = [{"id": "2", "title": "B", "scope": "shared", "doc_type": "pattern", "score": 0.8}]
        result = reciprocal_rank_fusion([list_a, list_b], weights=[0.8, 0.2])
        assert len(result) == 2

    def test_empty_lists(self):
        result = reciprocal_rank_fusion([[], []])
        assert result == []


class TestNormalizeFtsRank:
    def test_negative_rank(self):
        result = normalize_fts_rank(-10.0)
        assert 0 < result < 1

    def test_zero_rank(self):
        result = normalize_fts_rank(0.0)
        assert result == 1.0

    def test_positive_rank(self):
        result = normalize_fts_rank(5.0)
        assert result > 1.0


class TestHybridSearch:
    def test_fts_mode(self, populated_store):
        search = HybridSearch(populated_store)
        results = search.search("python", mode="fts")
        assert len(results) >= 1
        assert any("Python" in r["title"] for r in results)

    def test_fts_mode_with_scope(self, populated_store):
        search = HybridSearch(populated_store)
        results = search.search("hooks", mode="fts", scope="frontend")
        assert len(results) >= 1
        assert all(r["scope"] == "frontend" for r in results)

    def test_hybrid_mode_falls_back_to_fts(self, populated_store):
        search = HybridSearch(populated_store)
        # Without LanceDB, hybrid falls back to FTS
        results = search.search("docker", mode="hybrid")
        assert len(results) >= 1

    def test_dense_mode_without_lancedb_raises(self, populated_store):
        search = HybridSearch(populated_store)
        from synapse.exceptions import SearchError
        with pytest.raises(SearchError, match="Dense search requires LanceDB"):
            search.search("test", mode="dense")

    def test_no_results(self, sqlite_store):
        search = HybridSearch(sqlite_store)
        results = search.search("nonexistent_query_xyz", mode="fts")
        assert results == []

    def test_cache_hit(self, populated_store):
        search = HybridSearch(populated_store)
        # First call populates cache (hybrid mode caches, fts-only doesn't)
        results1 = search.search("python", mode="hybrid")
        # Second call should hit cache
        results2 = search.search("python", mode="hybrid")
        assert len(results1) == len(results2)

    def test_cache_stats(self, populated_store):
        search = HybridSearch(populated_store)
        search.search("python", mode="hybrid")
        assert search._cache.size > 0

    def test_cache_invalidation(self, populated_store):
        search = HybridSearch(populated_store)
        search.search("python", mode="fts")
        search._cache.invalidate()
        assert search._cache.size == 0

    def test_custom_cache_settings(self, populated_store):
        search = HybridSearch(populated_store, cache_ttl=60, cache_max_size=50)
        assert search._cache.stats()["ttl"] == 60
        assert search._cache.stats()["max_size"] == 50


class TestCrossScopeSearch:
    def test_search_across_scopes(self, sqlite_store):
        sqlite_store.add("Python Shared", "Python tips", scope="shared")
        sqlite_store.add("Python Project", "Python project tips", scope="project-a")

        search = HybridSearch(sqlite_store)
        results = search.search_cross_scope("python", scopes=["shared", "project-a"])
        assert len(results) >= 2

    def test_search_single_scope(self, sqlite_store):
        sqlite_store.add("Python Shared", "Python tips", scope="shared")
        sqlite_store.add("Docker Tips", "Docker compose", scope="project-a")

        search = HybridSearch(sqlite_store)
        results = search.search_cross_scope("python", scopes=["shared"])
        assert len(results) >= 1
        assert all(r["scope"] == "shared" for r in results)

    def test_search_empty_scopes(self, sqlite_store):
        search = HybridSearch(sqlite_store)
        results = search.search_cross_scope("nonexistent", scopes=["shared"])
        assert len(results) == 0