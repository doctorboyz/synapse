# Synapse v3 — Testing & Quality Patterns

## 1. Test Structure and Conventions

### Directory Layout

Tests live in a flat `tests/` directory at the project root. 22 test files plus `conftest.py` and `__init__.py`.

**V1 tests** (importing from `synapse.*` — SQLite/LanceDB package):

| File | Source Module |
|------|---------------|
| `test_sqlite_store.py` | `synapse.store.sqlite_store` |
| `test_lancedb_store.py` | `synapse.store.lancedb_store` |
| `test_hybrid_search_v2.py` | `synapse.retrieve.hybrid_search` |
| `test_init.py` | `synapse.ingest.init` |
| `test_init_v2.py` | `synapse.ingest.init` (shared=True) |
| `test_hook_handler.py` | `synapse.ingest.hook_handler` |
| `test_rebuild.py` | `synapse.ingest.rebuild` |
| `test_embedding.py` | `synapse.embedding` |
| `test_cache.py` | `synapse.cache` |
| `test_config.py` | `synapse.config` |
| `test_exceptions.py` | `synapse.exceptions` |
| `test_cli.py` | `synapse.cli` |
| `test_scope_manager.py` | `synapse.scope.manager` |
| `test_cross_scope.py` | `synapse.scope.manager` + `synapse.retrieve.hybrid_search` |
| `test_daemon.py` | `synapse.daemon.*` |
| `test_registry.py` | `synapse.daemon.registry` |
| `test_integration.py` | E2E lifecycle tests |

**V2 tests** (importing from `src.*` — PostgreSQL/Qdrant package):

| File | Source Module |
|------|---------------|
| `test_pg_store.py` | `src.db.pg_store` |
| `test_hybrid_search.py` | `src.retrieve.hybrid_search` |
| `test_embed.py` | `src.embed.ollama` |
| `test_mcp_server.py` | `src.mcp.server` |
| `test_push.py` | `src.ingest.push` + `src.ingest.oracle_paths` |
| `test_oracle_paths.py` | `src.ingest.oracle_paths` |

### Naming Conventions

- **File naming**: `test_<module_name>.py` — direct mapping from source module
- **Class naming**: `Test<Feature>` grouped by concern (e.g. `TestPgStoreCRUD`, `TestPgStoreFTS`, `TestOllamaEmbedderInit`)
- **Method naming**: `test_<behavior>` in plain descriptive style (e.g. `test_add_duplicate`, `test_search_excludes_superseded`)

### Pytest Configuration

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
```

---

## 2. Test Utilities and Helpers

### conftest.py

Provides V2 (PostgreSQL) async fixtures only:

```python
TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:88888888@localhost:5432/mysynapse",
)

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
```

Key design decisions:
- **Module-level singleton**: `_pg_store` and `_schema_initialized` are module globals — connection and schema created once per test session
- **DELETE-based cleanup**: `clean_pg` deletes all rows between tests rather than dropping/recreating the schema
- **Hardcoded credentials**: Default database URL requires a running Docker PostgreSQL instance

### Inline Fixtures (in individual test files)

Many test files define their own fixtures rather than using conftest:

- `test_mcp_server.py`: `app_components` and `clean_components` fixtures (duplicate of conftest pattern)
- `test_push.py`: Inline `pg_store` fixture (risks shadowing conftest)
- `test_hybrid_search_v2.py`: `sqlite_store` and `populated_store` fixtures
- `test_daemon.py`: `config_file` and `config` fixtures for daemon IPC testing

---

## 3. Mocking Patterns

### Ollama Embedding Service

Mocked at the `httpx` HTTP layer. V1 tests patch `httpx.post` (sync); V2 tests patch `httpx.AsyncClient` (async):

```python
# V2 async mocking pattern
with patch("src.embed.ollama.httpx.AsyncClient") as mock_cls:
    client = AsyncMock()
    client.post = AsyncMock(return_value=_mock_response())
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    mock_cls.return_value = client
    result = await embedder.embed("test query")
```

### Qdrant

Not mocked — set to `None`:

```python
qdrant = None  # No Qdrant in tests
embedder = None  # No Ollama in tests
push = Push(pg, qdrant, embedder)
search = HybridSearch(pg, qdrant, embedder)
```

`HybridSearch` handles `None` qdrant by falling back to FTS-only search.

### PostgreSQL

NOT mocked. Tests require a live Docker PostgreSQL instance at `localhost:5432`.

### LanceDB

Conditionally skipped:

```python
try:
    import lancedb as _lancedb
    HAS_LANCEDB = True
except ImportError:
    HAS_LANCEDB = False

skip_no_lancedb = pytest.mark.skipif(not HAS_LANCEDB, reason="lancedb not installed")
```

### RRF Function

Tested as pure functions without mocking:

```python
class TestReciprocalRankFusion:
    def test_merge_two_lists(self):
        list_a = [{"id": "1", "title": "A", ...}]
        list_b = [{"id": "2", "title": "B", ...}]
        result = reciprocal_rank_fusion([list_a, list_b])
        assert len(result) == 2
```

---

## 4. Coverage Approach

### What is Tested

| Layer | V1 Coverage | V2 Coverage |
|-------|-------------|-------------|
| SQLite Store | CRUD, dedup, supersede, FTS5, stats, WAL | N/A |
| LanceDB Store | Chunking, scope, embed (conditional) | N/A |
| PostgreSQL Store | N/A | CRUD, FTS, supersede, concepts, trace, scope stats |
| Hybrid Search | RRF, FTS, hybrid fallback, cross-scope | RRF, FTS, hybrid fallback, error on dense without Qdrant |
| Embedding | OllamaEmbedder sync/async, retries, timeout | OllamaEmbedder async, retries, truncation |
| Init | Vault creation, scope, gitignore, validation | N/A |
| Config | Load v1/v2, validate, hot-reload | N/A |
| Exceptions | Full hierarchy | N/A |
| CLI | init, push, search, status, scope, rebuild | N/A |
| Daemon | Server lifecycle, health, IPC | N/A |
| Hook Handler | File type detection, scope detection | N/A |
| Oracle Paths | Name extraction, metadata from paths | Name extraction, metadata extraction |
| MCP Server | N/A | Search, push, trace, scope stats (end-to-end via Push+HybridSearch) |
| Push Pipeline | N/A | Push text, oracle metadata, concepts, duplicates |

### What is NOT Tested

1. **Qdrant vector operations** — `QdrantStore` is always `None` in tests; no actual vector search/insert/delete tests
2. **Dense search mode** — Only verifies that dense mode raises without Qdrant; actual dense search with real vectors is untested
3. **API routes** — `src/api/routes.py` has no dedicated test file
4. **MCP protocol framing** — Tests the handlers but not the MCP transport layer
5. **Embedding batch with real vectors** — Batch tests mock HTTP responses, don't verify vector quality
6. **Concurrency under load** — Only 2 concurrent SQLite connections tested
7. **Authentication/authorization** — No auth tests
8. **CI/CD pipeline** — No `.github/workflows` or CI configuration

### Coverage Targets

No explicit coverage target defined. `pytest-cov>=5.0` is a dev dependency but no `fail_under` threshold, `.coveragerc`, or coverage configuration exists.

### Key Architectural Observation

The test suite reflects a **dual-package architecture**:
- **V1 `synapse.*`** package: SQLite + LanceDB + local-file vault model. Self-contained, uses `tmp_path` fixtures, needs no external services (except LanceDB which is conditionally skipped).
- **V2 `src.*`** package: PostgreSQL + Qdrant + Ollama model. Requires a live PostgreSQL instance. Qdrant and Ollama are stubbed with `None`.

### Notable Issues

- `sqlite_store` fixture independently defined in multiple V1 test files with identical code
- `clean_pg` fixture defined in conftest, `test_mcp_server.py`, and `test_push.py` — risking fixture shadowing
- `pg_store` fixture defined in both conftest and `test_push.py`
- V1 fixtures (`sqlite_store`, `mock_ollama`, etc.) were removed from conftest during V2 migration, leaving V1 tests in a broken state