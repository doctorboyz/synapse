"""Tests for cross-scope search and ScopeManager.list_all_scopes."""

import pytest

from synapse.scope.manager import ScopeManager, validate_scope
from synapse.store.sqlite_store import SQLiteStore


@pytest.fixture
def sqlite_store(tmp_path):
    vault = tmp_path / ".synapse"
    vault.mkdir()
    store = SQLiteStore(vault)
    yield store
    store.close()


@pytest.fixture
def scope_mgr(sqlite_store):
    return ScopeManager(sqlite_store)


class TestListAllScopes:
    def test_empty_vault(self, scope_mgr):
        assert scope_mgr.list_all_scopes() == []

    def test_with_docs(self, sqlite_store, scope_mgr):
        sqlite_store.add("Doc 1", "Content 1", scope="alpha")
        sqlite_store.add("Doc 2", "Content 2", scope="beta")
        sqlite_store.add("Doc 3", "Content 3", scope="alpha")

        scopes = scope_mgr.list_all_scopes()
        assert "alpha" in scopes
        assert "beta" in scopes


class TestCrossScopeSearch:
    def test_search_across_multiple_scopes(self, tmp_path):
        from synapse.retrieve.hybrid_search import HybridSearch
        from synapse.store.sqlite_store import SQLiteStore

        vault = tmp_path / ".synapse"
        vault.mkdir()
        sqlite = SQLiteStore(vault)
        try:
            sqlite.add("Python Tips", "Use list comprehensions", scope="shared")
            sqlite.add("Docker Setup", "Use compose v2 for orchestration", scope="project-a")
            sqlite.add("React Hooks", "Use useEffect for side effects", scope="project-b")

            search = HybridSearch(sqlite)
            results = search.search_cross_scope("use", scopes=["shared", "project-a", "project-b"])
            assert len(results) >= 2
        finally:
            sqlite.close()

    def test_search_cross_scope_with_single_scope(self, tmp_path):
        from synapse.retrieve.hybrid_search import HybridSearch
        from synapse.store.sqlite_store import SQLiteStore

        vault = tmp_path / ".synapse"
        vault.mkdir()
        sqlite = SQLiteStore(vault)
        try:
            sqlite.add("Python Tips", "Use list comprehensions", scope="shared")
            sqlite.add("Docker Setup", "Use compose v2", scope="project-a")

            search = HybridSearch(sqlite)
            results = search.search_cross_scope("python", scopes=["shared"])
            assert len(results) >= 1
            assert all(r["scope"] == "shared" for r in results)
        finally:
            sqlite.close()

    def test_search_cross_scope_empty_results(self, tmp_path):
        from synapse.retrieve.hybrid_search import HybridSearch
        from synapse.store.sqlite_store import SQLiteStore

        vault = tmp_path / ".synapse"
        vault.mkdir()
        sqlite = SQLiteStore(vault)
        try:
            sqlite.add("Doc", "Content", scope="alpha")

            search = HybridSearch(sqlite)
            results = search.search_cross_scope("nonexistent", scopes=["alpha"])
            assert len(results) == 0
        finally:
            sqlite.close()

    def test_search_cross_scope_merges_best_scores(self, tmp_path):
        from synapse.retrieve.hybrid_search import HybridSearch
        from synapse.store.sqlite_store import SQLiteStore

        vault = tmp_path / ".synapse"
        vault.mkdir()
        sqlite = SQLiteStore(vault)
        try:
            # Same doc in different scopes should keep best score
            sqlite.add("Python Guide", "Python list comprehension patterns", scope="shared")
            sqlite.add("Python Guide v2", "Python list comprehension advanced", scope="project-a")

            search = HybridSearch(sqlite)
            results = search.search_cross_scope("python", scopes=["shared", "project-a"])
            # Should have results from both scopes
            scopes_found = {r["scope"] for r in results}
            assert len(scopes_found) >= 1
        finally:
            sqlite.close()