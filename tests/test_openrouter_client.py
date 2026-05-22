"""Tests for OpenRouter client with fallback to Ollama."""

import pytest
from src.llm.openrouter_client import OpenRouterClient, OpenRouterError
from src.config import Settings


class TestOpenRouterClient:
    def test_enabled_when_api_key_present(self):
        settings = Settings()
        settings.openrouter_api_key = "sk-test"
        client = OpenRouterClient(settings)
        assert client.enabled is True

    def test_disabled_when_api_key_empty(self):
        settings = Settings()
        settings.openrouter_api_key = ""
        client = OpenRouterClient(settings)
        assert client.enabled is False

    @pytest.mark.asyncio
    async def test_chat_raises_when_disabled(self):
        settings = Settings()
        settings.openrouter_api_key = ""
        client = OpenRouterClient(settings)
        with pytest.raises(OpenRouterError, match="API key not configured"):
            await client.chat([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_summarize_fallback_to_ollama_when_disabled(self, monkeypatch):
        settings = Settings()
        settings.openrouter_api_key = ""

        async def mock_ollama_summarize(text, settings):
            return "ollama summary"

        monkeypatch.setattr(
            "src.llm.openrouter_client._ollama_summarize",
            mock_ollama_summarize,
        )

        client = OpenRouterClient(settings)
        result = await client.summarize("some long text here", language="thai")
        assert result == "ollama summary"

    @pytest.mark.asyncio
    async def test_ocr_fallback_to_ollama_when_disabled(self, monkeypatch):
        settings = Settings()
        settings.openrouter_api_key = ""

        async def mock_ollama_ocr(image_bytes, settings):
            return "ocr fallback text"

        monkeypatch.setattr(
            "src.llm.openrouter_client._ollama_ocr",
            mock_ollama_ocr,
        )

        client = OpenRouterClient(settings)
        result = await client.ocr_image(b"fake image")
        assert result == "ocr fallback text"


class TestGuessImageExt:
    def test_jpeg(self):
        from src.llm.openrouter_client import _guess_image_ext
        assert _guess_image_ext(b"\xff\xd8") == "jpeg"

    def test_png(self):
        from src.llm.openrouter_client import _guess_image_ext
        assert _guess_image_ext(b"\x89PNG\r\n\x1a\n") == "png"

    def test_gif(self):
        from src.llm.openrouter_client import _guess_image_ext
        assert _guess_image_ext(b"GIF89a") == "gif"

    def test_webp(self):
        from src.llm.openrouter_client import _guess_image_ext
        assert _guess_image_ext(b"RIFF\x00\x00\x00\x00WEBP") == "webp"

    def test_unknown_defaults_to_jpeg(self):
        from src.llm.openrouter_client import _guess_image_ext
        assert _guess_image_ext(b"random bytes") == "jpeg"
