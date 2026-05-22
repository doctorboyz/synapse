# Synapse v3 — Architecture Document

> Date: 2026-05-14
> Branch: v3
> Version: 3.0.0

## Overview

Synapse is a **local-first hybrid knowledge framework** that ingests documents, embeds them as dense vectors, indexes them via full-text search, and serves retrieval through multiple interfaces (CLI, HTTP API, MCP stdio server). It is designed as **Stage 2** knowledge infrastructure for the Oracle ecosystem: consulted after primary project context is exhausted.

**Core value proposition**: Zero-network-egress knowledge synthesis on your machine. PostgreSQL for structured storage and FTS, Qdrant for vector similarity, Ollama for embeddings and LLM synthesis — all running locally.

---

## Directory Structure & Organization Philosophy

```
src/
├── main.py                    # FastAPI app + CLI entry point (20+ subcommands)
├── cli.py                     # Components helper: async setup/teardown, JSON output
├── config.py                  # Settings dataclass: env vars + YAML hot-reload
├── cache.py                   # LRU + TTL search result cache
├── daemon.py                  # PID file, signal handling (SIGTERM/SIGHUP)
├── scheduler.py               # Background scan + nightly reconcile loops
├── local_only.py              # URL validation enforcing localhost-only
├── registry.py                # Project registration for cross-project search
├── api/
│   └── routes.py              # HTTP API: 18 endpoints (search, push, ingest, chat, health)
├── db/
│   ├── pg_store.py            # PostgreSQL CRUD, FTS, supersession, traces, concepts
│   ├── qdrant_store.py        # Qdrant vector upsert/search with payload filters
│   └── schema.sql             # Idempotent PostgreSQL schema (tables, triggers, indexes)
├── embed/
│   └── ollama.py              # Async Ollama embedder: retry, batch, timeout
├── ingest/
│   ├── push.py                # Dual-store write (PG + Qdrant), dedup, summarization
│   ├── hook_handler.py        # PostToolUse auto-ingest for κ/ψ brain files
│   ├── init_scan.py           # Directory scanner: md/txt/pdf/docx → vault
│   ├── oracle_paths.py        # κ/ψ path → doc_type, oracle_name, brain_tier
│   ├── concepts.py            # Hashtag + CamelCase concept extraction
│   └── obsidian_links.py      # [[Link]] parsing → trace creation
├── retrieve/
│   └── hybrid_search.py       # RRF fusion (60% dense / 40% FTS) + cross-scope
├── reconcile/
│   ├── defrag.py              # Compact duplicates via supersession
│   ├── detox.py               # LLM-powered conflict detection + resolution
│   └── llm.py                 # Ollama LLM client for conflict analysis
├── mcp/
│   └── server.py              # MCP stdio server: 14 tools
└── hooks/
    └── installer.py           # Register synapse hooks in ~/.claude/settings.json
```

### Organization Principles

1. **Feature-based grouping**: Each directory (`db/`, `ingest/`, `retrieve/`, `reconcile/`) encapsulates a complete vertical slice.
2. **Dual-store pattern**: Every write goes to PostgreSQL (canonical) and optionally Qdrant (vectors). The `Push` class orchestrates this.
3. **Graceful degradation**: Qdrant and Ollama are optional. If unavailable, the system falls back to FTS-only search.
4. **Local-only enforcement**: `local_only.py` validates all service URLs are localhost/Unix socket. No external network egress.

---

## Entry Points

Synapse has **four distinct entry points**, all converging on the same core abstractions:

### 1. CLI (`synapse` command)
- **Entry**: `src.main:cli_main`
- **Dispatcher**: `COMMAND_DISPATCH` dict maps 20+ subcommands to async handlers
- **Lifecycle**: Each command calls `get_components()` → executes → `cleanup()`
- **Commands**: `serve`, `mcp`, `push`, `search`, `get`, `list`, `scope`, `stats`, `supersede`, `trace`, `trace-chain`, `concepts`, `init`, `reconcile`, `register`, `unregister`, `projects`, `search-cross`, `stop`, `status`, `scan`, `install-hooks`

### 2. HTTP API Server (`synapse serve`)
- **Entry**: `uvicorn.run(app, host=settings.api_host, port=settings.api_port)`
- **App**: `FastAPI` instance in `src.main`
- **Routes**: `src.api.routes` — 18 endpoints under `/api/*`
- **Startup**: Connects PG, Qdrant, Ollama; restores project registry backup; starts scheduler

### 3. MCP Server (`synapse mcp`)
- **Entry**: `src.mcp.server:run_server`
- **Protocol**: MCP stdio server via `mcp.server.stdio`
- **Tools**: 14 tools (`synapse_search`, `synapse_push`, `synapse_supersede`, etc.)
- **Lifecycle**: Per-session component initialization (PG + Qdrant + embedder)

### 4. Hook Handler (auto-ingest)
- **Entry**: `src.ingest.hook_handler:main`
- **Trigger**: Claude Code `PostToolUse` hook on Write/Edit to κ/ψ paths
- **Input**: File path via argv, `CLAUDE_CODE_FILEPATH` env var, or stdin JSON

---

## Core Abstractions & Their Relationships

### Settings (`src.config.Settings`)
- `@dataclass` with `field(default_factory=lambda: os.getenv(...))`
- Sources: environment variables (SYNAPSE_* prefix) → YAML config (`~/.synapse/config.yaml`)
- Supports hot-reload via `reload()` (triggered by SIGHUP)
- Key settings: `database_url`, `qdrant_url`, `ollama_url`, `search_weights`, `cache_ttl`, `scan_interval`, `reconcile_hour`

### PgStore (`src.db.pg_store`)
- **Role**: Canonical data store and FTS engine
- **Connection**: `asyncpg.create_pool(min_size=2, max_size=10)`
- **Schema**: Idempotent SQL in `schema.sql` — run via `init_schema()` on every startup
- **Key operations**:
  - `add()`: Insert document with content_hash dedup (UNIQUE(content_hash, scope))
  - `search_fts()`: PostgreSQL tsvector query with ranked results
  - `supersede()`: Create new doc, link old doc via `superseded_by` (nothing deleted)
  - `add_trace()` / `get_trace_chain()`: Document relationship graph
  - `list_concepts()`: Concept catalog with document counts

### QdrantStore (`src.db.qdrant_store`)
- **Role**: Vector similarity search
- **Connection**: `AsyncQdrantClient` with auto-collection creation
- **Vector config**: Cosine distance, dimension from settings (default 768)
- **Payload filtering**: scope, doc_type, oracle_name, source_project, concepts, superseded flag
- **Graceful degradation**: If Qdrant fails to connect, system runs FTS-only

### OllamaEmbedder (`src.embed.ollama`)
- **Role**: Text → dense vector embeddings
- **API**: `POST /api/embed` with retry (2 retries, exponential backoff)
- **Batching**: `asyncio.Semaphore(4)` for concurrent requests
- **Chunking**: Truncates to 4000 chars before embedding
- **Graceful degradation**: If Ollama unavailable, embeddings skipped

### Push (`src.ingest.push`)
- **Role**: Ingestion orchestrator
- **Pipeline**:
  1. Validate doc_type
  2. Extract concepts (hashtags + CamelCase)
  3. LLM summarize if content > 3000 chars
  4. Write to PostgreSQL (canonical)
  5. Create traces from Obsidian [[links]]
  6. Embed and upsert to Qdrant (optional)
- **Deduplication**: PG UNIQUE(content_hash, scope) prevents re-ingestion

### HybridSearch (`src.retrieve.hybrid_search`)
- **Role**: Retrieval orchestrator
- **Modes**:
  - `hybrid` (default): Dense + FTS → RRF fusion (60/40 weights, k=60)
  - `dense`: Vector search only
  - `fts`: Keyword search only
- **Cache**: LRU + TTL via `SearchCache` (optional)
- **Cross-scope**: `search_cross_scope()` runs per-scope search then merges via RRF

### SearchCache (`src.cache`)
- **Role**: Thread-safe in-memory search result cache
- **Policy**: LRU eviction + TTL expiration
- **Key format**: `query||scope||mode||limit`

### Components (`src.cli.Components`)
- **Role**: Service locator / dependency container
- **Holds**: Settings, PgStore, QdrantStore, OllamaEmbedder, Push, HybridSearch
- **Pattern**: `get_components()` initializes all connections; `cleanup()` closes them

---

## Dependencies (Direct + Transitive Patterns)

### Runtime Dependencies
| Package | Role |
|---------|------|
| `asyncpg` | Async PostgreSQL driver |
| `qdrant-client` | Async Qdrant vector store |
| `httpx` | Async HTTP client (Ollama API, website scraping, YouTube) |
| `fastapi` + `uvicorn` | HTTP API server |
| `pyyaml` | Config file parsing |
| `mcp` | MCP SDK for stdio server |
| `beautifulsoup4` | Website content extraction |
| `youtube-transcript-api` | YouTube transcript ingestion |
| `pypdf` | PDF text extraction |
| `python-docx` | DOCX text extraction |

### External Services
| Service | Purpose | Required? |
|---------|---------|-----------|
| PostgreSQL | Canonical storage + FTS | Yes |
| Qdrant | Vector search | No (FTS fallback) |
| Ollama | Embeddings + LLM synthesis | No (PG-only mode) |

### Dev Dependencies
| Package | Role |
|---------|------|
| `pytest` + `pytest-asyncio` + `pytest-cov` | Test framework |
| `testcontainers[postgres]` | Integration testing with real PostgreSQL |

---

## Data Flow Through the System

### Ingestion Flow (Push)

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│   Source    │───→│   Push.push  │───→│  PgStore.add  │───→│ PostgreSQL   │
│ (file/text/ │    │   _text()    │    │  (canonical)  │    │ (knowledge_  │
│   hook/API) │    └──────┬───────┘    └─────────────┘    │  documents)  │
└─────────────┘           │                                    └──────────────┘
                        │
                        │    ┌─────────────┐    ┌──────────────┐
                        └───→│ OllamaEmbed │───→│ QdrantStore  │
                             │  .embed()    │    │  .upsert()   │
                             └─────────────┘    └──────────────┘
```

1. Content arrives via CLI, API, MCP, or hook
2. `Push.push_text()` validates, extracts concepts, optionally summarizes
3. Writes to PostgreSQL with content_hash dedup
4. Parses Obsidian `[[links]]` and creates traces
5. If embedder available: embeds summary/content, upserts to Qdrant with payload filters

### Retrieval Flow (Search)

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Query     │───→│ HybridSearch │───→│   SearchCache     │
│             │    │  .search()   │    │  (check/get)    │
└─────────────┘    └──────┬───────┘    └─────────────────┘
                          │
           ┌──────────────┼──────────────┐
           │              │              │
    ┌──────┴──────┐  ┌────┴────┐  ┌──────┴──────┐
    │   Dense     │  │   FTS   │  │  Fallback   │
    │ (Qdrant)    │  │  (PG)   │  │  (PG only)  │
    └──────┬──────┘  └────┬────┘  └─────────────┘
           │              │
           └──────┬───────┘
                  │
           ┌──────┴──────┐
           │     RRF     │
           │   Fusion    │
           └──────┬──────┘
                  │
           ┌──────┴──────┐
           │   Cache.put │
           │   Results   │
           └─────────────┘
```

1. Check `SearchCache` for exact match
2. If mode is `hybrid` and Qdrant/Ollama available:
   - Embed query via OllamaEmbedder
   - Search Qdrant (dense) and PostgreSQL (FTS) in parallel
   - Merge via Reciprocal Rank Fusion (60/40 weights)
3. If Qdrant unavailable: fall back to FTS-only
4. Store results in cache, return top-k

### Auto-Ingestion Flow (Hook)

```
Claude Code Write/Edit
        │
        ▼
PostToolUse Hook ──→  hook_handler.py
        │                  │
        │           is_oracle_brain_path()? (κ/ψ check)
        │                  │
        │           extract_metadata() → scope, doc_type, oracle_name
        │                  │
        │           Push.push_text() ──→ PG + Qdrant
        │
        ▼
   stdout JSON result
```

### Reconciliation Flow (Scheduled)

```
TaskScheduler (background)
        │
   ┌────┴────┐
   │         │
Scan Loop  Reconcile Loop
(every N s) (daily at 2 AM)
   │         │
   ▼         ▼
init_scan  reconcile()
(project   │
 files)    ├── defrag() ──→ find duplicates ──→ supersede()
           │
           └── detox() ──→ LLM conflict analysis ──→ supersede()
```

---

## Key Design Decisions

### 1. Dual-Store Architecture (PostgreSQL + Qdrant)
- **Rationale**: PostgreSQL provides ACID transactions, relational queries, FTS, and schema stability. Qdrant provides fast vector similarity. Neither alone covers all retrieval needs.
- **Trade-off**: Write amplification (every document written to two stores). Mitigated by async batching and dedup.

### 2. Supersession Instead of Deletion
- **Rationale**: Immutable history for auditability, traceability, and conflict resolution
- **Mechanism**: `superseded_by` UUID column links old → new. Queries filter `WHERE superseded_by IS NULL`
- **Implication**: Storage grows monotonically; `defrag` compacts duplicates

### 3. Graceful Degradation (FTS Fallback)
- **Rationale**: Local-first means users may not have Qdrant or Ollama running
- **Mechanism**: Try/catch around Qdrant/Ollama connections. If either fails, system continues with PG-only FTS
- **User impact**: `synapse status` reports which services are available

### 4. Local-Only Enforcement
- **Rationale**: Prevent accidental data exfiltration to cloud services
- **Mechanism**: `local_only.py` validates all URLs (database, Qdrant, Ollama, API host) are localhost/127.0.0.1/::1
- **Exception**: Docker `host.docker.internal` allowed when `SYNAPSE_ALLOW_EXTERNAL=1`

### 5. Oracle-Aware Document Types
- **Rationale**: The Oracle ecosystem uses κ (intrinsic) and ψ (extrinsic) brain structure
- **Mechanism**: `oracle_paths.py` maps file paths to `doc_type` and `brain_tier` based on regex rules
- **Types**: `learning`, `pattern`, `retro`, `reference`, `handoff`, `protocol`, `wisdom`, `instinct`, `log`, `note`

### 6. RRF Fusion (60% Dense / 40% FTS)
- **Rationale**: Dense vectors capture semantic similarity; FTS captures exact keyword matches. RRF combines both without calibration.
- **Parameters**: `k=60` (RRF constant), weights `[0.6, 0.4]`
- **Fallback**: If one search returns empty, return the other directly

### 7. Three-Way Access Pattern
- **Rationale**: Different consumption contexts need different interfaces
- **Interfaces**:
  - **Oracle Skill (auto)**: Hook handler auto-ingests κ/ψ files
  - **Direct MCP (manual)**: Claude Code conversation tools
  - **CLI (terminal)**: Scripting, automation, CI/CD
  - **HTTP API**: Docker services, external integrations

### 8. Project Registry + Cross-Scope Search
- **Rationale**: Knowledge should be searchable across projects, not siloed
- **Mechanism**: `registered_projects` table tracks scope → path mappings. Backup/restore to JSON for durability.
- **Cross-scope**: `search_cross_scope()` runs per-scope search then merges via RRF for fairness

### 9. Background Scheduler
- **Rationale**: Keep vault current without manual intervention
- **Tasks**:
  - **Scan**: Periodically walk registered projects, ingest new/modified files
  - **Reconcile**: Daily defrag (dedup) + detox (conflict detection)
- **Lifecycle**: Managed by FastAPI startup/shutdown events; PID file for daemon tracking

### 10. Config Hot-Reload
- **Rationale**: Avoid restart when changing settings
- **Mechanism**: SIGHUP handler triggers `settings.reload()`, re-reading env vars + YAML
- **Scope**: Runtime-tunable settings only (connection strings require restart)

---

## Testing Strategy

| Layer | Approach | Fixtures |
|-------|----------|----------|
| Unit | Mock Ollama at `httpx.post` level | `clean_pg`, `push`, `search` |
| Integration | Real PostgreSQL via `testcontainers` | `pg_store`, `api_client` |
| API | `httpx.AsyncClient` with `ASGITransport` | `api_client` |

Key test files:
- `tests/test_pg_store.py` — PostgreSQL CRUD, FTS, supersession
- `tests/test_qdrant_store.py` — Vector upsert/search (optional Qdrant)
- `tests/test_hybrid_search.py` — RRF fusion, cross-scope
- `tests/test_api_routes.py` — HTTP endpoint contracts
- `tests/test_mcp_server.py` — MCP tool definitions
- `tests/test_hook_handler.py` — Auto-ingest logic
- `tests/test_cli.py` — CLI argument parsing

---

## Operational Notes

### Startup Sequence
1. Parse settings (env → YAML)
2. Connect PostgreSQL, run idempotent schema init
3. Restore project registry from JSON backup if DB empty
4. Connect Qdrant (optional), create collection if missing
5. Initialize Ollama embedder (optional)
6. Wire API routes with initialized stores
7. Start background scheduler if enabled

### Shutdown Sequence
1. Stop background scheduler (cancel async tasks)
2. Close PostgreSQL pool
3. Close Qdrant client
4. Remove PID file (if daemon)

### Health Endpoints
- `/api/health` — Quick: qdrant boolean, embedding boolean
- `/api/health/live` — Liveness: always returns 200
- `/api/health/ready` — Readiness: PG connected, Qdrant reachable, embedding responsive

---

## Migration from v2 → v3

v3 replaced SQLite + LanceDB with PostgreSQL + Qdrant:
- **Storage**: SQLite FTS5 → PostgreSQL tsvector (richer query language, concurrent access)
- **Vectors**: LanceDB (local files) → Qdrant (service, payload filtering)
- **Schema**: Added `registered_projects`, `trace`, `concepts`, `document_concepts`, `supersede_log`
- **API**: Expanded from basic search/push to 18 endpoints including chat, ingest, health, models
- **MCP**: Grew from ~8 tools to 14 tools (cross-scope search, project registry)
- **Config**: Moved from per-project `.synapse/config.yaml` to centralized `~/.synapse/config.yaml`

---

## Glossary

| Term | Definition |
|------|------------|
| **Scope** | Namespace for documents (e.g., `shared`, `my-project`) |
| **Supersession** | Immutable update: old doc linked to new, never deleted |
| **Trace** | Directed relationship between documents (derived_from, refines, contradicts, extends) |
| **Oracle** | A Claude Code persona with κ/ψ brain structure |
| **Brain Tier** | `intrinsic` (core identity) or `extrinsic` (learned knowledge) |
| **RRF** | Reciprocal Rank Fusion: combines ranked lists without score calibration |
| **Defrag** | Compact duplicate documents by superseding older copies |
| **Detox** | LLM-powered conflict detection and resolution between documents |

---

*Document generated from source analysis of synapse v3 codebase.*
