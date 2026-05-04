"""Daemon server lifecycle — start, stop, reload, PID file management.

The daemon runs as a background process, listening for IPC requests
on a Unix socket. It manages the shared vault and serves cross-project
queries.
"""

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from synapse.config import Config
from synapse.daemon.registry import ProjectRegistry
from synapse.exceptions import (
    DaemonAlreadyRunningError,
    DaemonNotRunningError,
)

log = logging.getLogger("synapse.daemon.server")


class DaemonServer:
    """Synapse daemon — persistent service for cross-project knowledge.

    Manages a shared vault at ~/.synapse/ with:
    - SQLite store (WAL mode for concurrent access)
    - Project registry (projects.yaml)
    - Config (config.yaml, hot-reloadable on SIGHUP)
    """

    def __init__(self, config: Optional[Config] = None):
        self._config = config
        self._running = False
        self._registry: Optional[ProjectRegistry] = None
        self._pid_file: Optional[str] = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def config(self) -> Config:
        if self._config is None:
            from synapse.ingest.init import init_vault
            config_path = Path.home() / ".synapse" / "config.yaml"
            self._config = Config(config_path) if config_path.exists() else Config()
        return self._config

    def start(self, foreground: bool = False) -> None:
        """Start the daemon.

        Args:
            foreground: If True, run in foreground (for debugging).
        """
        pid_path = self.config.daemon_pid_file

        # Check if already running
        if self._is_running(pid_path):
            existing_pid = Path(pid_path).read_text().strip()
            raise DaemonAlreadyRunningError(
                f"Daemon already running (PID {existing_pid})"
            )

        # Write PID file
        Path(pid_path).parent.mkdir(parents=True, exist_ok=True)
        Path(pid_path).write_text(str(os.getpid()), encoding="utf-8")
        self._pid_file = pid_path

        # Initialize registry
        vault_path = Path(self.config.vault_path)
        self._registry = ProjectRegistry(vault_path)

        self._running = True
        log.info("Synapse daemon started (PID %d)", os.getpid())

        # Register signal handlers for graceful shutdown and reload
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        try:
            signal.signal(signal.SIGHUP, self._handle_reload)
        except (OSError, ValueError):
            # SIGHUP not available on Windows or non-main thread
            pass

        if foreground:
            self._run_foreground()
        # If not foreground, caller manages the event loop

    def stop(self) -> None:
        """Stop the daemon gracefully."""
        if not self._running:
            raise DaemonNotRunningError("Daemon is not running")

        log.info("Stopping Synapse daemon")
        self._running = False

        # Clean up PID file
        if self._pid_file and Path(self._pid_file).exists():
            Path(self._pid_file).unlink()
            self._pid_file = None

        log.info("Daemon stopped")

    def reload(self) -> None:
        """Hot-reload configuration."""
        if self._config:
            self._config.reload()
            log.info("Configuration reloaded")

    def status(self) -> dict:
        """Get daemon status."""
        return {
            "running": self._running,
            "pid": os.getpid() if self._running else None,
            "vault_path": self.config.vault_path,
            "config_version": self.config.version,
            "projects": self._registry.list_projects() if self._registry else [],
        }

    def _is_running(self, pid_path: str) -> bool:
        """Check if another daemon instance is running."""
        pid_file = Path(pid_path)
        if not pid_file.exists():
            return False

        try:
            pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            # Corrupt PID file, clean it up
            pid_file.unlink(missing_ok=True)
            return False

        # Check if process is alive
        try:
            os.kill(pid, 0)  # Signal 0 = just check if process exists
            return True
        except ProcessLookupError:
            # Process not found, stale PID file
            pid_file.unlink(missing_ok=True)
            return False
        except PermissionError:
            # Process exists but we can't signal it
            return True

    def _handle_signal(self, signum, frame):
        """Handle SIGTERM and SIGINT."""
        log.info("Received signal %d, shutting down", signum)
        try:
            self.stop()
        except DaemonNotRunningError:
            pass

    def _handle_reload(self, signum, frame):
        """Handle SIGHUP — reload config."""
        log.info("Received SIGHUP, reloading configuration")
        try:
            self.reload()
        except Exception as e:
            log.error("Failed to reload config: %s", e)

    def _run_foreground(self):
        """Run in foreground, blocking until stopped."""
        log.info("Running in foreground mode")
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self.stop()
            except DaemonNotRunningError:
                pass