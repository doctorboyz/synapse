"""Runtime configuration — load, validate, hot-reload config.yaml.

In v1, config.yaml was write-only (created by init, never read).
In v2, config becomes authoritative — the daemon reads settings at runtime.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import yaml

from synapse.exceptions import ConfigError

log = logging.getLogger("synapse.config")

DEFAULT_V1_CONFIG = {
    "version": 1,
    "embedding": {
        "model": "nomic-embed-text",
        "dim": 768,
    },
    "search": {
        "mode": "hybrid",
        "weights": {"dense": 0.6, "fts": 0.4},
    },
    "scope": {
        "default": "shared",
    },
    "retrieval": {
        "priority": "stage2",
        "after": ["CLAUDE.md", ".claude/docs", "psi vault"],
    },
}

DEFAULT_V2_CONFIG = {
    "version": 2,
    "daemon": {
        "host": "127.0.0.1",
        "port": 8321,
        "socket": "~/.synapse/daemon.sock",
        "pid_file": "~/.synapse/daemon.lock",
        "log_level": "INFO",
        "graceful_shutdown_timeout": 30,
    },
    "embedding": {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "dim": 768,
        "timeout": 30,
        "base_url": "http://localhost:11434",
        "batch_size": 1,
    },
    "search": {
        "mode": "hybrid",
        "weights": {"dense": 0.6, "fts": 0.4},
        "cache_ttl": 300,
        "cache_max_size": 1000,
    },
    "scope": {
        "default": "shared",
        "cross_project": True,
    },
    "vault": {
        "path": "~/.synapse",
        "wal_mode": True,
        "busy_timeout": 5000,
    },
    "hooks": {
        "auto_index": True,
        "trigger_paths": ["*/learnings/*.md", "*/retrospectives/*.md"],
        "use_daemon": True,
    },
}


def _expand_path(path: str) -> str:
    """Expand ~ and environment variables in a path string."""
    return os.path.expanduser(os.path.expandvars(path))


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, returning a new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """Synapse runtime configuration.

    Loads from config.yaml, validates, and provides typed access.
    Supports v1 (write-only) and v2 (authoritative) config formats.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._path = config_path
        self._data: dict = {}
        self._version: int = 1
        if config_path and config_path.exists():
            self.load()

    def load(self) -> None:
        """Load and validate config from YAML file."""
        if not self._path or not self._path.exists():
            raise ConfigError(f"Config file not found: {self._path}")

        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config: {e}") from e
        except OSError as e:
            raise ConfigError(f"Failed to read config: {e}") from e

        if not isinstance(raw, dict):
            raise ConfigError(f"Config must be a YAML mapping, got {type(raw).__name__}")

        self._version = raw.get("version", 1)
        self._data = raw
        self._validate()

    def reload(self) -> None:
        """Hot-reload config from disk."""
        self.load()
        log.info("Config reloaded from %s", self._path)

    def _validate(self) -> None:
        """Validate config structure."""
        if self._version not in (1, 2):
            raise ConfigError(f"Unsupported config version: {self._version}")

        if self._version == 2:
            emb = self._data.get("embedding", {})
            dim = emb.get("dim")
            if dim and not isinstance(dim, int):
                raise ConfigError(f"embedding.dim must be an integer, got {type(dim).__name__}")

            weights = self._data.get("search", {}).get("weights", {})
            if weights:
                total = sum(weights.values())
                if abs(total - 1.0) > 0.01:
                    log.warning("Search weights sum to %.2f, expected 1.0", total)

    @property
    def version(self) -> int:
        return self._version

    @property
    def embedding_model(self) -> str:
        return self._data.get("embedding", {}).get("model", "nomic-embed-text")

    @property
    def embedding_dim(self) -> int:
        return self._data.get("embedding", {}).get("dim", 768)

    @property
    def embedding_provider(self) -> str:
        return self._data.get("embedding", {}).get("provider", "ollama")

    @property
    def embedding_timeout(self) -> int:
        return self._data.get("embedding", {}).get("timeout", 30)

    @property
    def embedding_base_url(self) -> str:
        return self._data.get("embedding", {}).get("base_url", "http://localhost:11434")

    @property
    def search_mode(self) -> str:
        return self._data.get("search", {}).get("mode", "hybrid")

    @property
    def search_weights(self) -> dict:
        return self._data.get("search", {}).get("weights", {"dense": 0.6, "fts": 0.4})

    @property
    def cache_ttl(self) -> int:
        return self._data.get("search", {}).get("cache_ttl", 300)

    @property
    def cache_max_size(self) -> int:
        return self._data.get("search", {}).get("cache_max_size", 1000)

    @property
    def scope_default(self) -> str:
        return self._data.get("scope", {}).get("default", "shared")

    @property
    def cross_project(self) -> bool:
        return self._data.get("scope", {}).get("cross_project", True)

    @property
    def vault_path(self) -> str:
        raw = self._data.get("vault", {}).get("path", "~/.synapse")
        return _expand_path(raw)

    @property
    def wal_mode(self) -> bool:
        return self._data.get("vault", {}).get("wal_mode", True)

    @property
    def busy_timeout(self) -> int:
        return self._data.get("vault", {}).get("busy_timeout", 5000)

    @property
    def daemon_host(self) -> str:
        return self._data.get("daemon", {}).get("host", "127.0.0.1")

    @property
    def daemon_port(self) -> int:
        return self._data.get("daemon", {}).get("port", 8321)

    @property
    def daemon_socket(self) -> str:
        raw = self._data.get("daemon", {}).get("socket", "~/.synapse/daemon.sock")
        return _expand_path(raw)

    @property
    def daemon_pid_file(self) -> str:
        raw = self._data.get("daemon", {}).get("pid_file", "~/.synapse/daemon.lock")
        return _expand_path(raw)

    @property
    def daemon_log_level(self) -> str:
        return self._data.get("daemon", {}).get("log_level", "INFO")

    @property
    def daemon_shutdown_timeout(self) -> int:
        return self._data.get("daemon", {}).get("graceful_shutdown_timeout", 30)

    @property
    def hooks_auto_index(self) -> bool:
        return self._data.get("hooks", {}).get("auto_index", True)

    @property
    def hooks_trigger_paths(self) -> list:
        return self._data.get("hooks", {}).get("trigger_paths", ["*/learnings/*.md", "*/retrospectives/*.md"])

    @property
    def hooks_use_daemon(self) -> bool:
        return self._data.get("hooks", {}).get("use_daemon", True)

    def to_dict(self) -> dict:
        """Return config as a plain dictionary."""
        return dict(self._data)

    def merge_with_defaults(self, version: int = 2) -> dict:
        """Merge current config with defaults for the given version."""
        defaults = DEFAULT_V2_CONFIG if version == 2 else DEFAULT_V1_CONFIG
        return _deep_merge(defaults, self._data)