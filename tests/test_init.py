"""Tests for synapse.ingest.init — vault initialization."""

import os
from pathlib import Path

import pytest
import yaml

from synapse.exceptions import VaultAlreadyExistsError
from synapse.ingest.init import init_vault


class TestInit:
    def test_fresh_init(self, tmp_path):
        result = init_vault(tmp_path)
        assert result["vault"].endswith(".synapse")
        assert (tmp_path / ".synapse" / "vault.db").exists()
        assert (tmp_path / ".synapse" / "config.yaml").exists()
        assert (tmp_path / ".synapse" / "vectors").exists()

    def test_init_creates_gitignore_entry(self, tmp_path):
        init_vault(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".synapse/" in content

    def test_init_with_scope(self, tmp_path):
        result = init_vault(tmp_path, scope="my-project")
        config_path = tmp_path / ".synapse" / "config.yaml"
        config = yaml.safe_load(config_path.read_text())
        assert config["scope"]["default"] == "my-project"

    def test_init_already_exists_raises(self, tmp_path):
        init_vault(tmp_path)
        with pytest.raises(VaultAlreadyExistsError):
            init_vault(tmp_path)

    def test_config_yaml_contents(self, tmp_path):
        init_vault(tmp_path, scope="test-scope")
        config_path = tmp_path / ".synapse" / "config.yaml"
        config = yaml.safe_load(config_path.read_text())
        assert "scope" in config
        assert config["scope"]["default"] == "test-scope"

    def test_vault_db_is_valid_sqlite(self, tmp_path):
        import sqlite3
        init_vault(tmp_path)
        db_path = tmp_path / ".synapse" / "vault.db"
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        assert "knowledge_documents" in table_names
        conn.close()