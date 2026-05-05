"""Test configuration — uses Docker postgres on ai-server."""

import os

import pytest
import pytest_asyncio

from src.config import Settings
from src.db.pg_store import PgStore

TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:88888888@localhost:5432/mysynapse",
)

# Module-level store, created per-event-loop
_pg_store: PgStore | None = None
_schema_initialized = False


@pytest_asyncio.fixture
async def pg_store():
    global _pg_store, _schema_initialized
    settings = Settings()
    settings.database_url = TEST_DB_URL
    store = PgStore(settings)
    await store.connect()
    if not _schema_initialized:
        await store.init_schema()
        _schema_initialized = True
    yield store
    await store.close()


@pytest_asyncio.fixture
async def clean_pg(pg_store):
    async with pg_store.pool.acquire() as conn:
        await conn.execute("DELETE FROM document_concepts")
        await conn.execute("DELETE FROM trace")
        await conn.execute("DELETE FROM supersede_log")
        await conn.execute("DELETE FROM knowledge_documents")
        await conn.execute("DELETE FROM concepts")
        await conn.execute("DELETE FROM scope_registry")
    return pg_store