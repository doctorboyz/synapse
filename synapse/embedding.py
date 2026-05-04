"""OllamaEmbedder — sync and async embedding with retry, timeout, batching.

Extracted from LanceDBStore so the embedding logic can be reused
by the daemon's async path without duplicating httpx calls.
"""

import asyncio
import logging
from typing import Optional

from synapse.exceptions import EmbeddingError

log = logging.getLogger("synapse.embedding")

MAX_CHUNK_CHARS = 4000


class OllamaEmbedder:
    """Embed text via local Ollama nomic-embed-text model.

    Supports both synchronous and asynchronous embedding calls,
    with retry logic, timeout, and optional batching.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        dim: int = 768,
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
        max_retries: int = 2,
        batch_size: int = 1,
    ):
        self.model = model
        self.dim = dim
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.batch_size = batch_size

    def embed(self, text: str) -> list[float]:
        """Get embedding vector for a single text (synchronous)."""
        if len(text) > MAX_CHUNK_CHARS:
            text = text[:MAX_CHUNK_CHARS]

        try:
            import httpx
        except ImportError:
            raise EmbeddingError("httpx not installed. Run: pip install httpx")

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = httpx.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": text},
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as e:
                last_error = EmbeddingError(f"Ollama embedding timed out (attempt {attempt + 1}): {e}")
                continue
            except httpx.HTTPError as e:
                last_error = EmbeddingError(f"Ollama embedding request failed (attempt {attempt + 1}): {e}")
                continue

            if resp.status_code != 200:
                last_error = EmbeddingError(f"Ollama returned status {resp.status_code}: {resp.text[:200]}")
                continue

            try:
                return resp.json()["embeddings"][0]
            except (KeyError, IndexError) as e:
                last_error = EmbeddingError(f"Unexpected Ollama response format: {e}")
                continue

        raise last_error or EmbeddingError("Ollama embedding failed after retries")

    async def aembed(self, text: str) -> list[float]:
        """Get embedding vector for a single text (asynchronous)."""
        if len(text) > MAX_CHUNK_CHARS:
            text = text[:MAX_CHUNK_CHARS]

        try:
            import httpx
        except ImportError:
            raise EmbeddingError("httpx not installed. Run: pip install httpx")

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/api/embed",
                        json={"model": self.model, "input": text},
                    )
            except httpx.TimeoutException as e:
                last_error = EmbeddingError(f"Ollama embedding timed out (async attempt {attempt + 1}): {e}")
                continue
            except httpx.HTTPError as e:
                last_error = EmbeddingError(f"Ollama embedding request failed (async attempt {attempt + 1}): {e}")
                continue

            if resp.status_code != 200:
                last_error = EmbeddingError(f"Ollama returned status {resp.status_code}: {resp.text[:200]}")
                continue

            try:
                return resp.json()["embeddings"][0]
            except (KeyError, IndexError) as e:
                last_error = EmbeddingError(f"Unexpected Ollama response format: {e}")
                continue

        raise last_error or EmbeddingError("Ollama embedding failed after retries")

    async def aembed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embedding vectors for multiple texts (asynchronous, concurrent)."""
        semaphore = asyncio.Semaphore(self.batch_size)

        async def _embed_with_semaphore(text: str) -> list[float]:
            async with semaphore:
                return await self.aembed(text)

        tasks = [_embed_with_semaphore(t) for t in texts]
        return await asyncio.gather(*tasks)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embedding vectors for multiple texts (synchronous, sequential)."""
        return [self.embed(t) for t in texts]