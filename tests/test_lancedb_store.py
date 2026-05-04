"""Tests for synapse.store.lancedb_store — chunking, scope validation.

LanceDB-dependent tests are skipped if lancedb is not installed.
Ollama is mocked at httpx.post level so tests run without Ollama.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from synapse.exceptions import EmbeddingError, ScopeError


# Check if lancedb is available
try:
    import lancedb as _lancedb
    HAS_LANCEDB = True
except ImportError:
    HAS_LANCEDB = False


skip_no_lancedb = pytest.mark.skipif(not HAS_LANCEDB, reason="lancedb not installed")


class TestChunkText:
    def _chunk(self, text, max_chars=4000, overlap=200):
        """Helper to call _chunk_text without needing LanceDBStore instance."""
        from synapse.store.lancedb_store import LanceDBStore
        # Create a minimal mock-like instance
        store = MagicMock(spec=LanceDBStore)
        store.embedding_dim = 768
        return LanceDBStore._chunk_text(store, text, max_chars=max_chars, overlap=overlap)

    def test_short_text_single_chunk(self):
        chunks = self._chunk("Short text", max_chars=100)
        assert chunks == ["Short text"]

    def test_long_text_multiple_chunks(self):
        text = "\n\n".join(["Paragraph " * 100 for _ in range(5)])
        chunks = self._chunk(text, max_chars=500)
        assert len(chunks) > 1

    def test_empty_paragraphs_handled(self):
        text = "\n\n\n\n"
        chunks = self._chunk(text, max_chars=100)
        assert len(chunks) >= 1

    def test_overlap_between_chunks(self):
        text = "A" * 300 + "\n\n" + "B" * 300
        chunks = self._chunk(text, max_chars=200, overlap=50)
        assert len(chunks) >= 2


class TestValidateScope:
    def test_valid_scope(self):
        from synapse.store.lancedb_store import LanceDBStore
        assert LanceDBStore._validate_scope("shared") == "shared"
        assert LanceDBStore._validate_scope("my-project") == "my-project"
        assert LanceDBStore._validate_scope("project_v2") == "project_v2"

    def test_invalid_scope_raises(self):
        from synapse.store.lancedb_store import LanceDBStore
        with pytest.raises(ScopeError):
            LanceDBStore._validate_scope("UPPERCASE")
        with pytest.raises(ScopeError):
            LanceDBStore._validate_scope("has spaces")
        with pytest.raises(ScopeError):
            LanceDBStore._validate_scope("1starts-with-number")

    def test_scope_injection_raises(self):
        from synapse.store.lancedb_store import LanceDBStore
        with pytest.raises(ScopeError):
            LanceDBStore._validate_scope("'; DROP TABLE--")


@skip_no_lancedb
class TestEmbedWithLanceDB:
    def test_embed_ollama_success(self, tmp_vault, mock_ollama):
        from synapse.store.lancedb_store import LanceDBStore
        store = LanceDBStore(tmp_vault)
        vector = store._embed("test text")
        assert len(vector) == 768
        mock_ollama.assert_called_once()
        store.close()

    def test_embed_ollama_timeout(self, tmp_vault, mock_ollama_timeout):
        from synapse.store.lancedb_store import LanceDBStore
        store = LanceDBStore(tmp_vault)
        with pytest.raises(EmbeddingError, match="timed out"):
            store._embed("test text")
        store.close()

    def test_embed_ollama_http_error(self, tmp_vault, mock_ollama_error):
        from synapse.store.lancedb_store import LanceDBStore
        store = LanceDBStore(tmp_vault)
        with pytest.raises(EmbeddingError, match="request failed"):
            store._embed("test text")
        store.close()

    def test_embed_ollama_non_200(self, tmp_vault):
        from synapse.store.lancedb_store import LanceDBStore
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("synapse.store.lancedb_store.httpx.post", return_value=mock_resp):
            store = LanceDBStore(tmp_vault)
            with pytest.raises(EmbeddingError, match="500"):
                store._embed("test text")
            store.close()

    def test_embed_ollama_bad_response_format(self, tmp_vault):
        from synapse.store.lancedb_store import LanceDBStore
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # missing 'embeddings' key
        with patch("synapse.store.lancedb_store.httpx.post", return_value=mock_resp):
            store = LanceDBStore(tmp_vault)
            with pytest.raises(EmbeddingError, match="Unexpected"):
                store._embed("test text")
            store.close()


@skip_no_lancedb
class TestAddAndSearch:
    def test_add_creates_records(self, tmp_vault, mock_ollama):
        from synapse.store.lancedb_store import LanceDBStore
        store = LanceDBStore(tmp_vault)
        store.add("doc1", "Test Title", "Test content for embedding")
        table = store._db.open_table("knowledge")
        df = table.to_pandas()
        assert len(df) >= 1
        store.close()

    def test_search_returns_results(self, tmp_vault, mock_ollama):
        from synapse.store.lancedb_store import LanceDBStore
        store = LanceDBStore(tmp_vault)
        store.add("doc1", "Test Title", "Test content for embedding")
        results = store.search("test query")
        assert isinstance(results, list)
        store.close()

    def test_add_with_embed_failure_skips_chunk(self, tmp_vault, mock_ollama_error):
        from synapse.store.lancedb_store import LanceDBStore
        store = LanceDBStore(tmp_vault)
        # Should not raise — chunk is skipped gracefully
        store.add("doc1", "Title", "Content that fails embedding")
        store.close()


@skip_no_lancedb
class TestLanceDBStats:
    def test_stats_empty(self, tmp_vault, mock_ollama):
        from synapse.store.lancedb_store import LanceDBStore
        store = LanceDBStore(tmp_vault)
        stats = store.stats()
        assert stats["total_vectors"] == 0
        assert stats["embedding_dim"] == 768
        store.close()

    def test_stats_after_add(self, tmp_vault, mock_ollama):
        from synapse.store.lancedb_store import LanceDBStore
        store = LanceDBStore(tmp_vault)
        store.add("doc1", "Title", "Content for vectorization")
        stats = store.stats()
        assert stats["total_vectors"] >= 1
        store.close()


class TestNoLanceDB:
    def test_import_flag_exists(self):
        from synapse.store.lancedb_store import HAS_LANCEDB
        assert isinstance(HAS_LANCEDB, bool)

    def test_init_raises_when_not_installed(self, tmp_vault):
        if HAS_LANCEDB:
            pytest.skip("lancedb is installed, cannot test missing case")
        from synapse.store.lancedb_store import LanceDBStore
        from synapse.exceptions import LanceDBStoreError
        with pytest.raises(LanceDBStoreError):
            LanceDBStore(tmp_vault)