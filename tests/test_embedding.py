"""Tests for synapse.embedding — OllamaEmbedder sync and async."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from synapse.embedding import OllamaEmbedder
from synapse.exceptions import EmbeddingError


def _mock_response(vectors=None, dim=768):
    """Create a mock httpx response for Ollama embedding API."""
    import random
    if vectors is None:
        vectors = [random.uniform(-0.1, 0.1) for _ in range(dim)]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [vectors]}
    return mock_resp


class TestOllamaEmbedderInit:
    def test_default_settings(self):
        emb = OllamaEmbedder()
        assert emb.model == "nomic-embed-text"
        assert emb.dim == 768
        assert emb.base_url == "http://localhost:11434"
        assert emb.timeout == 30.0
        assert emb.max_retries == 2
        assert emb.batch_size == 1

    def test_custom_settings(self):
        emb = OllamaEmbedder(model="custom-model", dim=1024, base_url="http://ollama:11434", timeout=60, max_retries=3, batch_size=4)
        assert emb.model == "custom-model"
        assert emb.dim == 1024
        assert emb.base_url == "http://ollama:11434"
        assert emb.timeout == 60
        assert emb.max_retries == 3
        assert emb.batch_size == 4

    def test_trailing_slash_stripped(self):
        emb = OllamaEmbedder(base_url="http://localhost:11434/")
        assert emb.base_url == "http://localhost:11434"


class TestEmbedSync:
    def test_embed_returns_vector(self):
        emb = OllamaEmbedder()
        with patch("httpx.post", return_value=_mock_response()):
            result = emb.embed("test text")
        assert isinstance(result, list)
        assert len(result) == 768

    def test_embed_truncates_long_text(self):
        emb = OllamaEmbedder()
        long_text = "x" * 5000
        with patch("httpx.post") as mock_post:
            mock_post.return_value = _mock_response()
            emb.embed(long_text)
            call_text = mock_post.call_args[1]["json"]["input"]
            assert len(call_text) <= 4000

    def test_embed_timeout_raises(self):
        import httpx
        emb = OllamaEmbedder(max_retries=1, timeout=1.0)
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(EmbeddingError, match="timed out"):
                emb.embed("test")

    def test_embed_http_error_raises(self):
        import httpx
        emb = OllamaEmbedder(max_retries=1)
        with patch("httpx.post", side_effect=httpx.HTTPError("connection failed")):
            with pytest.raises(EmbeddingError, match="request failed"):
                emb.embed("test")

    def test_embed_non_200_raises(self):
        emb = OllamaEmbedder(max_retries=1)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(EmbeddingError, match="status 500"):
                emb.embed("test")

    def test_embed_bad_response_format(self):
        emb = OllamaEmbedder(max_retries=1)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"bad": "format"}
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(EmbeddingError, match="response format"):
                emb.embed("test")

    def test_embed_retries_on_timeout(self):
        import httpx
        emb = OllamaEmbedder(max_retries=2)
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timeout")
            return _mock_response()

        with patch("httpx.post", side_effect=side_effect):
            result = emb.embed("test")

        assert call_count == 3
        assert isinstance(result, list)

    def test_embed_uses_custom_base_url(self):
        emb = OllamaEmbedder(base_url="http://custom:1234")
        with patch("httpx.post", return_value=_mock_response()) as mock_post:
            emb.embed("test")
            url = mock_post.call_args[0][0]
            assert url.startswith("http://custom:1234/")


class TestEmbedAsync:
    def test_aembed_returns_vector(self):
        emb = OllamaEmbedder()

        async def _test():
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value.__aenter__ = MagicMock(return_value=mock_client)
                mock_client_cls.return_value.__aexit__ = MagicMock(return_value=None)
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"embeddings": [[0.1] * 768]}
                mock_client.post = MagicMock(return_value=mock_resp)
                # Need async context manager
                mock_client_cls.return_value.__aenter__ = MagicMock(return_value=mock_client)
                mock_client_cls.return_value.__aexit__ = MagicMock(return_value=None)
                result = await emb.aembed("test")
            return result

        # Test aembed directly with mocked httpx
        async def _test_direct():
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"embeddings": [[0.1] * 768]}

            # Create a mock async context manager for AsyncClient
            class MockAsyncClient:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                async def post(self, *args, **kwargs):
                    return mock_resp

            with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
                result = await emb.aembed("test")
            return result

        result = asyncio.get_event_loop().run_until_complete(_test_direct())
        assert isinstance(result, list)
        assert len(result) == 768

    def test_aembed_timeout_raises(self):
        import httpx
        emb = OllamaEmbedder(max_retries=1, timeout=1.0)

        class FailingAsyncClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def post(self, *args, **kwargs):
                raise httpx.TimeoutException("timeout")

        with patch("httpx.AsyncClient", return_value=FailingAsyncClient()):
            with pytest.raises(EmbeddingError, match="timed out"):
                asyncio.get_event_loop().run_until_complete(emb.aembed("test"))


class TestEmbedBatch:
    def test_embed_batch_sequential(self):
        emb = OllamaEmbedder()
        with patch("httpx.post", return_value=_mock_response()):
            results = emb.embed_batch(["text1", "text2"])
        assert len(results) == 2
        assert all(isinstance(r, list) for r in results)

    def test_aembed_batch_concurrent(self):
        emb = OllamaEmbedder(batch_size=2)

        async def _test():
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"embeddings": [[0.1] * 768]}

            class MockAsyncClient:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                async def post(self, *args, **kwargs):
                    return mock_resp

            with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
                results = await emb.aembed_batch(["text1", "text2"])
            return results

        results = asyncio.get_event_loop().run_until_complete(_test())
        assert len(results) == 2