"""IPC — Unix socket client/server for daemon tool calls.

Protocol: JSON request/response over Unix domain socket.
Each message is a JSON object terminated by a newline.

Request:  {"action": "search", "params": {"query": "...", "scope": "..."}}
Response: {"status": "ok", "data": {...}}
Error:    {"status": "error", "error": "message"}
"""

import json
import logging
import os
import socket
from pathlib import Path
from typing import Optional

log = logging.getLogger("synapse.daemon.ipc")

BUFFER_SIZE = 65536


class IPCServer:
    """Unix socket server for daemon IPC."""

    def __init__(self, socket_path: str, handler):
        self._socket_path = socket_path
        self._handler = handler  # Callable that processes request dicts
        self._server_socket: Optional[socket.socket] = None

    def start(self) -> None:
        """Start listening on the Unix socket."""
        # Remove stale socket
        Path(self._socket_path).unlink(missing_ok=True)
        Path(self._socket_path).parent.mkdir(parents=True, exist_ok=True)

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(self._socket_path)
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)  # Allow periodic interrupt checks
        log.info("IPC server listening on %s", self._socket_path)

    def serve_one(self) -> Optional[dict]:
        """Accept and handle one connection. Returns the response or None on timeout."""
        if self._server_socket is None:
            raise RuntimeError("IPC server not started")

        try:
            conn, _ = self._server_socket.accept()
        except socket.timeout:
            return None

        try:
            data = conn.recv(BUFFER_SIZE).decode("utf-8").strip()
            if not data:
                return None

            request = json.loads(data)
            response = self._handler(request)
            conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
            return response
        except json.JSONDecodeError as e:
            error_response = {"status": "error", "error": f"Invalid JSON: {e}"}
            conn.sendall((json.dumps(error_response) + "\n").encode("utf-8"))
            return error_response
        except Exception as e:
            error_response = {"status": "error", "error": str(e)}
            conn.sendall((json.dumps(error_response) + "\n").encode("utf-8"))
            return error_response
        finally:
            conn.close()

    def stop(self) -> None:
        """Stop the IPC server."""
        if self._server_socket:
            self._server_socket.close()
            self._server_socket = None
        Path(self._socket_path).unlink(missing_ok=True)
        log.info("IPC server stopped")


class IPCClient:
    """Unix socket client for daemon IPC."""

    def __init__(self, socket_path: str, timeout: float = 30.0):
        self._socket_path = socket_path
        self._timeout = timeout

    def call(self, action: str, params: Optional[dict] = None) -> dict:
        """Send a request to the daemon and return the response.

        Args:
            action: Action name (e.g., "search", "push", "status")
            params: Action parameters

        Returns:
            Response dict from the daemon.
        """
        request = {"action": action}
        if params:
            request["params"] = params

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self._timeout)

        try:
            sock.connect(self._socket_path)
            sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

            data = b""
            while True:
                chunk = sock.recv(BUFFER_SIZE)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            response = json.loads(data.decode("utf-8").strip())
            return response
        except FileNotFoundError:
            raise ConnectionError(f"Daemon socket not found: {self._socket_path}")
        except socket.timeout:
            raise ConnectionError(f"Daemon request timed out after {self._timeout}s")
        finally:
            sock.close()

    def is_available(self) -> bool:
        """Check if the daemon socket exists and is connectable."""
        if not Path(self._socket_path).exists():
            return False
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(self._socket_path)
            sock.close()
            return True
        except (ConnectionError, FileNotFoundError, OSError):
            return False