"""Daemon lifecycle — PID file management, signal handling, status."""

import logging
import os
import signal
import time
from pathlib import Path

log = logging.getLogger("synapse.daemon")

DEFAULT_PID_DIR = Path.home() / ".synapse"


def is_running_in_docker() -> bool:
    """Detect if current process is inside a Docker container."""
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/self/cgroup").read_text(encoding="utf-8")
        return "docker" in cgroup or "containerd" in cgroup
    except (FileNotFoundError, PermissionError):
        return False


def get_docker_container_status(container_name: str = "synapse") -> dict | None:
    """Check if a Docker container is running. Returns status dict or None."""
    if is_running_in_docker():
        return None  # Inside container, can't docker ps from within
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if container_name in line:
                    parts = line.split("\t")
                    return {
                        "container": parts[0] if len(parts) > 0 else container_name,
                        "status": parts[1] if len(parts) > 1 else "unknown",
                        "ports": parts[2] if len(parts) > 2 else "",
                    }
        # Also try legacy name mysynapse
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=mysynapse", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if "mysynapse" in line:
                    parts = line.split("\t")
                    return {
                        "container": parts[0] if len(parts) > 0 else "mysynapse",
                        "status": parts[1] if len(parts) > 1 else "unknown",
                        "ports": parts[2] if len(parts) > 2 else "",
                    }
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass
    return None


def write_pid(pid_path: str | None = None) -> str:
    """Write current PID to file. Returns PID file path."""
    if pid_path is None:
        pid_path = str(DEFAULT_PID_DIR / "synapse.pid")
    Path(pid_path).parent.mkdir(parents=True, exist_ok=True)
    Path(pid_path).write_text(str(os.getpid()), encoding="utf-8")
    log.info("PID %d written to %s", os.getpid(), pid_path)
    return pid_path


def read_pid(pid_path: str | None = None) -> int | None:
    """Read PID from file. Returns None if file doesn't exist or is invalid."""
    if pid_path is None:
        pid_path = str(DEFAULT_PID_DIR / "synapse.pid")
    try:
        return int(Path(pid_path).read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def remove_pid(pid_path: str | None = None) -> None:
    """Remove PID file."""
    if pid_path is None:
        pid_path = str(DEFAULT_PID_DIR / "synapse.pid")
    try:
        Path(pid_path).unlink(missing_ok=True)
        log.info("Removed PID file %s", pid_path)
    except OSError as e:
        log.warning("Failed to remove PID file %s: %s", pid_path, e)


def is_running(pid_path: str | None = None) -> bool:
    """Check if a process with the stored PID is running."""
    pid = read_pid(pid_path)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        # Stale PID file
        remove_pid(pid_path)
        return False
    except PermissionError:
        # Process exists but we can't signal it
        return True


def stop_daemon(pid_path: str | None = None) -> dict:
    """Stop a running daemon by sending SIGTERM, or stop Docker container. Returns status dict."""
    pid = read_pid(pid_path)
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(30):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.5)
                except ProcessLookupError:
                    remove_pid(pid_path)
                    return {"status": "stopped", "pid": pid}
            os.kill(pid, signal.SIGKILL)
            remove_pid(pid_path)
            return {"status": "killed", "pid": pid}
        except ProcessLookupError:
            remove_pid(pid_path)
            return {"status": "not_running", "pid": pid, "message": "Process already stopped"}
        except PermissionError:
            return {"status": "error", "pid": pid, "message": "Permission denied"}

    # No PID file — try stopping Docker container
    docker_status = get_docker_container_status()
    if docker_status and docker_status.get("status", "").startswith("Up"):
        container = docker_status.get("container")
        try:
            import subprocess
            subprocess.run(
                ["docker", "stop", "-t", "30", container],
                capture_output=True, text=True, timeout=35,
            )
            return {"status": "stopped", "mode": "docker", "container": container}
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {"status": "error", "mode": "docker", "container": container, "message": "docker stop failed"}

    return {"status": "not_running", "message": "No PID file found and no Docker container running"}


def get_status(pid_path: str | None = None) -> dict:
    """Get daemon status. Checks PID file first, then Docker fallback."""
    pid = read_pid(pid_path)
    running = is_running(pid_path)
    if running:
        return {
            "running": True,
            "pid": pid,
            "pid_file": pid_path or str(DEFAULT_PID_DIR / "synapse.pid"),
            "mode": "pid",
        }
    # Fallback: check Docker container
    docker_status = get_docker_container_status()
    if docker_status:
        return {
            "running": True,
            "pid": None,
            "pid_file": pid_path or str(DEFAULT_PID_DIR / "synapse.pid"),
            "mode": "docker",
            "container": docker_status.get("container"),
            "container_status": docker_status.get("status"),
        }
    return {
        "running": False,
        "pid": None,
        "pid_file": pid_path or str(DEFAULT_PID_DIR / "synapse.pid"),
        "mode": "none",
    }


def setup_signals(on_reload=None, on_shutdown=None):
    """Set up signal handlers for SIGTERM and SIGHUP."""
    def _handle_shutdown(signum, frame):
        log.info("Received signal %d, shutting down", signum)
        if on_shutdown:
            on_shutdown()

    def _handle_reload(signum, frame):
        log.info("Received SIGHUP, reloading configuration")
        if on_reload:
            on_reload()

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    try:
        signal.signal(signal.SIGHUP, _handle_reload)
    except (OSError, ValueError):
        # SIGHUP not available on Windows
        pass