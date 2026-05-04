"""Health checks — liveness, readiness, vault stats, embedding availability."""

import logging
import time
from typing import Optional

log = logging.getLogger("synapse.daemon.health")


class HealthChecker:
    """Daemon health monitoring."""

    def __init__(self, daemon_server):
        self._server = daemon_server
        self._start_time: Optional[float] = None

    def mark_started(self):
        """Record daemon start time."""
        self._start_time = time.time()

    def liveness(self) -> dict:
        """Is the daemon process alive?"""
        return {
            "alive": self._server.running,
        }

    def readiness(self) -> dict:
        """Is the daemon ready to serve requests?"""
        if not self._server.running:
            return {"ready": False, "reason": "daemon not running"}

        try:
            config = self._server.config
        except Exception as e:
            return {"ready": False, "reason": f"config error: {e}"}

        return {"ready": True}

    def full_status(self) -> dict:
        """Comprehensive health and status report."""
        uptime = None
        if self._start_time and self._server.running:
            uptime = round(time.time() - self._start_time, 1)

        status = self._server.status()
        status["uptime_seconds"] = uptime
        status["health"] = "ok" if self._server.running else "stopped"

        return status

    def check_embedding(self) -> dict:
        """Check if Ollama embedding is available."""
        try:
            from synapse.embedding import OllamaEmbedder
            embedder = OllamaEmbedder(
                base_url=self._server.config.embedding_base_url,
                model=self._server.config.embedding_model,
                timeout=5,
                max_retries=1,
            )
            # Try a minimal embedding call
            embedder.embed("health check")
            return {"embedding": "available", "model": self._server.config.embedding_model}
        except ImportError:
            return {"embedding": "unavailable", "reason": "httpx not installed"}
        except Exception as e:
            return {"embedding": "unavailable", "reason": str(e)}