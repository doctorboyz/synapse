"""Tests for QdrantStore — mocked AsyncQdrantClient tests."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.db.qdrant_store import QdrantStore


def _make_settings():
    settings = Settings()
    settings.qdrant_url = "http://localhost:6333"
    settings.qdrant_collection = "test_collection"
    settings.embedding_dim = 768
    return settings


def _make_point(doc_id, title="Test", score=0.9, payload=None):
    point = MagicMock()
    point.id = uuid.UUID(doc_id).hex
    point.score = score
    point.payload = payload or {
        "title": title,
        "scope": "shared",
        "doc_type": "learning",
        "superseded": False,
    }
    return point


class TestQdrantStoreConnect:
    @pytest.mark.asyncio
    async def test_connect_creates_collection_if_missing(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(side_effect=Exception("not found"))
            mock_client.create_collection = AsyncMock()
            mock_client.close = AsyncMock()
            MockClient.return_value = mock_client

            await store.connect()
            mock_client.create_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_skips_create_if_exists(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            MockClient.return_value = mock_client

            await store.connect()
            mock_client.create_collection.assert_not_called()


class TestQdrantStoreUpsert:
    @pytest.mark.asyncio
    async def test_upsert_sends_correct_payload(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_client.upsert = AsyncMock()
            MockClient.return_value = mock_client

            await store.connect()
            doc_id = str(uuid.uuid4())
            vector = [0.1] * 768

            await store.upsert(
                doc_id=doc_id, vector=vector, title="Test Doc",
                scope="shared", doc_type="learning",
                oracle_name="emily", brain_tier="extrinsic",
                concepts=["search"],
            )

            mock_client.upsert.assert_called_once()
            call_kwargs = mock_client.upsert.call_args
            assert call_kwargs.kwargs["collection_name"] == "test_collection"
            points = call_kwargs.kwargs["points"]
            assert len(points) == 1
            point = points[0]
            assert point.payload["title"] == "Test Doc"
            assert point.payload["scope"] == "shared"
            assert point.payload["superseded"] is False
            assert point.payload["oracle_name"] == "emily"
            assert point.payload["concepts"] == ["search"]


class TestQdrantStoreSearch:
    @pytest.mark.asyncio
    async def test_search_applies_superseded_filter(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_point = _make_point(str(uuid.uuid4()), title="Result")
            mock_result = MagicMock()
            mock_result.points = [mock_point]
            mock_client.query_points = AsyncMock(return_value=mock_result)
            MockClient.return_value = mock_client

            await store.connect()
            results = await store.search(vector=[0.1] * 768)

            call_kwargs = mock_client.query_points.call_args
            query_filter = call_kwargs.kwargs.get("query_filter")
            assert query_filter is not None
            must_conditions = query_filter.must
            assert any(c.key == "superseded" for c in must_conditions)

    @pytest.mark.asyncio
    async def test_search_applies_scope_and_doc_type_filters(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_point = _make_point(str(uuid.uuid4()), title="Result")
            mock_result = MagicMock()
            mock_result.points = [mock_point]
            mock_client.query_points = AsyncMock(return_value=mock_result)
            MockClient.return_value = mock_client

            await store.connect()
            results = await store.search(
                vector=[0.1] * 768, scope="emily", doc_type="learning",
            )

            call_kwargs = mock_client.query_points.call_args
            query_filter = call_kwargs.kwargs.get("query_filter")
            must_conditions = query_filter.must
            keys = [c.key for c in must_conditions]
            assert "scope" in keys
            assert "doc_type" in keys

    @pytest.mark.asyncio
    async def test_search_applies_source_project_filter(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_point = _make_point(str(uuid.uuid4()), title="Result")
            mock_result = MagicMock()
            mock_result.points = [mock_point]
            mock_client.query_points = AsyncMock(return_value=mock_result)
            MockClient.return_value = mock_client

            await store.connect()
            results = await store.search(
                vector=[0.1] * 768, source_project="emily-oracle",
            )

            call_kwargs = mock_client.query_points.call_args
            query_filter = call_kwargs.kwargs.get("query_filter")
            must_conditions = query_filter.must
            keys = [c.key for c in must_conditions]
            assert "source_project" in keys

    @pytest.mark.asyncio
    async def test_search_applies_concepts_filter(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_point = _make_point(str(uuid.uuid4()), title="Result")
            mock_result = MagicMock()
            mock_result.points = [mock_point]
            mock_client.query_points = AsyncMock(return_value=mock_result)
            MockClient.return_value = mock_client

            await store.connect()
            results = await store.search(
                vector=[0.1] * 768, concepts=["search", "hybrid"],
            )

            call_kwargs = mock_client.query_points.call_args
            query_filter = call_kwargs.kwargs.get("query_filter")
            must_conditions = query_filter.must
            concept_conditions = [c for c in must_conditions if c.key == "concepts"]
            assert len(concept_conditions) == 2


class TestQdrantStoreMarkSuperseded:
    @pytest.mark.asyncio
    async def test_mark_superseded_sets_payload(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_client.set_payload = AsyncMock()
            MockClient.return_value = mock_client

            await store.connect()
            doc_id = str(uuid.uuid4())
            await store.mark_superseded(doc_id)

            mock_client.set_payload.assert_called_once()
            call_kwargs = mock_client.set_payload.call_args
            assert call_kwargs.kwargs["payload"] == {"superseded": True}

    @pytest.mark.asyncio
    async def test_mark_superseded_swallows_exceptions(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_client.set_payload = AsyncMock(side_effect=Exception("connection failed"))
            MockClient.return_value = mock_client

            await store.connect()
            # Should not raise
            await store.mark_superseded(str(uuid.uuid4()))


class TestQdrantStoreDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_point(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_client.delete = AsyncMock()
            MockClient.return_value = mock_client

            await store.connect()
            doc_id = str(uuid.uuid4())
            await store.delete(doc_id)

            mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_swallows_exceptions(self):
        settings = _make_settings()
        store = QdrantStore(settings)

        with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_collection = AsyncMock(return_value=MagicMock())
            mock_client.close = AsyncMock()
            mock_client.delete = AsyncMock(side_effect=Exception("connection failed"))
            MockClient.return_value = mock_client

            await store.connect()
            # Should not raise
            await store.delete(str(uuid.uuid4()))