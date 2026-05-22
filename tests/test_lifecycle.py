"""Tests for FastAPI app lifecycle — startup, shutdown, graceful degradation."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.main import app
import src.main as main_mod


class TestAppLifecycle:
    @pytest.mark.asyncio
    async def test_startup_connects_pg(self):
        saved_pg = main_mod._pg
        saved_qdrant = main_mod._qdrant
        try:
            with patch("src.main.PgStore") as MockPg, \
                 patch("src.main.QdrantStore") as MockQdrant, \
                 patch("src.main.OllamaEmbedder") as MockEmbedder, \
                 patch("src.main.init_routes") as mock_init, \
                 patch("src.registry.restore_registry_backup", new_callable=AsyncMock) as mock_restore:

                mock_pg = AsyncMock()
                mock_pg.connect = AsyncMock()
                mock_pg.init_schema = AsyncMock()
                MockPg.return_value = mock_pg

                MockQdrant.return_value = AsyncMock()
                MockQdrant.return_value.connect = AsyncMock(side_effect=Exception("no qdrant"))

                MockEmbedder.return_value = MagicMock()

                await main_mod.startup()

                mock_pg.connect.assert_called_once()
                mock_pg.init_schema.assert_called_once()
                mock_init.assert_called_once()
                mock_restore.assert_called_once()
        finally:
            main_mod._pg = saved_pg
            main_mod._qdrant = saved_qdrant

    @pytest.mark.asyncio
    async def test_startup_graceful_qdrant_failure(self):
        saved_pg = main_mod._pg
        saved_qdrant = main_mod._qdrant
        try:
            with patch("src.main.PgStore") as MockPg, \
                 patch("src.main.QdrantStore") as MockQdrant, \
                 patch("src.main.OllamaEmbedder") as MockEmbedder, \
                 patch("src.main.init_routes"), \
                 patch("src.registry.restore_registry_backup", new_callable=AsyncMock):

                mock_pg = AsyncMock()
                mock_pg.connect = AsyncMock()
                mock_pg.init_schema = AsyncMock()
                MockPg.return_value = mock_pg

                mock_qdrant = AsyncMock()
                mock_qdrant.connect = AsyncMock(side_effect=Exception("connection refused"))
                MockQdrant.return_value = mock_qdrant

                MockEmbedder.return_value = MagicMock()

                await main_mod.startup()

                assert main_mod._qdrant is None
        finally:
            main_mod._pg = saved_pg
            main_mod._qdrant = saved_qdrant

    @pytest.mark.asyncio
    async def test_shutdown_closes_pg(self):
        saved_pg = main_mod._pg
        saved_qdrant = main_mod._qdrant
        try:
            main_mod._pg = AsyncMock()
            main_mod._pg.close = AsyncMock()
            main_mod._qdrant = None

            await main_mod.shutdown()

            main_mod._pg.close.assert_called_once()
        finally:
            main_mod._pg = saved_pg
            main_mod._qdrant = saved_qdrant

    @pytest.mark.asyncio
    async def test_shutdown_closes_qdrant_when_present(self):
        saved_pg = main_mod._pg
        saved_qdrant = main_mod._qdrant
        try:
            main_mod._pg = AsyncMock()
            main_mod._pg.close = AsyncMock()
            main_mod._qdrant = AsyncMock()
            main_mod._qdrant.close = AsyncMock()

            await main_mod.shutdown()

            main_mod._pg.close.assert_called_once()
            main_mod._qdrant.close.assert_called_once()
        finally:
            main_mod._pg = saved_pg
            main_mod._qdrant = saved_qdrant

    @pytest.mark.asyncio
    async def test_health_endpoint_no_qdrant(self, api_client, clean_pg):
        resp = await api_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["qdrant"] is False

    @pytest.mark.asyncio
    async def test_app_has_router(self):
        routes = [r.path for r in app.routes]
        assert "/api/health" in routes
        assert "/api/search" in routes
        assert "/api/push" in routes