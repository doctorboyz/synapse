"""Tests for synapse.daemon — server, health, IPC."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from synapse.config import Config, DEFAULT_V2_CONFIG
from synapse.daemon.server import DaemonServer
from synapse.daemon.health import HealthChecker
from synapse.daemon.ipc import IPCClient, IPCServer
from synapse.daemon.registry import ProjectRegistry
from synapse.exceptions import DaemonAlreadyRunningError, DaemonNotRunningError


@pytest.fixture
def config_file(tmp_path):
    """Create a v2 config file for testing."""
    config_path = tmp_path / "config.yaml"
    import yaml
    config_data = dict(DEFAULT_V2_CONFIG)
    config_data["daemon"]["pid_file"] = str(tmp_path / "daemon.lock")
    config_data["daemon"]["socket"] = str(tmp_path / "daemon.sock")
    config_data["vault"]["path"] = str(tmp_path / ".synapse")
    config_path.write_text(yaml.dump(config_data, default_flow_style=False), encoding="utf-8")
    return config_path


@pytest.fixture
def config(config_file):
    """Create a Config instance from the test config file."""
    return Config(config_file)


class TestDaemonServer:
    def test_create_server(self, config):
        server = DaemonServer(config)
        assert not server.running

    def test_start_stop(self, config):
        server = DaemonServer(config)
        # Initialize vault directory
        vault_path = Path(config.vault_path)
        vault_path.mkdir(parents=True, exist_ok=True)

        server.start(foreground=False)
        assert server.running

        server.stop()
        assert not server.running

    def test_stop_not_running_raises(self, config):
        server = DaemonServer(config)
        with pytest.raises(DaemonNotRunningError):
            server.stop()

    def test_status(self, config):
        server = DaemonServer(config)
        vault_path = Path(config.vault_path)
        vault_path.mkdir(parents=True, exist_ok=True)

        server.start(foreground=False)
        status = server.status()
        assert status["running"] is True
        assert status["pid"] == os.getpid()

        server.stop()

    def test_start_already_running_raises(self, config):
        server = DaemonServer(config)
        vault_path = Path(config.vault_path)
        vault_path.mkdir(parents=True, exist_ok=True)

        server.start(foreground=False)
        try:
            # Second start should fail
            server2 = DaemonServer(config)
            with pytest.raises(DaemonAlreadyRunningError):
                server2.start(foreground=False)
        finally:
            server.stop()

    def test_reload(self, config):
        server = DaemonServer(config)
        vault_path = Path(config.vault_path)
        vault_path.mkdir(parents=True, exist_ok=True)

        server.start(foreground=False)
        # Reload should not raise
        server.reload()
        server.stop()


class TestHealthChecker:
    def test_liveness(self, config):
        server = DaemonServer(config)
        vault_path = Path(config.vault_path)
        vault_path.mkdir(parents=True, exist_ok=True)

        checker = HealthChecker(server)
        assert checker.liveness()["alive"] is False

        server.start(foreground=False)
        assert checker.liveness()["alive"] is True
        server.stop()

    def test_readiness_not_running(self, config):
        server = DaemonServer(config)
        checker = HealthChecker(server)
        result = checker.readiness()
        assert result["ready"] is False

    def test_full_status(self, config):
        server = DaemonServer(config)
        vault_path = Path(config.vault_path)
        vault_path.mkdir(parents=True, exist_ok=True)

        checker = HealthChecker(server)
        server.start(foreground=False)
        checker.mark_started()

        status = checker.full_status()
        assert status["health"] == "ok"
        assert status["uptime_seconds"] is not None
        assert status["uptime_seconds"] >= 0

        server.stop()


class TestIPCServer:
    def test_start_stop(self, tmp_path):
        # Use /tmp for short Unix socket paths (macOS limit ~104 bytes)
        socket_path = "/tmp/synapse_test.sock"
        handler = lambda req: {"status": "ok"}
        server = IPCServer(socket_path, handler)
        server.start()
        assert Path(socket_path).exists()
        server.stop()
        assert not Path(socket_path).exists()

    def test_serve_one(self, tmp_path):
        import threading
        socket_path = "/tmp/synapse_test_serve.sock"

        def handler(request):
            return {"status": "ok", "action": request.get("action")}

        server = IPCServer(socket_path, handler)
        server.start()

        # Run serve_one in a background thread
        def serve():
            server.serve_one()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()

        try:
            client = IPCClient(socket_path, timeout=5.0)
            response = client.call("search", {"query": "test"})
            assert response["status"] == "ok"
            assert response["action"] == "search"
            thread.join(timeout=5)
        finally:
            server.stop()

    def test_invalid_json(self, tmp_path):
        import threading
        socket_path = "/tmp/synapse_test_invalid.sock"
        handler = lambda req: {"status": "ok"}
        server = IPCServer(socket_path, handler)
        server.start()

        def serve():
            server.serve_one()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()

        try:
            import socket as sock_mod
            sock = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
            sock.connect(socket_path)
            sock.sendall(b"not json\n")
            data = sock.recv(65536)
            response = json.loads(data.decode().strip())
            assert response["status"] == "error"
            sock.close()
            thread.join(timeout=5)
        finally:
            server.stop()


class TestIPCClient:
    def test_is_available_no_socket(self, tmp_path):
        client = IPCClient("/tmp/synapse_nonexistent_test.sock")
        assert client.is_available() is False

    def test_is_available_with_server(self, tmp_path):
        socket_path = "/tmp/synapse_test_avail.sock"
        server = IPCServer(socket_path, lambda req: {"status": "ok"})
        server.start()

        try:
            client = IPCClient(socket_path)
            assert client.is_available() is True
        finally:
            server.stop()


class TestProjectRegistry:
    def test_register_and_list(self, tmp_path):
        vault = tmp_path / ".synapse"
        vault.mkdir()
        registry = ProjectRegistry(vault)

        project = tmp_path / "myproject"
        project.mkdir()
        registry.register(str(project))

        projects = registry.list_projects()
        assert len(projects) == 1
        assert projects[0]["scope"] == "myproject"

    def test_unregister(self, tmp_path):
        vault = tmp_path / ".synapse"
        vault.mkdir()
        registry = ProjectRegistry(vault)

        project = tmp_path / "myproject"
        project.mkdir()
        registry.register(str(project))
        registry.unregister("myproject")

        assert len(registry.list_projects()) == 0