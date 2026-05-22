# Synapse v3 Architecture

> Hybrid Knowledge Framework -- PostgreSQL + Qdrant + MCP
> Generated: 2026-05-05

---

## 1. Directory Structure & Organization Philosophy

### Full Tree

```
synapse/
├── pyproject.toml              # Project metadata, dependencies, entry point
├── README.md                   # Full documentation (v1+v2+v3 history)
├── CLAUDE.md                   # Claude Code context (stack, commands, architecture)
├── SKILL.md                    # /synapse skill definition for Claude Code
├── LICENSE
├── .gitignore
├── docker/
│   ├── Dockerfile              # Python 3.13-slim, pip install, EXPOSE 8420
│   └── docker-compose.yml     # mysynapse + postgres + qdrant services
├── benchmarks/
│   └── basic.py                # R@5, R@10, latency benchmark script
├── src/                        # v3 CODE (active, PostgreSQL + Qdrant)
│   ├── __init__.py             # __version__ = "3.0.0"
│   ├── main.py                 # FastAPI app + CLI entry point
│   ├── config.py               # Settings dataclass from env vars
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.sql          # PostgreSQL DDL (idempotent)
│   │   ├── pg_store.py         # Async PgStore: CRUD, FTS, supersession, trace
│   │   └── qdrant_store.py    # Async QdrantStore: upsert, search, delete
│   ├── embed/
│   │   ├── __init__.py
│   │   └── ollama.py           # OllamaEmbedder (async, retry, batch)
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── push.py             # Push: dual-store write (PG + Qdrant)
│   │   ├── oracle_paths.py     # Oracle path mapping (kappa/psi -> metadata)
│   │   └── hook_handler.py     # PostToolUse auto-ingest for oracle brain files
│   ├── retrieve/
│   │   ├── __init__.py
│   │   └── hybrid_search.py    # HybridSearch: RRF fusion (dense + FTS)
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── server.py           # MCP stdio server (10 tools)
│   └── api/
│       ├── __init__.py
│       └── routes.py           # HTTP API routes (mirrors MCP tools)
├── synapse/                    # v2 CODE (legacy, SQLite + LanceDB)
│   ├── __init__.py             # __version__ = "2.0.0"
│   ├── cli.py                  # Full CLI (init, push, search, status, scope, rebuild, daemon, etc.)
│   ├── config.py               # YAML-based Config with v1/v2 schema validation
│   ├── exceptions.py           # Exception hierarchy
│   ├── cache.py                # LRU+TTL SearchCache
│   ├── embedding.py            # OllamaEmbedder (sync + async)
│   ├── logging_config.py       # Logging setup
│   ├── ingest/
│   │   ├── init.py             # Vault initialization (SQLite + config.yaml)
│   │   ├── push.py             # Push: SQLite + LanceDB dual write
│   │   ├── rebuild.py          # Vault rebuild from source files
│   │   └── hook_handler.py     # PostToolUse auto-index hook
│   ├── store/
│   │   ├── sqlite_store.py     # SQLiteStore: FTS5, metadata, scope
│   │   └── lancedb_store.py    # LanceDBStore: dense vectors, chunking
│   ├── retrieve/
│   │   └── hybrid_search.py    # HybridSearch with SearchCache
│   ├── scope/
│   │   └── manager.py          # ScopeManager + detect_scope
│   ├── daemon/
│   │   ├── server.py           # DaemonServer lifecycle
│   │   ├── registry.py         # ProjectRegistry (projects.yaml)
│   │   ├── health.py           # HealthChecker
│   │   └── ipc.py              # Unix socket IPC client/server
│   └── mcp/
│       └── server.py           # MCP server (11 tools, v2 feature set)
└── tests/                      # Test suite
    ├── conftest.py              # Fixtures: pg_store, clean_pg
    ├── test_pg_store.py
    ├── test_qdrant_store.py
    ├── test_config.py
    ├── test_cli.py
    ├── test_mcp_server.py
    ├── test_hybrid_search.py
    ├── test_hybrid_search_v2.py
    ├── test_embedding.py
    ├── test_embed.py
    ├── test_push.py
    ├── test_hook_handler.py
    ├── test_oracle_paths.py
    ├── test_scope_manager.py
    ├── test_cross_scope.py
    ├── test_exceptions.py
    ├── test_cache.py
    ├── test_daemon.py
    ├── test_init.py
    ├── test_init_v2.py
    ├── test_rebuild.py
    ├── test_lancedb_store.py
    ├── test_sqlite_store.py
    ├── test_registry.py
    └── test_integration.py
```

### Organization Philosophy

The repo contains **two parallel package trees** reflecting version evolution:

1. **`src/`** (v3 -- the active codebase on the `v3` branch): Migrated from local-first SQLite+LanceDB to a server-grade PostgreSQL+Qdrant stack. Every module is `async`, uses `asyncpg` for PostgreSQL and `qdrant-client` AsyncQdrantClient. Configuration is a flat `Settings` dataclass from environment variables (no YAML files). The v3 design prioritizes Docker-deployable multi-user service over per-project local vaults.

2. **`synapse/`** (v2 -- the legacy codebase, still present on the `v3` branch): The original per-project skill with SQLite+LanceDB, YAML config, CLI subcommands, daemon mode, Unix socket IPC, and project registry. This code is fully self-contained and still functional but is not the active development target.

The two packages share the same conceptual architecture (dual-store, RRF fusion, oracle paths, MCP tools) but differ in implementation. The `src/` package stripped away daemon/IPC/project-registry complexity in favor of a single FastAPI service + MCP stdio server, offloading multi-tenancy to PostgreSQL scopes and Qdrant payload filters.

**Branch history:**
- `main` -- v1: Claude Code skill (SQLite + ChromaDB)
- `v2` -- v2: Service mode daemon, shared vault, async
- `v3` -- v3: PostgreSQL + Qdrant hybrid search (current, checked out)

---

## 2. Entry Points

### 2a. CLI (`synapse` command)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/main.py` (lines 54-70)
**pyproject.toml entry:** `synapse = "src.main:cli_main"`

Two subcommands:

| Command | What it does |
|---------|-------------|
| `synapse serve` | Starts uvicorn with the FastAPI app on `MYSYNAPSE_HOST:MYSYNAPSE_PORT` (default `0.0.0.0:8420`) |
| `synapse mcp` | Starts the MCP stdio server via `asyncio.run(run_server())` |

No other CLI subcommands exist in v3 -- all v2 CLI commands (init, push, search, status, scope, rebuild, daemon, stop, register, unregister, projects, health) were removed. In v3, all interactions go through the HTTP API or MCP tools.

### 2b. HTTP API Server

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/main.py` (lines 21-51)

A FastAPI application with startup/shutdown lifecycle:
- **Startup:** Creates `PgStore`, connects, initializes schema. Creates `QdrantStore` (optional -- graceful fallback to FTS-only). Creates `OllamaEmbedder`. Calls `init_routes()` to wire dependencies.
- **Shutdown:** Closes PgStore and QdrantStore connections.

### 2c. MCP Server

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/mcp/server.py` (lines 155-288)

The `run_server()` async function:
1. Creates its own `PgStore`, `QdrantStore`, `OllamaEmbedder` instances (independent from the FastAPI app).
2. Connects to PostgreSQL and Qdrant (same graceful Qdrant fallback).
3. Constructs a `Server("synapse")` from the MCP SDK.
4. Registers `list_tools` and `call_tool` handlers.
5. Opens `stdio_server()` and runs.

### 2d. Hook Handler (standalone script)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/ingest/hook_handler.py` (lines 92-104)

Called by Claude Code PostToolUse hooks after Write/Edit on files under `kappa/` or `psi/` paths. Has its own `main()` entry point that reads the file path from `sys.argv[1]` or stdin JSON, then calls `asyncio.run(ingest_file(file_path))`.

### 2e. Docker

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/docker/Dockerfile`
**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/docker/docker-compose.yml`

The Dockerfile uses `python:3.13-slim`, copies `pyproject.toml` and `src/`, runs `pip install .`, and sets `CMD ["mysynapse", "serve"]`. Note: the CMD references `mysynapse` which does not match the pyproject.toml entry point `synapse` -- this appears to be a leftover from a rename.

docker-compose defines a `mysynapse` service (port 8420) that depends on a PostgreSQL service and a Qdrant service on the `server-network` external network (Postgres and Qdrant containers are defined elsewhere).

---

## 3. Core Abstractions & Their Relationships

### 3a. Settings (v3 Configuration)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/config.py`

A `@dataclass` that reads all configuration from environment variables with sensible defaults:

| Field | Env Var | Default | Purpose |
|-------|---------|---------|---------|
| `database_url` | `DATABASE_URL` | `postgresql://admin:88888888@localhost:5432/mysynapse` | PostgreSQL connection |
| `qdrant_url` | `QDRANT_URL` | `http://localhost:6333` | Qdrant server |
| `qdrant_collection` | `QDRANT_COLLECTION` | `mysynapse_vectors` | Qdrant collection name |
| `ollama_url` | `OLLAMA_URL` | `http://localhost:11434` | Ollama API |
| `embedding_model` | `EMBEDDING_MODEL` | `nomic-embed-text` | Model name |
| `embedding_dim` | `EMBEDDING_DIM` | `768` | Vector dimensions |
| `embedding_timeout` | `EMBEDDING_TIMEOUT` | `30` | Seconds |
| `api_host` | `MYSYNAPSE_HOST` | `0.0.0.0` | HTTP listen address |
| `api_port` | `MYSYNAPSE_PORT` | `8420` | HTTP listen port |
| `log_level` | `LOG_LEVEL` | `INFO` | Logging level |
| `search_weights` | `SEARCH_WEIGHTS` | `0.6,0.4` | RRF weights [dense, fts] |
| `search_rrf_k` | (hardcoded) | `60` | RRF constant |
| `cache_ttl` | `CACHE_TTL` | `300` | Cache TTL seconds |
| `cache_max_size` | `CACHE_MAX_SIZE` | `1000` | Max cache entries |

Unlike v2's YAML-based `Config` class (which supports v1/v2 schema, hot-reload, deep-merge), v3 uses a simple env-var dataclass with no file-based config.

### 3b. PgStore (PostgreSQL Knowledge Store)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/db/pg_store.py`

The central data store for v3. An async class using `asyncpg.Pool`:

**Schema** (`/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/db/schema.sql`):

| Table | Purpose |
|-------|---------|
| `knowledge_documents` | Core documents: id (UUID), title, content, content_hash, scope, doc_type, source_file, source_type, source_project, oracle_name, brain_path, brain_tier, concepts (JSONB), tags (JSONB), superseded_by (UUID FK self-ref), search_vector (tsvector auto-updated by trigger), UNIQUE(content_hash, scope) |
| `supersede_log` | Audit trail: old_id, new_id, reason, timestamp |
| `scope_registry` | Scope tracking: name (PK), description, doc_count, oracle_name |
| `concepts` | Concept dictionary: name (UNIQUE), description |
| `document_concepts` | Many-to-many: doc_id, concept_id (PK) |
| `trace` | Knowledge graph edges: source_id, target_id, relation, confidence |

Key features:
- **tsvector trigger** (`update_search_vector`): Auto-generates search_vector from title (weight A), content (weight B), concepts (weight C) on INSERT/UPDATE.
- **GIN index** on search_vector for fast FTS.
- **Partial indexes** on scope, doc_type, oracle_name, brain_tier, source_project (WHERE superseded_by IS NULL).
- **Dedup** by (content_hash, scope) -- UNIQUE constraint.
- **Supersession** never deletes -- old doc gets `superseded_by = new_id`.

**Methods:**
- `add()` -- Insert document with hash dedup, update scope_registry, upsert concepts
- `get()` -- Fetch by ID, optionally walk supersession chain
- `supersede()` -- Create new doc, link old to new, log in supersede_log
- `search_fts()` -- PostgreSQL tsvector full-text search with ts_rank
- `list_concepts()` -- Search/list concepts with doc counts
- `add_trace()` / `get_trace_chain()` -- Add and walk knowledge graph edges (BFS, configurable depth and direction)
- `list_scopes()` / `stats()` / `list_docs()` -- Metadata queries

### 3c. QdrantStore (Vector Store)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/db/qdrant_store.py`

Async wrapper around `AsyncQdrantClient`. Manages a single collection with COSINE distance.

**Payload schema** (stored alongside vectors):
- `title`, `scope`, `doc_type`, `superseded` (bool), `created_at`
- Optional: `oracle_name`, `brain_tier`, `concepts`

**Methods:**
- `connect()` -- Connect or create collection with configured vector size
- `upsert()` -- Insert point with doc_id as UUID hex, vector, and payload
- `search()` -- Query by vector with payload filters (scope, doc_type, oracle_name, superseded=false)
- `mark_superseded()` -- Set payload `superseded=True` for a doc
- `delete()` -- Remove point by doc_id

Unlike v2's LanceDBStore (which chunks text into 4000-char segments with overlap and stores multiple vectors per document), v3's QdrantStore stores **one vector per document** -- no chunking. The chunking responsibility is implicitly on the caller or the embedding service.

### 3d. OllamaEmbedder

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/embed/ollama.py`

Async embedding client with retry logic. Calls Ollama's `/api/embed` endpoint.

- `embed(text)` -- Single text embedding with retry (2 retries, exponential backoff 0.5s * 2^attempt). Truncates to 4000 chars.
- `embed_batch(texts)` -- Sequential batch with semaphore (concurrency=4).
- `check()` -- Health check via `embed("health check")`.

Compared to v2's OllamaEmbedder (which has both sync `embed()` and async `aembed()` methods, plus `embed_batch()` and `aembed_batch()`), v3 is **async-only** with a simpler interface.

### 3e. Push (Ingestion Pipeline)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/ingest/push.py`

Orchestrates dual-store writes:

1. Validates `doc_type` via `oracle_paths.validate_doc_type()`
2. Inserts into PostgreSQL via `pg.add()` (with dedup check)
3. If not duplicate AND Qdrant + embedder available: embeds content and upserts to Qdrant
4. Returns `{"id", "scope", "status"}` -- status is "indexed", "duplicate", or "indexed_pg_only"

Also has `push_file()` which reads a file, extracts oracle metadata from the path, and delegates to `push_text()`.

### 3f. Oracle Paths (Path-to-Metadata Mapping)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/ingest/oracle_paths.py`

Maps file paths from the Oracle ecosystem (kappa/psi brain structure) to Synapse metadata:

| Pattern | doc_type | brain_tier |
|---------|----------|------------|
| `psi/memory/learnings/` | learning | extrinsic |
| `psi/memory/retrospectives/` | retro | extrinsic |
| `psi/outbox/` | handoff | extrinsic |
| `kappa/extrinsic/wisdom/knowledge/` | wisdom | extrinsic |
| `kappa/extrinsic/wisdom/reference/` | reference | extrinsic |
| `kappa/extrinsic/experience/learn/` | learning | extrinsic |
| `kappa/extrinsic/experience/work/logs/` | log | extrinsic |
| `kappa/intrinsic/instinct/` | instinct | intrinsic |
| `kappa/intrinsic/identity/` | instinct | intrinsic |
| `kappa/intrinsic/inherit/` | instinct | intrinsic |

Valid doc_types: `learning, pattern, retro, reference, handoff, protocol, wisdom, instinct, log, note`

Valid trace relations: `derived_from, refines, contradicts, extends`

`extract_metadata(file_path, repo_root)` returns `{oracle_name, brain_path, brain_tier, doc_type, scope}`.

`extract_oracle_name(repo_path)` strips `-oracle` suffix from directory basename.

### 3g. HybridSearch (Retrieval Engine)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/retrieve/hybrid_search.py`

Implements three search modes with Reciprocal Rank Fusion:

| Mode | Behavior |
|------|----------|
| `hybrid` (default) | Qdrant dense + PostgreSQL FTS -> RRF merge. Falls back to FTS-only if Qdrant unavailable or embedding fails. |
| `dense` | Qdrant vector search only (requires Qdrant + embedder). |
| `fts` | PostgreSQL tsvector search only. |

**RRF algorithm** (`reciprocal_rank_fusion`):
- Input: N ranked result lists with optional weights
- For each doc in each list: `score += weight / (k + rank)` where k=60
- Merge by summing scores across lists
- Sort descending by total score

Default weights: [0.6, 0.4] = 60% dense, 40% FTS (configurable via `SEARCH_WEIGHTS` env var).

Graceful degradation: if Qdrant is down, falls back to FTS-only. If embedding fails for a single query, falls back to FTS.

### 3h. API Routes (HTTP Interface)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/api/routes.py`

FastAPI `APIRouter(prefix="/api")`. Mirrors the MCP tool interface exactly:

| Endpoint | Method | Maps to |
|----------|--------|---------|
| `/api/search` | POST | `HybridSearch.search()` |
| `/api/push` | POST | `Push.push_text()` |
| `/api/webhook` | POST | Same as push with `source_type="webhook"` |
| `/api/supersede` | POST | `PgStore.supersede()` + `QdrantStore.mark_superseded()` |
| `/api/trace` | POST | `PgStore.add_trace()` |
| `/api/trace/{doc_id}` | GET | `PgStore.get_trace_chain()` |
| `/api/concepts` | GET | `PgStore.list_concepts()` |
| `/api/documents/{doc_id}` | GET | `PgStore.get()` |
| `/api/scopes` | GET | `PgStore.list_scopes()` |
| `/api/stats` | GET | `PgStore.stats()` |
| `/api/documents` | GET | `PgStore.list_docs()` |
| `/api/health` | GET | Health check (qdrant + embedding) |

Dependencies are injected via `init_routes(pg_store, qdrant_store, embedder_client)` called during FastAPI startup.

### 3i. MCP Server (10 Tools)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/mcp/server.py`

Exposes 10 tools via the MCP SDK stdio transport:

| Tool | Description |
|------|-------------|
| `synapse_search` | Hybrid/dense/FTS search |
| `synapse_push` | Add knowledge |
| `synapse_supersede` | Supersede document |
| `synapse_trace` | Create trace link |
| `synapse_trace_chain` | Walk trace graph |
| `synapse_concepts` | List/search concepts |
| `synapse_get` | Retrieve full document |
| `synapse_scope` | List scopes |
| `synapse_stats` | Vault statistics |
| `synapse_list` | List documents with filters |

The MCP server creates its own independent PgStore/QdrantStore/OllamaEmbedder instances (not shared with the HTTP API process).

### 3j. Hook Handler (Auto-Ingest)

**File:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/ingest/hook_handler.py`

Standalone script for Claude Code PostToolUse hooks. On each invocation:
1. Checks if the file path contains `kappa` or `psi` directory components
2. Walks up to find the oracle root (directory containing `CLAUDE.md`)
3. Extracts oracle metadata from the path
4. Creates its own PgStore/QdrantStore/OllamaEmbedder instances
5. Calls `Push.push_text()` with `source_type="hook"`
6. Cleans up connections

### Relationship Diagram

```
                    ┌──────────────┐
                    │   Settings   │  (env vars)
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌─────▼──────┐   ┌─────▼──────┐
    │  PgStore   │   │ QdrantStore│   │   Ollama   │
    │ (asyncpg)  │   │(qdrant-client)│  │ Embedder   │
    └─────┬─────┘   └─────┬──────┘   └─────┬──────┘
          │               │                │
          │         ┌─────┴──────┐    ┌─────┘
          │         │            │    │
    ┌─────▼─────────▼──┐  ┌─────▼────▼─────┐
    │      Push        │  │  HybridSearch  │
    │ (dual-store      │  │ (dense + FTS   │
    │  write + dedup)  │  │  -> RRF)       │
    └─────┬────────────┘  └───────┬────────┘
          │                       │
    ┌─────▼───────────────────────▼─────┐
    │                                   │
    │  ┌───────────┐    ┌────────────┐  │
    │  │ API Routes│    │ MCP Server │  │
    │  │(FastAPI)  │    │ (stdio)    │  │
    │  └───────────┘    └────────────┘  │
    │                                   │
    │         Entry Points               │
    └───────────────────────────────────┘

    ┌───────────────┐     ┌────────────────┐
    │ Oracle Paths   │────▶│ Hook Handler   │
    │ (path -> meta) │     │ (auto-ingest)  │
    └───────────────┘     └───────┬────────┘
                                  │
                          ┌───────▼────────┐
                          │     Push       │
                          └────────────────┘
```

---

## 4. Dependencies

### 4a. Direct Dependencies (from pyproject.toml)

| Package | Version | Why |
|---------|---------|-----|
| `asyncpg` | >=0.30.0 | Async PostgreSQL driver. Used by PgStore for connection pooling and all queries. Replaces v2's sqlite3. |
| `qdrant-client` | >=1.12.0 | Official Qdrant Python client. Provides AsyncQdrantClient for vector upsert/search with payload filters. Replaces v2's lancedb. |
| `httpx` | >=0.27.0 | Async HTTP client. Used by OllamaEmbedder to call Ollama's `/api/embed` endpoint. |
| `fastapi` | >=0.115.0 | Web framework. Used for the HTTP API server in `src/main.py` and `src/api/routes.py`. |
| `uvicorn` | >=0.34.0 | ASGI server. Runs the FastAPI app in `synapse serve`. |
| `pyyaml` | >=6.0 | YAML parser. Present in dependencies but not used by v3's `src/` code (only used by v2's `synapse/config.py`). Likely retained for v2 backward compatibility or future config files. |
| `mcp` | >=1.0.0 | MCP SDK. Provides `Server`, `stdio_server`, `Tool`, `TextContent` for the MCP stdio server. |

### 4b. Optional Dev Dependencies

| Package | Version | Why |
|---------|---------|-----|
| `pytest` | >=8.0 | Test runner |
| `pytest-asyncio` | >=0.24 | Async test support (mode=auto) |
| `pytest-cov` | >=5.0 | Coverage reporting |
| `testcontainers[postgres]` | >=4.0 | Docker-based PostgreSQL for integration tests |

### 4c. Transitive / Implicit Dependencies

| Package | Used By | Why |
|---------|---------|-----|
| `pydantic` | fastapi (transitive) | FastAPI's request/response validation. v3 does not use Pydantic models directly -- `SearchRequest` in routes.py is a plain class. |
| `starlette` | fastapi (transitive) | Underlying ASGI toolkit for FastAPI |
| `anyio` | mcp (transitive) | Async I/O for MCP stdio transport |
| `grpcio` | qdrant-client (transitive) | gRPC transport for Qdrant client |
| `protobuf` | qdrant-client (transitive) | Protocol buffers for Qdrant gRPC |

### 4d. External Service Dependencies (not pip packages)

| Service | Port | Used By | Required? |
|---------|------|---------|-----------|
| PostgreSQL | 5432 | PgStore | Yes (no fallback) |
| Qdrant | 6333 | QdrantStore | Optional (graceful FTS-only fallback) |
| Ollama | 11434 | OllamaEmbedder | Optional (FTS-only without it; dense search requires it) |

### 4e. v2 Dependencies (in `synapse/` package, not installed by v3)

| Package | Why (v2 only) |
|---------|---------------|
| `lancedb` | Vector storage in v2 (local file-based, no server) |
| `httpx` | Ollama API calls (same as v3) |
| `pyyaml` | Config file parsing |
| `mcp` | MCP SDK (same as v3) |

### 4f. Dependency Evolution v1 -> v2 -> v3

```
v1:  sqlite3 (stdlib) + lancedb + httpx + pyyaml + mcp
v2:  sqlite3 (stdlib) + lancedb + httpx + pyyaml + mcp
v3:  asyncpg + qdrant-client + httpx + fastapi + uvicorn + pyyaml + mcp
```

Key shifts:
- SQLite -> asyncpg (local file -> network server)
- LanceDB -> Qdrant (local file -> network server)
- Added FastAPI + uvicorn (dedicated HTTP service vs v2's Unix socket daemon)
- Lost: local-first, zero-setup operation. Gained: multi-user, Docker-ready, concurrent access.

---

## Design Principles (from CLAUDE.md)

1. **Nothing is deleted** -- supersession only (documents get `superseded_by` pointing to newer version)
2. **Oracle-aware doc_types** -- kappa/psi brain structure mapped to doc_type, brain_tier
3. **source_project tracks origin** -- separate from scope/namespace
4. **FTS fallback when Qdrant unavailable** -- graceful degradation
5. **Dedup by (content_hash, scope)** -- same content in different scopes is allowed

---

## Notable Implementation Details

- **PostgreSQL tsvector trigger** auto-generates search_vector with weighted tokens (title=A, content=B, concepts=C) -- `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/db/schema.sql` lines 28-38
- **Qdrant uses UUID hex** as point IDs (not UUID objects) -- `/Users/doctorboyz/code/github.com/doctorboyz/synapse/src/db/qdrant_store.py` line 73
- **v3 has no text chunking** -- unlike v2's LanceDBStore which chunks at 4000 chars with 200-char overlap, v3's QdrantStore stores one vector per document. The OllamaEmbedder truncates to 4000 chars but does not chunk.
- **MCP server is fully independent** from the HTTP API server -- each creates its own store/embedder instances. They share the same PostgreSQL database and Qdrant collection but not Python objects.
- **Hook handler creates ephemeral connections** -- each hook invocation opens/closes PgStore and QdrantStore, which is correct for a short-lived subprocess but means no connection pooling across hook calls.
- **Docker CMD mismatch** -- Dockerfile says `CMD ["mysynapse", "serve"]` but pyproject.toml defines `synapse = "src.main:cli_main"`. The `mysynapse` command does not exist in the entry points.
- **v2 code is still present** on the v3 branch but is not imported by any v3 module. It exists as a reference implementation and fallback.
