"""Tests for hook_handler — oracle brain path detection and auto-ingest."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from src.ingest.hook_handler import is_oracle_brain_path, find_oracle_root


class TestIsOracleBrainPath:
    def test_psi_path(self, tmp_path):
        f = tmp_path / "emily-oracle" / "ψ" / "memory" / "learnings" / "test.md"
        assert is_oracle_brain_path(str(f)) is True

    def test_kappa_path(self, tmp_path):
        f = tmp_path / "pm-oracle" / "κ" / "intrinsic" / "instinct" / "oracle.md"
        assert is_oracle_brain_path(str(f)) is True

    def test_plain_path(self, tmp_path):
        f = tmp_path / "src" / "main.py"
        assert is_oracle_brain_path(str(f)) is False

    def test_unicode_in_filename_not_path(self, tmp_path):
        f = tmp_path / "regular" / "README.md"
        assert is_oracle_brain_path(str(f)) is False


class TestFindOracleRoot:
    def test_finds_claude_md(self, tmp_path):
        oracle_dir = tmp_path / "emily-oracle"
        oracle_dir.mkdir()
        (oracle_dir / "CLAUDE.md").write_text("# Emily Oracle", encoding="utf-8")
        brain_file = oracle_dir / "ψ" / "memory" / "learnings" / "test.md"
        brain_file.parent.mkdir(parents=True)

        result = find_oracle_root(str(brain_file))
        assert result is not None
        assert Path(result).name == "emily-oracle"

    def test_no_claude_md(self, tmp_path):
        f = tmp_path / "some" / "deep" / "path.md"
        f.parent.mkdir(parents=True)
        result = find_oracle_root(str(f))
        assert result is None


class TestIngestFile:
    @pytest.mark.asyncio
    async def test_ingest_psi_file(self, tmp_path, clean_pg):
        oracle_dir = tmp_path / "emily-oracle"
        oracle_dir.mkdir()
        (oracle_dir / "CLAUDE.md").write_text("# Emily Oracle", encoding="utf-8")
        brain_file = oracle_dir / "ψ" / "memory" / "learnings" / "pattern.md"
        brain_file.parent.mkdir(parents=True)
        brain_file.write_text("RRF fusion is effective for hybrid search", encoding="utf-8")

        from src.ingest.hook_handler import ingest_file

        # Mock Qdrant/Ollama to avoid needing running services
        with patch("src.ingest.hook_handler.QdrantStore") as MockQdrant, \
             patch("src.ingest.hook_handler.OllamaEmbedder") as MockEmbedder:
            MockQdrant.return_value = AsyncMock()
            MockQdrant.return_value.connect = AsyncMock(side_effect=Exception("no qdrant"))
            MockEmbedder.return_value = AsyncMock()

            await ingest_file(str(brain_file))

        # Verify document was pushed to PostgreSQL
        docs = await clean_pg.search_fts("RRF fusion", limit=5)
        assert len(docs) >= 1

    @pytest.mark.asyncio
    async def test_skip_non_oracle_path(self, tmp_path, clean_pg):
        plain_file = tmp_path / "src" / "main.py"
        plain_file.parent.mkdir(parents=True)
        plain_file.write_text("print('hello')", encoding="utf-8")

        from src.ingest.hook_handler import ingest_file

        await ingest_file(str(plain_file))

        # Nothing should be ingested
        docs = await clean_pg.search_fts("hello", limit=5)
        assert len(docs) == 0

    @pytest.mark.asyncio
    async def test_skip_missing_file(self, clean_pg):
        from src.ingest.hook_handler import ingest_file

        await ingest_file("/nonexistent/path/file.md")
        # Should not raise, just silently skip

    @pytest.mark.asyncio
    async def test_graceful_qdrant_failure(self, tmp_path, clean_pg):
        oracle_dir = tmp_path / "test-oracle"
        oracle_dir.mkdir()
        (oracle_dir / "CLAUDE.md").write_text("# Test", encoding="utf-8")
        brain_file = oracle_dir / "ψ" / "memory" / "learnings" / "note.md"
        brain_file.parent.mkdir(parents=True)
        brain_file.write_text("Test content for hook handler", encoding="utf-8")

        from src.ingest.hook_handler import ingest_file

        with patch("src.ingest.hook_handler.QdrantStore") as MockQdrant, \
             patch("src.ingest.hook_handler.OllamaEmbedder") as MockEmbedder:
            MockQdrant.return_value = AsyncMock()
            MockQdrant.return_value.connect = AsyncMock(side_effect=Exception("no qdrant"))
            MockEmbedder.return_value = AsyncMock()
            MockEmbedder.return_value.check = AsyncMock(return_value=False)

            await ingest_file(str(brain_file))

        # Should still be indexed in PG even without Qdrant/Ollama
        docs = await clean_pg.search_fts("hook handler", limit=5)
        assert len(docs) >= 1


class TestMainEntrypoint:
    def test_empty_argv_exits_silently(self, monkeypatch):
        """Regression: empty CLI arg from $CLAUDE_CODE_FILEPATH should exit 0, not error."""
        monkeypatch.setattr("sys.argv", ["hook_handler", ""])
        monkeypatch.delenv("CLAUDE_CODE_FILEPATH", raising=False)

        from src.ingest.hook_handler import main

        with patch("src.ingest.hook_handler.json.load", side_effect=json.JSONDecodeError("", "", 0)):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_missing_file_path_exits_silently(self, monkeypatch):
        """No file path available at all should exit 0 silently."""
        monkeypatch.setattr("sys.argv", ["hook_handler"])
        monkeypatch.delenv("CLAUDE_CODE_FILEPATH", raising=False)

        from src.ingest.hook_handler import main

        with patch("src.ingest.hook_handler.json.load", side_effect=json.JSONDecodeError("", "", 0)):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0