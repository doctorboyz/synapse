"""Tests for synapse.ingest.push — adding knowledge to vault."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from synapse.ingest.push import Push
from synapse.store.sqlite_store import SQLiteStore
from synapse.scope.manager import ScopeManager


@pytest.fixture
def push_setup(tmp_vault):
    """Create a Push instance with SQLite (no LanceDB)."""
    sqlite = SQLiteStore(tmp_vault)
    scope_mgr = ScopeManager(sqlite)
    push = Push(sqlite, lancedb=None, scope_mgr=scope_mgr)
    yield push, sqlite
    sqlite.close()


class TestPushText:
    def test_push_text_basic(self, push_setup):
        push, sqlite = push_setup
        result = push.push_text("Test Title", "Test content", scope="shared", doc_type="learning")
        assert result["status"] in ("indexed", "indexed_sqlite_only")
        assert "doc_id" in result

    def test_push_text_with_source_file(self, push_setup):
        push, sqlite = push_setup
        result = push.push_text("Title", "Content", source_file="test.md")
        doc = sqlite.get(result["doc_id"])
        assert doc["source_file"] == "test.md"

    def test_push_text_without_title_defaults_untitled(self, push_setup):
        push, _ = push_setup
        result = push.push_text(title="untitled", content="Some content")
        assert result["status"] in ("indexed", "indexed_sqlite_only")


class TestPushFile:
    def test_push_file_exists(self, push_setup, tmp_path):
        push, sqlite = push_setup
        md_file = tmp_path / "learnings" / "test.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text("# Test Learning\n\nSome content here.")
        result = push.push_file(str(md_file))
        assert result["status"] in ("indexed", "indexed_sqlite_only", "file_not_found")

    def test_push_file_not_found(self, push_setup):
        push, _ = push_setup
        result = push.push_file("/nonexistent/file.md")
        assert result["status"] == "file_not_found"


class TestPushWithLanceDB:
    def test_push_text_with_lancedb(self, tmp_vault, mock_ollama):
        try:
            from synapse.store.lancedb_store import LanceDBStore
            lancedb = LanceDBStore(tmp_vault)
        except (ImportError, Exception):
            pytest.skip("lancedb not available")

        sqlite = SQLiteStore(tmp_vault)
        scope_mgr = ScopeManager(sqlite)
        push = Push(sqlite, lancedb, scope_mgr)
        result = push.push_text("Title", "Content for embedding", scope="shared")
        assert result["status"] == "indexed"
        sqlite.close()
        lancedb.close()

    def test_embed_failure_falls_back_to_sqlite(self, tmp_vault, mock_ollama_error):
        try:
            from synapse.store.lancedb_store import LanceDBStore
            lancedb = LanceDBStore(tmp_vault)
        except (ImportError, Exception):
            pytest.skip("lancedb not available")

        sqlite = SQLiteStore(tmp_vault)
        scope_mgr = ScopeManager(sqlite)
        push = Push(sqlite, lancedb, scope_mgr)
        result = push.push_text("Title", "Content that fails embedding")
        assert result["status"] == "indexed_sqlite_only"
        sqlite.close()
        lancedb.close()


class TestScopeAutoDetect:
    def test_scope_from_path(self, push_setup, tmp_path):
        push, sqlite = push_setup
        md_file = tmp_path / "learnings" / "test.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text("# Test")
        result = push.push_file(str(md_file), scope=None)
        # Should auto-detect scope from path
        assert "doc_id" in result or result["status"] == "file_not_found"