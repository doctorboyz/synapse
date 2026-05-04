"""Tests for synapse.scope.manager — scope detection, validation, listing."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from synapse.exceptions import ScopeError
from synapse.scope.manager import ScopeManager, detect_scope, validate_scope
from synapse.store.sqlite_store import SQLiteStore


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

    def test_learnings_path(self):
        scope = detect_scope("/Users/dev/Code/github.com/doctorboyz/project/learnings/test.md")
        assert scope == "project"

    def test_retrospectives_path(self):
        scope = detect_scope("/Users/dev/Code/github.com/doctorboyz/project/retrospectives/2024/test.md")
        assert scope == "project"


class TestValidateScope:
    def test_valid_scopes(self):
        assert validate_scope("shared") is True
        assert validate_scope("my-project") is True
        assert validate_scope("project-v2") is True

    def test_invalid_scopes(self):
        assert validate_scope("UPPERCASE") is False
        assert validate_scope("has spaces") is False
        assert validate_scope("1starts-with-number") is False
        assert validate_scope("'; DROP TABLE--") is False


class TestScopeManager:
    def test_list_scopes_empty(self, sqlite_store):
        mgr = ScopeManager(sqlite_store)
        scopes = mgr.list_scopes()
        assert isinstance(scopes, list)

    def test_list_scopes_with_docs(self, populated_vault):
        mgr = ScopeManager(populated_vault)
        scopes = mgr.list_scopes()
        scope_names = [s["name"] for s in scopes]
        assert "shared" in scope_names
        assert "frontend" in scope_names


class TestResolvePriority:
    def test_explicit_scope_overrides_detected(self, sqlite_store):
        mgr = ScopeManager(sqlite_store)
        resolved = mgr.resolve_scope("/some/path", explicit_scope="my-scope")
        assert resolved == "my-scope"

    def test_detected_scope_when_no_explicit(self, sqlite_store):
        mgr = ScopeManager(sqlite_store)
        resolved = mgr.resolve_scope("/Code/github.com/doctorboyz/test-project/file.md")
        assert resolved == "test-project"

    def test_shared_when_no_info(self, sqlite_store):
        mgr = ScopeManager(sqlite_store)
        resolved = mgr.resolve_scope("/tmp/random/file.md")
        assert resolved == "shared"

    def test_invalid_explicit_scope_raises(self, sqlite_store):
        mgr = ScopeManager(sqlite_store)
        with pytest.raises(ScopeError):
            mgr.resolve_scope("/some/path", explicit_scope="UPPERCASE")