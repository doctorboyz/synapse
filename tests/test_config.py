"""Tests for synapse.config — load, validate, merge, hot-reload."""

import copy

import pytest
import yaml
from pathlib import Path

from synapse.config import Config, DEFAULT_V1_CONFIG, DEFAULT_V2_CONFIG, _deep_merge, _expand_path
from synapse.exceptions import ConfigError


class TestConfigLoad:
    def test_load_v1_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(DEFAULT_V1_CONFIG, default_flow_style=False), encoding="utf-8")
        cfg = Config(config_file)
        assert cfg.version == 1
        assert cfg.embedding_model == "nomic-embed-text"
        assert cfg.embedding_dim == 768
        assert cfg.search_mode == "hybrid"

    def test_load_v2_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(DEFAULT_V2_CONFIG, default_flow_style=False), encoding="utf-8")
        cfg = Config(config_file)
        assert cfg.version == 2
        assert cfg.daemon_host == "127.0.0.1"
        assert cfg.daemon_port == 8321
        assert cfg.wal_mode is True
        assert cfg.hooks_auto_index is True

    def test_load_nonexistent_raises(self, tmp_path):
        cfg = Config(tmp_path / "nonexistent.yaml")
        with pytest.raises(ConfigError, match="not found"):
            cfg.load()

    def test_load_invalid_yaml_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("{{invalid yaml", encoding="utf-8")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            Config(config_file)

    def test_load_non_dict_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="mapping"):
            Config(config_file)


class TestConfigValidate:
    def test_unsupported_version_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("version: 99\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="Unsupported config version"):
            Config(config_file)

    def test_embedding_dim_must_be_int(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        data = copy.deepcopy(DEFAULT_V2_CONFIG)
        data["embedding"]["dim"] = "not-a-number"
        config_file.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        with pytest.raises(ConfigError, match="integer"):
            Config(config_file)

    def test_search_weights_warning(self, tmp_path, caplog):
        config_file = tmp_path / "config.yaml"
        data = copy.deepcopy(DEFAULT_V2_CONFIG)
        data["search"]["weights"] = {"dense": 0.5, "fts": 0.3}
        config_file.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        cfg = Config(config_file)
        # Just a warning, should not raise
        assert cfg.version == 2


class TestConfigProperties:
    def test_defaults_from_v2_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(DEFAULT_V2_CONFIG, default_flow_style=False), encoding="utf-8")
        cfg = Config(config_file)
        assert cfg.embedding_provider == "ollama"
        assert cfg.embedding_timeout == 30
        assert cfg.embedding_base_url == "http://localhost:11434"
        assert cfg.cache_ttl == 300
        assert cfg.cache_max_size == 1000
        assert cfg.cross_project is True
        assert cfg.busy_timeout == 5000
        assert cfg.daemon_socket.endswith("daemon.sock")
        assert cfg.daemon_pid_file.endswith("daemon.lock")
        assert cfg.daemon_log_level == "INFO"
        assert cfg.daemon_shutdown_timeout == 30

    def test_v1_config_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(DEFAULT_V1_CONFIG, default_flow_style=False), encoding="utf-8")
        cfg = Config(config_file)
        assert cfg.version == 1
        # v2 properties should fall back to defaults
        assert cfg.daemon_host == "127.0.0.1"
        assert cfg.daemon_port == 8321
        assert cfg.wal_mode is True

    def test_path_expansion(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(DEFAULT_V2_CONFIG, default_flow_style=False), encoding="utf-8")
        cfg = Config(config_file)
        assert "~" not in cfg.vault_path
        assert "~" not in cfg.daemon_socket
        assert "~" not in cfg.daemon_pid_file

    def test_to_dict(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(DEFAULT_V2_CONFIG, default_flow_style=False), encoding="utf-8")
        cfg = Config(config_file)
        d = cfg.to_dict()
        assert isinstance(d, dict)
        assert d["version"] == 2


class TestConfigReload:
    def test_reload_picks_up_changes(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(DEFAULT_V2_CONFIG, default_flow_style=False), encoding="utf-8")
        cfg = Config(config_file)
        assert cfg.daemon_port == 8321

        # Modify config on disk
        modified = copy.deepcopy(DEFAULT_V2_CONFIG)
        modified["daemon"]["port"] = 9999
        config_file.write_text(yaml.dump(modified, default_flow_style=False), encoding="utf-8")

        cfg.reload()
        assert cfg.daemon_port == 9999


class TestDeepMerge:
    def test_shallow_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"embedding": {"model": "a", "dim": 768}}
        override = {"embedding": {"dim": 1024}}
        result = _deep_merge(base, override)
        assert result == {"embedding": {"model": "a", "dim": 1024}}

    def test_merge_with_defaults_v2(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("version: 2\ndaemon:\n  port: 9999\n", encoding="utf-8")
        cfg = Config(config_file)
        merged = cfg.merge_with_defaults(version=2)
        assert merged["daemon"]["port"] == 9999
        assert merged["daemon"]["host"] == "127.0.0.1"  # from defaults
        assert merged["embedding"]["model"] == "nomic-embed-text"  # from defaults


class TestExpandPath:
    def test_expand_home(self):
        result = _expand_path("~/.synapse")
        assert "~" not in result
        assert result.startswith("/")

    def test_expand_env_var(self):
        import os
        os.environ["SYNAPSE_TEST_VAR"] = "/test/path"
        result = _expand_path("$SYNAPSE_TEST_VAR/vault")
        assert result == "/test/path/vault"
        del os.environ["SYNAPSE_TEST_VAR"]

    def test_no_expansion_needed(self):
        result = _expand_path("/absolute/path")
        assert result == "/absolute/path"