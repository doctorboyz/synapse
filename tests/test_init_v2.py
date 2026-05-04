"""Tests for synapse.ingest.init — v2 shared vault init."""

import pytest
from pathlib import Path
import yaml

from synapse.ingest.init import init_vault
from synapse.exceptions import VaultAlreadyExistsError


class TestInitV1:
    def test_init_creates_vault(self, tmp_path):
        result = init_vault(tmp_path)
        assert result["status"] == "initialized"
        assert (tmp_path / ".synapse").exists()
        assert (tmp_path / ".synapse" / "vault.db").exists()
        assert (tmp_path / ".synapse" / "vectors").exists()
        assert (tmp_path / ".synapse" / "config.yaml").exists()

    def test_init_with_scope(self, tmp_path):
        result = init_vault(tmp_path, scope="my-project")
        assert result["status"] == "initialized"
        config = yaml.safe_load((tmp_path / ".synapse" / "config.yaml").read_text())
        assert config["scope"]["default"] == "my-project"

    def test_init_creates_gitignore(self, tmp_path):
        init_vault(tmp_path)
        gitignore = (tmp_path / ".gitignore").read_text()
        assert ".synapse/" in gitignore

    def test_init_existing_raises(self, tmp_path):
        init_vault(tmp_path)
        with pytest.raises(VaultAlreadyExistsError):
            init_vault(tmp_path)

    def test_init_v1_config_version(self, tmp_path):
        init_vault(tmp_path)
        config = yaml.safe_load((tmp_path / ".synapse" / "config.yaml").read_text())
        assert config["version"] == 1

    def test_init_v1_result_has_no_shared_flag(self, tmp_path):
        result = init_vault(tmp_path)
        assert result["shared"] is False
        assert result["version"] == 1


class TestInitV2Shared:
    def test_init_shared_creates_v2_config(self, tmp_path):
        result = init_vault(tmp_path, shared=True)
        config = yaml.safe_load((tmp_path / ".synapse" / "config.yaml").read_text())
        assert config["version"] == 2
        assert "daemon" in config
        assert "embedding" in config
        assert "search" in config
        assert "vault" in config
        assert "hooks" in config

    def test_init_shared_has_wal_mode(self, tmp_path):
        result = init_vault(tmp_path, shared=True)
        config = yaml.safe_load((tmp_path / ".synapse" / "config.yaml").read_text())
        assert config["vault"]["wal_mode"] is True

    def test_init_shared_no_gitignore(self, tmp_path):
        result = init_vault(tmp_path, shared=True)
        assert result["gitignore"] is None
        # Should NOT create .gitignore for shared vault
        assert not (tmp_path / ".gitignore").exists() or ".synapse/" not in (tmp_path / ".gitignore").read_text(errors="replace")

    def test_init_shared_result_flags(self, tmp_path):
        result = init_vault(tmp_path, shared=True)
        assert result["shared"] is True
        assert result["version"] == 2

    def test_init_shared_with_scope(self, tmp_path):
        result = init_vault(tmp_path, shared=True, scope="my-project")
        config = yaml.safe_load((tmp_path / ".synapse" / "config.yaml").read_text())
        assert config["scope"]["default"] == "my-project"