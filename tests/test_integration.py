"""Integration tests — E2E daemon lifecycle, v1 compat, config hot-reload, concurrent access."""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from synapse.config import Config, DEFAULT_V2_CONFIG
from synapse.daemon.server import DaemonServer
from synapse.daemon.registry import ProjectRegistry
from synapse.daemon.health import HealthChecker
from synapse.ingest.init import init_vault
from synapse.store.sqlite_store import SQLiteStore
from synapse.retrieve.hybrid_search import HybridSearch
from synapse.scope.manager import ScopeManager


@pytest.fixture
def shared_vault(tmp_path):
    """Create a shared vault at ~/.synapse equivalent."""
    vault = tmp_path / ".synapse"
    vault.mkdir()
    return vault


@pytest.fixture
def shared_config(shared_vault):
    """Create a v2 config for the shared vault."""
    config_path = shared_vault / "config.yaml"
    data = dict(DEFAULT_V2_CONFIG)
    data["daemon"]["pid_file"] = str(shared_vault / "daemon.lock")
    data["daemon"]["socket"] = str(shared_vault / "daemon.sock")
    data["vault"]["path"] = str(shared_vault)
    config_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return Config(config_path)


@pytest.fixture
def shared_store(shared_vault):
    """Create a SQLiteStore for the shared vault."""
    store = SQLiteStore(shared_vault, wal_mode=True)
    yield store
    store.close()


class TestE2EDaemonLifecycle:
    """E2E: daemon start → register → push → search → cross-search → stop"""

    def test_full_lifecycle(self, shared_vault, shared_config):
        # 1. Start daemon
        server = DaemonServer(shared_config)
        server.start(foreground=False)
        assert server.running

        # 2. Register projects
        registry = ProjectRegistry(shared_vault)
        project_a = Path("/tmp/synapse_test_project_a")
        project_b = Path("/tmp/synapse_test_project_b")
        project_a.mkdir(exist_ok=True)
        project_b.mkdir(exist_ok=True)

        reg_a = registry.register(str(project_a), scope="project-a")
        reg_b = registry.register(str(project_b), scope="project-b")
        assert reg_a["scope"] == "project-a"
        assert reg_b["scope"] == "project-b"

        # 3. Push knowledge to shared vault
        store = SQLiteStore(shared_vault, wal_mode=True)
        store.add("Python Tips", "Use list comprehensions for filtering", scope="shared")
        store.add("Docker Setup", "Use compose v2 for orchestration", scope="project-a")
        store.add("React Hooks", "Use useEffect for side effects", scope="project-b")

        # 4. Search within a scope
        search = HybridSearch(store)
        results = search.search("python", scope="shared", mode="fts")
        assert len(results) >= 1
        assert any(r["scope"] == "shared" for r in results)

        # 5. Cross-scope search
        results = search.search_cross_scope("use", scopes=["shared", "project-a", "project-b"])
        assert len(results) >= 2
        scopes_found = {r["scope"] for r in results}
        assert len(scopes_found) >= 2

        # 6. Check health
        checker = HealthChecker(server)
        checker.mark_started()
        status = checker.full_status()
        assert status["running"] is True
        assert status["health"] == "ok"

        # 7. Stop daemon
        server.stop()
        assert not server.running

        store.close()

    def test_status_reflects_projects(self, shared_vault, shared_config):
        server = DaemonServer(shared_config)
        server.start(foreground=False)

        # Register via the server's own registry
        project = Path("/tmp/synapse_status_project")
        project.mkdir(exist_ok=True)
        server._registry.register(str(project), scope="test-project")

        status = server.status()
        assert len(status["projects"]) >= 1
        assert status["projects"][0]["scope"] == "test-project"

        server.stop()


class TestV1BackwardCompat:
    """Per-project vault works without daemon."""

    def test_per_project_init_still_works(self, tmp_path):
        result = init_vault(tmp_path, scope="my-project")
        assert result["status"] == "initialized"
        assert result["shared"] is False
        assert result["version"] == 1

        config = yaml.safe_load((tmp_path / ".synapse" / "config.yaml").read_text())
        assert config["version"] == 1
        assert "daemon" not in config

    def test_per_project_search_still_works(self, tmp_path):
        init_vault(tmp_path)
        vault = tmp_path / ".synapse"
        store = SQLiteStore(vault)
        store.add("Test Doc", "Some content", scope="shared")

        search = HybridSearch(store)
        results = search.search("test", mode="fts")
        assert len(results) >= 1

        store.close()


class TestConfigHotReload:
    """Config hot-reload on SIGHUP."""

    def test_reload_picks_up_changes(self, shared_vault, shared_config):
        server = DaemonServer(shared_config)
        shared_store_path = shared_vault / "vault.db"
        shared_store_path.parent.mkdir(parents=True, exist_ok=True)

        server.start(foreground=False)
        assert server.config.daemon_port == 8321

        # Modify config on disk
        data = dict(DEFAULT_V2_CONFIG)
        data["daemon"]["pid_file"] = str(shared_vault / "daemon.lock")
        data["daemon"]["socket"] = str(shared_vault / "daemon.sock")
        data["vault"]["path"] = str(shared_vault)
        data["daemon"]["port"] = 9999
        config_path = shared_vault / "config.yaml"
        config_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

        server.reload()
        assert server.config.daemon_port == 9999

        server.stop()


class TestConcurrentAccess:
    """SQLite WAL mode supports concurrent reads."""

    def test_concurrent_reads(self, shared_vault):
        store1 = SQLiteStore(shared_vault, wal_mode=True)
        store2 = SQLiteStore(shared_vault, wal_mode=True)

        store1.add("Doc 1", "Content from store1", scope="shared")
        store2.add("Doc 2", "Content from store2", scope="shared")

        # Both stores should see both documents
        stats1 = store1.stats()
        stats2 = store2.stats()
        assert stats1["total_documents"] == 2
        assert stats2["total_documents"] == 2

        store1.close()
        store2.close()

    def test_wal_mode_is_set(self, shared_vault):
        store = SQLiteStore(shared_vault, wal_mode=True)
        result = store._conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"
        store.close()


class TestProjectRegistryPersistence:
    """Registry survives restart."""

    def test_registry_persists_across_instances(self, shared_vault, tmp_path):
        project = tmp_path / "persist-test"
        project.mkdir()

        # Register with first instance
        reg1 = ProjectRegistry(shared_vault)
        reg1.register(str(project), scope="persist-project")

        # Create new instance pointing to same vault
        reg2 = ProjectRegistry(shared_vault)
        projects = reg2.list_projects()
        assert len(projects) == 1
        assert projects[0]["scope"] == "persist-project"

    def test_unregister_persists(self, shared_vault, tmp_path):
        project = tmp_path / "unreg-test"
        project.mkdir()

        reg1 = ProjectRegistry(shared_vault)
        reg1.register(str(project), scope="unreg-project")
        reg1.unregister("unreg-project")

        reg2 = ProjectRegistry(shared_vault)
        assert len(reg2.list_projects()) == 0