"""Tests for web search, social search, and topic monitor connectors."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.connectors.web_search import WebSearchConnector, WebSearchResult
from src.connectors.social_search import SocialSearchConnector, SocialSearchResult
from src.connectors.topic_monitor import run_topic_monitor


class TestWebSearchConnector:
    def test_detect_provider_default(self):
        s = Settings()
        s.web_search_provider = ""
        conn = WebSearchConnector(s)
        assert conn.provider == "serper"

    def test_detect_provider_tavily(self):
        s = Settings()
        s.web_search_provider = "tavily"
        conn = WebSearchConnector(s)
        assert conn.provider == "tavily"

    def test_detect_provider_invalid_fallback(self):
        s = Settings()
        s.web_search_provider = "unknown"
        conn = WebSearchConnector(s)
        assert conn.provider == "serper"

    @pytest.mark.asyncio
    async def test_search_serper_success(self):
        s = Settings()
        s.serper_api_key = "test-key"
        conn = WebSearchConnector(s)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={
            "organic": [
                {"title": "T1", "link": "https://example.com/1", "snippet": "S1"},
                {"title": "T2", "link": "https://example.com/2", "snippet": "S2"},
            ]
        })

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await conn.search("test query", limit=5)

        assert len(results) == 2
        assert results[0].title == "T1"
        assert results[0].url == "https://example.com/1"
        assert results[0].snippet == "S1"

    @pytest.mark.asyncio
    async def test_search_serper_no_api_key(self):
        s = Settings()
        s.serper_api_key = ""
        conn = WebSearchConnector(s)
        results = await conn.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_tavily_success(self):
        s = Settings()
        s.web_search_provider = "tavily"
        s.tavily_api_key = "test-key"
        conn = WebSearchConnector(s)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={
            "results": [
                {"title": "T1", "url": "https://example.com/1", "content": "C1"},
            ]
        })

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await conn.search("test query")

        assert len(results) == 1
        assert results[0].title == "T1"
        assert results[0].snippet == "C1"

    @pytest.mark.asyncio
    async def test_fetch_page_success(self):
        s = Settings()
        conn = WebSearchConnector(s)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "<html><body><p>Hello world</p></body></html>"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            text = await conn.fetch_page("https://example.com")

        assert "Hello world" in text

    @pytest.mark.asyncio
    async def test_fetch_page_failure(self):
        s = Settings()
        conn = WebSearchConnector(s)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            text = await conn.fetch_page("https://example.com")

        assert text == ""


class TestSocialSearchConnector:
    @pytest.mark.asyncio
    async def test_search_reddit_success(self):
        s = Settings()
        conn = SocialSearchConnector(s)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={
            "data": {
                "children": [
                    {"data": {"title": "Post 1", "permalink": "/r/test/comments/1", "selftext": "Body", "author": "u1", "created_utc": 1234567890}},
                ]
            }
        })

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await conn.search("reddit", "python", limit=5)

        assert len(results) == 1
        assert results[0].title == "Post 1"
        assert results[0].platform == "reddit"

    @pytest.mark.asyncio
    async def test_search_hackernews_success(self):
        s = Settings()
        conn = SocialSearchConnector(s)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={
            "hits": [
                {"title": "HN Post", "url": "https://example.com", "author": "user1", "created_at": "2024-01-01", "objectID": "123"},
            ]
        })

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await conn.search("hackernews", "startup", limit=5)

        assert len(results) == 1
        assert results[0].title == "HN Post"
        assert results[0].platform == "hackernews"

    @pytest.mark.asyncio
    async def test_search_unknown_platform(self):
        s = Settings()
        conn = SocialSearchConnector(s)
        results = await conn.search("unknown", "test")
        assert results == []


class TestTopicMonitor:
    @pytest.mark.asyncio
    async def test_run_topic_monitor_no_topics(self):
        mock_pg = AsyncMock()
        mock_pg.list_search_topics = AsyncMock(return_value=[])
        mock_push = AsyncMock()

        stats = await run_topic_monitor(mock_pg, mock_push)
        assert stats["topics_checked"] == 0

    @pytest.mark.asyncio
    async def test_run_topic_monitor_web_topic(self):
        mock_pg = AsyncMock()
        mock_pg.list_search_topics = AsyncMock(return_value=[{
            "id": "t1", "scope": "test-scope", "topic": "python async", "source": "web",
        }])
        mock_pg.find_by_source_file = AsyncMock(return_value=None)
        mock_pg.update_search_topic_last_searched = AsyncMock()
        mock_push = AsyncMock()
        mock_push.push_text = AsyncMock(return_value={"status": "indexed"})

        mock_web = AsyncMock()
        mock_web.search = AsyncMock(return_value=[
            WebSearchResult(title="Async Guide", url="https://example.com/async", snippet="Learn async python"),
        ])
        mock_web.fetch_page = AsyncMock(return_value="Full article content here with much more text to exceed the fifty character minimum threshold")

        stats = await run_topic_monitor(
            mock_pg, mock_push,
            web_search=mock_web, social_search=AsyncMock(),
            limit_per_topic=5,
        )

        assert stats["topics_checked"] == 1
        assert stats["results_found"] == 1
        assert stats["indexed"] == 1
        mock_push.push_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_topic_monitor_duplicate_url(self):
        mock_pg = AsyncMock()
        mock_pg.list_search_topics = AsyncMock(return_value=[{
            "id": "t1", "scope": "test-scope", "topic": "python", "source": "web",
        }])
        mock_pg.find_by_source_file = AsyncMock(return_value={"id": "existing"})
        mock_push = AsyncMock()

        mock_web = AsyncMock()
        mock_web.search = AsyncMock(return_value=[
            WebSearchResult(title="Guide", url="https://example.com/guide", snippet="Learn python"),
        ])

        stats = await run_topic_monitor(
            mock_pg, mock_push,
            web_search=mock_web, social_search=AsyncMock(),
        )

        assert stats["duplicates"] == 1
        assert stats["indexed"] == 0
        mock_push.push_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_topic_monitor_short_content_skipped(self):
        mock_pg = AsyncMock()
        mock_pg.list_search_topics = AsyncMock(return_value=[{
            "id": "t1", "scope": "test-scope", "topic": "python", "source": "web",
        }])
        mock_pg.find_by_source_file = AsyncMock(return_value=None)
        mock_push = AsyncMock()

        mock_web = AsyncMock()
        mock_web.search = AsyncMock(return_value=[
            WebSearchResult(title="Short", url="https://example.com/s", snippet="Hi"),
        ])

        stats = await run_topic_monitor(
            mock_pg, mock_push,
            web_search=mock_web, social_search=AsyncMock(),
        )

        assert stats["indexed"] == 0
        mock_push.push_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_topic_monitor_error_handling(self):
        mock_pg = AsyncMock()
        mock_pg.list_search_topics = AsyncMock(return_value=[{
            "id": "t1", "scope": "test-scope", "topic": "python", "source": "web",
        }])
        mock_pg.find_by_source_file = AsyncMock(side_effect=Exception("DB error"))
        mock_push = AsyncMock()

        mock_web = AsyncMock()
        mock_web.search = AsyncMock(return_value=[
            WebSearchResult(title="Guide", url="https://example.com/guide", snippet="Learn python"),
        ])

        stats = await run_topic_monitor(
            mock_pg, mock_push,
            web_search=mock_web, social_search=AsyncMock(),
        )

        assert stats["errors"] == 1
