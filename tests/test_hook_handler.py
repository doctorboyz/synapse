"""Tests for synapse.ingest.hook_handler — auto-index trigger detection."""

from pathlib import Path
from unittest.mock import patch

import pytest

from synapse.ingest.hook_handler import should_process, detect_scope, find_vault, process_file


class TestShouldProcess:
    def test_learnings_file(self):
        assert should_process("/project/learnings/test.md") is True

    def test_retrospectives_file(self):
        assert should_process("/project/retrospectives/2024/01/test.md") is True

    def test_memory_learnings_file(self):
        assert should_process("/project/memory/learnings/test.md") is True

    def test_memory_retrospectives_file(self):
        assert should_process("/project/memory/retrospectives/test.md") is True

    def test_random_file(self):
        assert should_process("/project/src/main.py") is False

    def test_learnings_in_nested_path(self):
        assert should_process("/project/sub/learnings/nested.md") is True

    def test_non_md_extension(self):
        assert should_process("/project/learnings/test.py") is False

    def test_empty_path(self):
        assert should_process("") is False


class TestDetectScope:
    def test_github_pattern(self):
        scope = detect_scope("/Users/dev/Code/github.com/doctorboyz/my-project/src/file.py")
        assert scope == "my-project"

    def test_code_pattern(self):
        scope = detect_scope("/Users/dev/Code/my-project/src/file.py")
        assert scope == "my-project"

    def test_no_match_returns_shared(self):
        scope = detect_scope("/tmp/random/file.py")
        assert scope == "shared"


class TestFindVault:
    def test_find_vault_in_parent(self, tmp_path):
        vault = tmp_path / ".synapse"
        vault.mkdir()
        child = tmp_path / "src" / "file.md"
        child.parent.mkdir(parents=True)
        result = find_vault(child)
        assert result is not None
        assert result.name == ".synapse"

    def test_find_vault_not_found(self, tmp_path):
        child = tmp_path / "src" / "file.md"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.touch()
        result = find_vault(child)
        assert result is None


class TestProcessFile:
    def test_process_nonexistent_file(self):
        result = process_file("/nonexistent/learnings/test.md")
        assert result["status"] in ("file_not_found", "error")

    def test_process_non_trigger_file(self, tmp_path):
        md = tmp_path / "src" / "random.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("# Random\n\nNot a learning file.")
        result = process_file(str(md))
        # Should not be auto-indexed since it's not in learnings/ or retrospectives/
        # May return None or skip
        assert result is None or result.get("status") in ("skipped", "no_vault", "file_not_found", "error")