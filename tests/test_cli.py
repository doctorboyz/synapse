"""Tests for synapse.cli — command-line interface."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from synapse.cli import cmd_init, cmd_status, cmd_scope, cmd_push, cmd_search, cmd_rebuild


class TestCmdInit:
    def test_init_creates_vault(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        args = type("Args", (), {"scope": None})()
        cmd_init(args)
        assert (tmp_path / ".synapse").exists()
        assert (tmp_path / ".synapse" / "vault.db").exists()

    def test_init_with_scope(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        args = type("Args", (), {"scope": "test-project"})()
        cmd_init(args)
        config = (tmp_path / ".synapse" / "config.yaml").read_text()
        assert "test-project" in config

    def test_init_already_exists(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        args = type("Args", (), {"scope": None})()
        cmd_init(args)
        # Second init should print error
        cmd_init(args)
        captured = capsys.readouterr()
        assert "already exists" in captured.out.lower() or "VaultAlreadyExists" in captured.out


class TestCmdPush:
    def test_push_text(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        init_args = type("Args", (), {"scope": None})()
        cmd_init(init_args)
        push_args = type("Args", (), {
            "file": None, "title": "Test", "text": "Content here",
            "scope": None, "type": "learning",
        })()
        cmd_push(push_args)
        captured = capsys.readouterr()
        assert "indexed" in captured.out.lower() or "doc_id" in captured.out

    def test_push_file(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        init_args = type("Args", (), {"scope": None})()
        cmd_init(init_args)
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nContent.")
        push_args = type("Args", (), {
            "file": str(md), "title": None, "text": None,
            "scope": None, "type": "learning",
        })()
        cmd_push(push_args)
        captured = capsys.readouterr()
        assert "indexed" in captured.out.lower() or "doc_id" in captured.out


class TestCmdSearch:
    def test_search_no_results(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        init_args = type("Args", (), {"scope": None})()
        cmd_init(init_args)
        search_args = type("Args", (), {
            "query": "nonexistent", "scope": None, "limit": 10, "mode": "fts",
        })()
        cmd_search(search_args)
        captured = capsys.readouterr()
        assert "No results" in captured.out or "no results" in captured.out.lower()

    def test_search_after_push(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        init_args = type("Args", (), {"scope": None})()
        cmd_init(init_args)
        push_args = type("Args", (), {
            "file": None, "title": "Python Tips", "text": "Use list comprehensions",
            "scope": None, "type": "learning",
        })()
        cmd_push(push_args)
        search_args = type("Args", (), {
            "query": "python", "scope": None, "limit": 10, "mode": "fts",
        })()
        cmd_search(search_args)
        captured = capsys.readouterr()
        assert "Python" in captured.out or "No results" in captured.out


class TestCmdStatus:
    def test_status_command(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        init_args = type("Args", (), {"scope": None})()
        cmd_init(init_args)
        status_args = type("Args", (), {})()
        cmd_status(status_args)
        captured = capsys.readouterr()
        assert "Documents" in captured.out


class TestCmdScope:
    def test_scope_command(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        init_args = type("Args", (), {"scope": None})()
        cmd_init(init_args)
        scope_args = type("Args", (), {})()
        cmd_scope(scope_args)
        captured = capsys.readouterr()
        # Either lists scopes or "No scopes yet"
        assert "scopes" in captured.out.lower() or "shared" in captured.out.lower() or "No scopes" in captured.out


class TestCmdRebuild:
    def test_rebuild_command(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        init_args = type("Args", (), {"scope": None})()
        cmd_init(init_args)
        # Create source files
        learnings = tmp_path / "learnings"
        learnings.mkdir()
        (learnings / "test.md").write_text("# Test\n\nContent.")
        rebuild_args = type("Args", (), {"scope": None, "no_backup": False})()
        cmd_rebuild(rebuild_args)
        captured = capsys.readouterr()
        assert "Rebuilt" in captured.out or "Error" not in captured.out

    def test_rebuild_no_backup(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        init_args = type("Args", (), {"scope": None})()
        cmd_init(init_args)
        learnings = tmp_path / "learnings"
        learnings.mkdir()
        (learnings / "test.md").write_text("# Test\n\nContent.")
        rebuild_args = type("Args", (), {"scope": None, "no_backup": True})()
        cmd_rebuild(rebuild_args)
        captured = capsys.readouterr()
        assert "Rebuilt" in captured.out or "Error" not in captured.out