# Synapse v3 Testing Guide

> Generated from codebase exploration on 2026-05-14.
> Total: ~159 test functions across 48 test classes in 14 test files.

---

## Test Structure and Conventions

### Directory Layout

```
tests/
├── conftest.py              # Shared fixtures (PostgreSQL, FastAPI client, Push, HybridSearch)
├── test_api_routes.py       # FastAPI HTTP endpoint tests (18 tests)
├── test_cli.py              # CLI argument parser + dispatch tests (17 tests)
├── test_embed.py            # OllamaEmbedder mocked HTTP tests (4 tests)
├── test_hook_handler.py     # Auto-ingest hook handler tests (7 tests)
├── test_hooks_installer.py  # Hook installer settings.json tests (10 tests)
├── test_hybrid_search.py    # RRF fusion + HybridSearch tests (8 tests)
├── test_lifecycle.py        # App startup/shutdown + route tests (7 tests)
├── test_mcp_server.py       # MCP tool integration tests (10 tests)
├── test_obsidian_links.py   # Obsidian link parser tests (6 tests)
├── test_oracle_paths.py     # Oracle brain path metadata tests (9 tests)
├── test_pg_store.py         # PostgreSQL CRUD / FTS / trace tests (17 tests)
├── test_push.py             # Push pipeline integration tests (10 tests)
├── test_qdrant_store.py     # QdrantStore mocked client tests (10 tests)
```

### Naming Conventions

| Pattern | Example | Purpose |
|---------|---------|---------|
| Test classes | `TestPgStoreCRUD` | Group related tests by subsystem + behavior |
| Test methods | `test_add_document` | Descriptive action under test |
| Fixtures | `clean_pg`, `api_client` | Reusable setup with predictable cleanup |

### Test Isolation

- **Database**: Every test using `clean_pg` gets a freshly truncated PostgreSQL schema (all tables `DELETE`d via `conftest.py`).
- **Module-level singletons**: `conftest.py` uses a module-level `_pg_store` and `_schema_initialized` flag to avoid recreating the connection pool per test while still cleaning rows between tests.
- **Global state restoration**: `test_lifecycle.py` saves/restores `main_mod._pg` and `main_mod._qdrant` with `try/finally` to prevent side effects on module globals.

---

## Test Utilities and Helpers

### `tests/conftest.py` — Core Fixtures

**`pg_store`** (`@pytest_asyncio.fixture`)
- Creates `PgStore` connected to `postgresql://admin:88888888@localhost:5432/synapse` (override via `DATABASE_URL` env var).
- Runs `init_schema()` once per session (guarded by `_schema_initialized`).

**`clean_pg`** (`@pytest_asyncio.fixture`)
- Acquires a connection from `pg_store.pool` and truncates:
  - `document_concepts`, `trace`, `supersede_log`, `knowledge_documents`, `concepts`, `scope_registry`
- Returns the same `PgStore` instance but with empty tables.

**`api_client`** (`@pytest_asyncio.fixture`)
- Calls `init_routes(clean_pg, qdrant_store=None, embedder_client=None)` on the global FastAPI `app`.
- Yields an `httpx.AsyncClient` with `ASGITransport` for in-process HTTP testing.

**`app_components`** (`@pytest_asyncio.fixture`)
- Returns a 3-tuple: `(clean_pg, Push, HybridSearch)` — used by MCP server tests.

### Helper Factories in Test Files

```python
# tests/test_qdrant_store.py
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
    point.payload = payload or {...}
    return point
```

```python
# tests/test_embed.py
def _make_http_error(msg="connection error"):
    request = MagicMock()
    return httpx.HTTPStatusError(msg, request=request, response=MagicMock(status_code=500))

def _mock_response(data=None, raise_error=None):
    resp = MagicMock()
    ...
    return resp
```

---

## Mocking Patterns

### External HTTP / Async Clients

```python
# tests/test_embed.py
with patch("src.embed.ollama.httpx.AsyncClient") as mock_cls:
    client = AsyncMock()
    client.post = AsyncMock(return_value=_mock_response())
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    mock_cls.return_value = client
    result = await embedder.embed("test query")
```

### Qdrant Client (Full Class Replacement)

```python
# tests/test_qdrant_store.py
with patch("src.db.qdrant_store.AsyncQdrantClient") as MockClient:
    mock_client = AsyncMock()
    mock_client.get_collection = AsyncMock(return_value=MagicMock())
    mock_client.close = AsyncMock()
    mock_client.upsert = AsyncMock()
    MockClient.return_value = mock_client
    await store.connect()
    ...
```

### Graceful Failure Simulation

```python
# tests/test_lifecycle.py
mock_qdrant = AsyncMock()
mock_qdrant.connect = AsyncMock(side_effect=Exception("connection refused"))
MockQdrant.return_value = mock_qdrant
```

### Temporary Filesystem with `tmp_path`

```python
# tests/test_hook_handler.py
def test_psi_path(self, tmp_path):
    f = tmp_path / "emily-oracle" / "ψ" / "memory" / "learnings" / "test.md"
    assert is_oracle_brain_path(str(f)) is True
```

### Monkeypatching CLI / Env

```python
# tests/test_hook_handler.py
def test_empty_argv_exits_silently(self, monkeypatch):
    monkeypatch.setattr("sys.argv", ["hook_handler", ""])
    monkeypatch.delenv("CLAUDE_CODE_FILEPATH", raising=False)
```

---

## Coverage Approach

### Configuration

**`pyproject.toml`**:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "testcontainers[postgres]>=4.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
```

### How to Run Tests

```bash
# All tests (requires local PostgreSQL + optional Qdrant for non-mocked tests)
pytest tests/ -v

# With coverage
pytest --cov=src --cov-report=term-missing

# Specific module
pytest tests/test_pg_store.py -v
pytest tests/test_qdrant_store.py -v
pytest tests/test_api_routes.py -v
```

**External service dependency matrix**:

| Test File | PostgreSQL | Qdrant | Ollama |
|-----------|-----------|--------|--------|
| `test_pg_store.py` | Required | No | No |
| `test_api_routes.py` | Required | No | No |
| `test_mcp_server.py` | Required | No | No |
| `test_push.py` | Required | No | No |
| `test_hybrid_search.py` | Required | No | No |
| `test_hook_handler.py` | Required | Mocked | Mocked |
| `test_embed.py` | No | No | Mocked (HTTP) |
| `test_qdrant_store.py` | No | Mocked | No |
| `test_cli.py` | No | No | No |
| `test_hooks_installer.py` | No | No | No |
| `test_oracle_paths.py` | No | No | No |
| `test_obsidian_links.py` | No | No | No |
| `test_lifecycle.py` | No | Mocked | Mocked |

---

## Notable Test Patterns

### Async Test Classes with `@pytest.mark.asyncio`

All async database/HTTP tests are grouped in classes decorated at the top:

```python
@pytest.mark.asyncio
class TestPgStoreCRUD:
    async def test_add_document(self, clean_pg):
        ...
```

### Pure Unit Tests (No Async)

Parser, path extraction, and CLI tests use plain `def` without decorators:

```python
class TestExtractOracleName:
    def test_emily_oracle(self):
        assert extract_oracle_name("/path/to/emily-oracle") == "emily"
```

### Parametrized-Like via Loops

```python
# tests/test_cli.py
for cmd, args in test_args.items():
    parsed = parser.parse_args([cmd] + args)
    assert parsed.command == cmd, f"Command {cmd} not recognized"
```

```python
# tests/test_oracle_paths.py
for dt in VALID_DOC_TYPES:
    assert validate_doc_type(dt) == dt
```

### Stateful Mock with `nonlocal` Counter

```python
# tests/test_embed.py
async def mock_post(*args, **kwargs):
    nonlocal call_count
    call_count += 1
    if call_count == 1:
        return _mock_response(raise_error=_make_http_error())
    return _mock_response()
```

### Asserting Call Args (Keyword Inspection)

```python
# tests/test_qdrant_store.py
mock_client.upsert.assert_called_once()
call_kwargs = mock_client.upsert.call_args
points = call_kwargs.kwargs["points"]
assert point.payload["superseded"] is False
```

---

## Areas with Weak Coverage

| Module | Test File | Gap |
|--------|-----------|-----|
| `src/cache.py` | None | LRU + TTL search cache is untested directly |
| `src/cli.py` | `test_cli.py` (partial) | Only tests `main.py` parser/dispatch, not `cli.py` helpers (JSON output, error formatting, components setup) |
| `src/config.py` | None | Settings loading, YAML hot-reload, env var parsing untested |
| `src/daemon.py` | None | PID file, signal handling, start/stop/status lifecycle untested |
| `src/local_only.py` | None | URL validation for local-only enforcement untested |
| `src/registry.py` | None | Project registry backup/restore, cross-project registration untested |
| `src/scheduler.py` | None | Background scheduled scanning logic untested |
| `src/ingest/init_scan.py` | None | Directory scan + LLM summarization for `synapse init` untested |
| `src/ingest/concepts.py` | None | Concept extraction logic untested directly |
| `src/reconcile/defrag.py` | None | Duplicate compaction untested |
| `src/reconcile/detox.py` | None | LLM conflict detection untested |
| `src/reconcile/llm.py` | None | LLM reconciliation helpers untested |
| `src/api/routes.py` | `test_api_routes.py` | Missing tests for: cross-project search endpoint, Obsidian link resolution endpoint |
| `src/mcp/server.py` | `test_mcp_server.py` | Missing tests for: `synapse_supersede`, `synapse_trace`, `synapse_trace_chain`, `synapse_search_cross`, `synapse_register`, `synapse_unregister`, `synapse_projects` tools |

---

## Quick Reference: Running a Single Test

```bash
# Single test function
pytest tests/test_pg_store.py::TestPgStoreCRUD::test_add_document -v

# Single test class
pytest tests/test_hybrid_search.py::TestReciprocalRankFusion -v

# All non-DB tests (fast, no external services)
pytest tests/test_cli.py tests/test_oracle_paths.py tests/test_obsidian_links.py tests/test_hooks_installer.py -v
```
