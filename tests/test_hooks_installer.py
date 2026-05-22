"""Tests for hook installer and context injection script."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.hooks.installer import (
    SYNAPSE_CONTEXT_MARKER,
    SYNAPSE_INGEST_MARKER,
    build_context_inject_hook_entry,
    build_ingest_hook_entry,
    find_hook_entry,
    install_hooks,
    load_settings,
    save_settings,
)


# ─── load_settings / save_settings ───────────────────────────────────

class TestLoadSaveSettings:
    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "missing.json"
        result = load_settings(path)
        assert result == {}

    def test_load_valid_file(self, tmp_path):
        path = tmp_path / "settings.json"
        data = {"hooks": {"PostToolUse": []}}
        path.write_text(json.dumps(data))
        result = load_settings(path)
        assert result == data

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{invalid json}")
        result = load_settings(path)
        assert result == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "settings.json"
        save_settings({"test": True}, path)
        assert path.exists()
        assert json.loads(path.read_text()) == {"test": True}

    def test_roundtrip(self, tmp_path):
        path = tmp_path / "settings.json"
        original = {"hooks": {"PostToolUse": [{"matcher": "Write", "hooks": []}]}}
        save_settings(original, path)
        loaded = load_settings(path)
        assert loaded == original


# ─── find_hook_entry ─────────────────────────────────────────────────

class TestFindHookEntry:
    def test_find_existing_entry(self):
        hooks = [
            {"matcher": "Write|Edit", "hooks": [{"command": "python -m src.ingest.hook_handler"}]},
            {"matcher": "Read", "hooks": [{"command": "other-script"}]},
        ]
        result = find_hook_entry(hooks, SYNAPSE_INGEST_MARKER)
        assert result is hooks[0]

    def test_find_context_entry(self):
        hooks = [
            {"matcher": "Read|Glob|Grep", "hooks": [{"command": "bash synapse-context-inject.sh"}]},
        ]
        result = find_hook_entry(hooks, SYNAPSE_CONTEXT_MARKER)
        assert result is hooks[0]

    def test_not_found(self):
        hooks = [
            {"matcher": "Write", "hooks": [{"command": "other-script"}]},
        ]
        result = find_hook_entry(hooks, SYNAPSE_INGEST_MARKER)
        assert result is None

    def test_empty_list(self):
        result = find_hook_entry([], SYNAPSE_INGEST_MARKER)
        assert result is None

    def test_entry_without_hooks_key(self):
        hooks = [{"matcher": "Write"}]
        result = find_hook_entry(hooks, SYNAPSE_INGEST_MARKER)
        assert result is None


# ─── build_ingest_hook_entry ──────────────────────────────────────────

class TestBuildIngestHookEntry:
    def test_default_python(self):
        entry = build_ingest_hook_entry()
        assert entry["matcher"] == "Write|Edit|MultiEdit"
        assert len(entry["hooks"]) == 1
        cmd = entry["hooks"][0]["command"]
        assert "src.ingest.hook_handler" in cmd
        assert "CLAUDE_CODE_FILEPATH" in cmd
        assert entry["hooks"][0]["timeout"] == 30

    def test_custom_python(self):
        entry = build_ingest_hook_entry(python_path="/usr/bin/python3")
        cmd = entry["hooks"][0]["command"]
        assert cmd.startswith("/usr/bin/python3")


# ─── build_context_inject_hook_entry ─────────────────────────────────

class TestBuildContextInjectHookEntry:
    def test_default_script_path(self):
        entry = build_context_inject_hook_entry()
        assert entry["matcher"] == "Read|Glob|Grep"
        cmd = entry["hooks"][0]["command"]
        assert "synapse-context-inject.sh" in cmd
        assert entry["hooks"][0]["timeout"] == 5

    def test_custom_script_path(self):
        entry = build_context_inject_hook_entry(script_path="/opt/synapse/inject.sh")
        cmd = entry["hooks"][0]["command"]
        assert "/opt/synapse/inject.sh" in cmd


# ─── install_hooks ────────────────────────────────────────────────────

class TestInstallHooks:
    def test_fresh_install(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        save_settings({}, settings_path)

        result = install_hooks(settings_path=settings_path)
        assert result["ingest_hook"] == "installed"
        assert result["context_hook"] == "installed"
        assert len(result["changes"]) == 2

        settings = load_settings(settings_path)
        post_hooks = settings["hooks"]["PostToolUse"]
        pre_hooks = settings["hooks"]["PreToolUse"]
        assert len(post_hooks) == 1
        assert len(pre_hooks) == 1

    def test_idempotent_install(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        save_settings({}, settings_path)

        result1 = install_hooks(settings_path=settings_path)
        assert result1["ingest_hook"] == "installed"
        assert result1["context_hook"] == "installed"

        result2 = install_hooks(settings_path=settings_path)
        assert result2["ingest_hook"] == "already_exists"
        assert result2["context_hook"] == "already_exists"
        assert len(result2["changes"]) == 0

        settings = load_settings(settings_path)
        assert len(settings["hooks"]["PostToolUse"]) == 1
        assert len(settings["hooks"]["PreToolUse"]) == 1

    def test_dry_run_does_not_write(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        save_settings({}, settings_path)

        result = install_hooks(settings_path=settings_path, dry_run=True)
        assert result["ingest_hook"] == "installed"
        assert result["context_hook"] == "installed"
        assert result.get("dry_run") is True

        settings = load_settings(settings_path)
        assert "hooks" not in settings

    def test_preserves_existing_hooks(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        existing = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Write", "hooks": [{"command": "formatter"}]},
                ],
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"command": "safety-check"}]},
                ],
            }
        }
        save_settings(existing, settings_path)

        install_hooks(settings_path=settings_path)

        settings = load_settings(settings_path)
        assert len(settings["hooks"]["PostToolUse"]) == 2
        assert len(settings["hooks"]["PreToolUse"]) == 2
        # Original hooks preserved
        assert settings["hooks"]["PostToolUse"][0]["matcher"] == "Write"
        assert settings["hooks"]["PreToolUse"][0]["matcher"] == "Bash"

    def test_custom_paths(self, tmp_path):
        settings_path = tmp_path / "settings.json"
        save_settings({}, settings_path)

        result = install_hooks(
            settings_path=settings_path,
            python_path="/opt/python",
            script_path="/opt/inject.sh",
        )
        assert result["ingest_hook"] == "installed"

        settings = load_settings(settings_path)
        cmd = settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        assert cmd.startswith("/opt/python")
        cmd2 = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert "/opt/inject.sh" in cmd2