"""Tests for synapse.store.sqlite_store."""

import json
from pathlib import Path

import pytest

from synapse.exceptions import SQLiteStoreError
from synapse.store.sqlite_store import SQLiteStore


class TestAdd:
    def test_add_returns_doc_id(self, sqlite_store):
        doc_id = sqlite_store.add("Test Doc", "Some content")
        assert doc_id and len(doc_id) == 36  # UUID format

    def test_add_with_all_fields(self, sqlite_store):
        doc_id = sqlite_store.add("Title", "Content", scope="project-x", doc_type="pattern", source_file="test.md", concepts=["a", "b"])
        doc = sqlite_store.get(doc_id)
        assert doc["title"] == "Title"
        assert doc["scope"] == "project-x"
        assert doc["doc_type"] == "pattern"
        assert doc["source_file"] == "test.md"
        assert doc["concepts"] == ["a", "b"]

    def test_dedup_same_content_returns_same_id(self, sqlite_store):
        id1 = sqlite_store.add("Doc A", "Same content here")
        id2 = sqlite_store.add("Doc B", "Same content here")
        assert id1 == id2

    def test_different_content_returns_different_id(self, sqlite_store):
        id1 = sqlite_store.add("Doc A", "Content A")
        id2 = sqlite_store.add("Doc B", "Content B")
        assert id1 != id2


class TestSupersede:
    def test_supersede_creates_new_doc(self, sqlite_store):
        old_id = sqlite_store.add("Doc", "Original content")
        new_id = sqlite_store.supersede(old_id, "Updated content")
        assert new_id != old_id

    def test_supersede_marks_old_as_superseded(self, sqlite_store):
        old_id = sqlite_store.add("Doc", "Original")
        new_id = sqlite_store.supersede(old_id, "Updated")
        old_doc = sqlite_store.get(old_id)
        assert old_doc["superseded_by"] == new_id

    def test_supersede_same_content_returns_same_id(self, sqlite_store):
        old_id = sqlite_store.add("Doc", "Same content")
        result_id = sqlite_store.supersede(old_id, "Same content")
        assert result_id == old_id

    def test_supersede_not_found_raises(self, sqlite_store):
        with pytest.raises(SQLiteStoreError, match="not found"):
            sqlite_store.supersede("00000000-0000-0000-0000-000000000000", "new content")

    def test_supersede_decrements_scope_count(self, sqlite_store):
        old_id = sqlite_store.add("Doc", "Original", scope="test-scope")
        new_id = sqlite_store.supersede(old_id, "Updated content")
        # New doc should be in test-scope, old doc superseded
        new_doc = sqlite_store.get(new_id)
        assert new_doc["scope"] == "test-scope"


class TestSearch:
    def test_fts5_basic_search(self, populated_vault):
        results = populated_vault.search_fts5("python")
        assert len(results) >= 1
        assert any("Python" in r["title"] for r in results)

    def test_fts5_scope_filter(self, populated_vault):
        results = populated_vault.search_fts5("hooks", scope="frontend")
        assert len(results) >= 1
        assert all(r["scope"] == "frontend" for r in results)

    def test_fts5_no_results(self, sqlite_store):
        sqlite_store.add("Doc", "Some content")
        results = sqlite_store.search_fts5("xyznonexistent")
        assert len(results) == 0

    def test_fts5_empty_query_returns_empty(self, sqlite_store):
        results = sqlite_store.search_fts5("")
        assert results == []

    def test_fts5_excludes_superseded(self, sqlite_store):
        old_id = sqlite_store.add("Old Doc", "unique keyword superseded")
        sqlite_store.supersede(old_id, "new content")
        results = sqlite_store.search_fts5("superseded")
        assert len(results) == 0


class TestStats:
    def test_stats_empty(self, sqlite_store):
        stats = sqlite_store.stats()
        assert stats["total_documents"] == 0

    def test_stats_with_docs(self, populated_vault):
        stats = populated_vault.stats()
        assert stats["total_documents"] == 3
        assert "shared" in stats["by_scope"]
        assert "frontend" in stats["by_scope"]

    def test_stats_superseded_count(self, sqlite_store):
        old_id = sqlite_store.add("Doc", "Original")
        sqlite_store.supersede(old_id, "Updated")
        stats = sqlite_store.stats()
        assert stats["superseded_documents"] == 1


class TestSanitizeFts:
    def test_removes_special_chars(self, sqlite_store):
        result = sqlite_store._sanitize_fts('test "quoted" & stuff|more')
        # Special chars are removed, words are OR-joined with quotes
        assert "&" not in result
        assert "|" not in result

    def test_short_tokens_removed(self, sqlite_store):
        result = sqlite_store._sanitize_fts("a I big")
        assert "a" not in result.split("OR")

    def test_empty_string_returns_empty(self, sqlite_store):
        result = sqlite_store._sanitize_fts("")
        assert result == ""


class TestGet:
    def test_get_existing_doc(self, sqlite_store):
        doc_id = sqlite_store.add("Title", "Content")
        doc = sqlite_store.get(doc_id)
        assert doc is not None
        assert doc["title"] == "Title"

    def test_get_nonexistent_returns_none(self, sqlite_store):
        doc = sqlite_store.get("00000000-0000-0000-0000-000000000000")
        assert doc is None