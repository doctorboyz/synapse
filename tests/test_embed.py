"""Tests for OllamaEmbedder — mocked HTTP calls."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from src.embed.ollama import OllamaEmbedder, EmbeddingError


def _make_http_error(msg="connection error"):
    request = MagicMock()
    return httpx.HTTPStatusError(msg, request=request, response=MagicMock(status_code=500))


def _mock_response(data=None, raise_error=None):
    resp = MagicMock()
    if raise_error:
        resp.raise_for_status = MagicMock(side_effect=raise_error)
    else:
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=data or {"embeddings": [[0.1] * 768]})
    return resp


@pytest.mark.asyncio
class TestOllamaEmbedder:
    async def test_embed_success(self):
        embedder = OllamaEmbedder()
        with patch("src.embed.ollama.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.post = AsyncMock(return_value=_mock_response())
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = client
            result = await embedder.embed("test query")
            assert len(result) == 768

    async def test_embed_retry(self):
        embedder = OllamaEmbedder()
        embedder._max_retries = 1
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_response(raise_error=_make_http_error())
            return _mock_response()

        with patch("src.embed.ollama.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.post = mock_post
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = client
            result = await embedder.embed("test query")
            assert len(result) == 768
            assert call_count == 2

    async def test_embed_all_retries_fail(self):
        embedder = OllamaEmbedder()
        embedder._max_retries = 0
        with patch("src.embed.ollama.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.post = AsyncMock(return_value=_mock_response(raise_error=_make_http_error("fail")))
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = client
            with pytest.raises(EmbeddingError):
                await embedder.embed("test query")

    async def test_embed_truncates_long_text(self):
        embedder = OllamaEmbedder()
        long_text = "x" * 10000
        sent_texts = []

        async def capture_post(url, json=None, **kwargs):
            sent_texts.append(json["input"])
            return _mock_response()

        with patch("src.embed.ollama.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.post = capture_post
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = client
            await embedder.embed(long_text)
            assert len(sent_texts[0]) <= 4000