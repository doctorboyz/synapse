# Synapse v3 API Surface Documentation

Generated from source exploration of the `v3` branch.

---

## 1. Public API (HTTP Endpoints)

The HTTP API is a FastAPI application (`src/api/routes.py`) that mirrors the MCP tool interface, enabling Docker service access and third-party integrations. All routes are prefixed with `/api`.

### 1.1 Search

#### `POST /api/search`
Hybrid dense + keyword search with RRF fusion.

**Request:**
```json
{
  "query": "asyncpg connection pooling",
  "scope": "synapse",
  "doc_type": "learning",
  "oracle": "doctorboyz",
  "source_project": "synapse",
  "concepts": ["asyncpg", "postgres"],
  "limit": 10,
  "mode": "hybrid"
}
```

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Connection Pool Tuning",
    "scope": "synapse",
    "doc_type": "learning",
    "oracle_name": "doctorboyz",
    "source_project": "synapse",
    "score": 0.85
  }
]
```

**Modes:** `hybrid` (default), `dense`, `fts`.

#### `POST /api/search-cross`
Search across multiple scopes, merging results by best score.

**Request:**
```json
{
  "query": "docker deployment",
  "scopes": ["synapse", "my-other-project"],
  "limit": 10,
  "mode": "hybrid"
}
```

### 1.2 Knowledge Push

#### `POST /api/push`
Add knowledge to the vault. Auto-detects oracle metadata from `source_file` path.

**Request:**
```json
{
  "title": "New Design Pattern",
  "content": "# Observer Pattern...",
  "scope": "shared",
  "doc_type": "pattern",
  "source_file": "/path/to/file.md",
  "source_project": "my-project",
  "concepts": ["design-patterns", "observer"],
  "tags": ["architecture"],
  "oracle_name": "doctorboyz",
  "brain_path": "κ/extrinsic/wisdom/knowledge/patterns.md",
  "brain_tier": "extrinsic"
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "scope": "shared",
  "status": "indexed"
}
```

**Doc Types:** `learning`, `pattern`, `retro`, `reference`, `handoff`, `protocol`, `wisdom`, `instinct`, `log`, `note`.

#### `POST /api/webhook`
Alias for `/api/push` that defaults `source_type` to `webhook`.

### 1.3 Document Lifecycle

#### `POST /api/supersede`
Supersede a document with updated knowledge. The old document is never deleted; it is marked with `superseded_by`.

**Request:**
```json
{
  "old_id": "550e8400-e29b-41d4-a716-446655440000",
  "new_content": "Updated content here...",
  "new_title": "Updated Title",
  "reason": "correction"
}
```

#### `GET /api/documents/{doc_id}`
Retrieve a full document by ID.

**Query Params:**
- `include_chain` (bool, default `true`): Include supersession history.

**Response:** Full document row from `knowledge_documents` including `content`, `concepts`, `tags`, `summary`, and optionally `supersession_chain`.

#### `GET /api/documents`
List documents with filters and pagination.

**Query Params:**
- `scope`, `doc_type`, `oracle`
- `limit` (default 20), `offset` (default 0)
- `order`: `newest` or `oldest`

### 1.4 Trace (Provenance)

#### `POST /api/trace`
Create a trace link between two documents.

**Request:**
```json
{
  "source_id": "...",
  "target_id": "...",
  "relation": "derived_from",
  "confidence": 1.0
}
```

**Relations:** `derived_from`, `refines`, `contradicts`, `extends`.

#### `GET /api/trace/{doc_id}`
Follow trace chain from a document.

**Query Params:**
- `direction`: `both` (default), `upstream`, `downstream`
- `max_depth`: default 5
- `relation`: filter to a specific relation type

### 1.5 Concepts

#### `GET /api/concepts`
List or search concepts.

**Query Params:** `search` (string), `limit` (default 50).

**Response:**
```json
[
  {
    "name": "asyncpg",
    "description": null,
    "doc_count": 12
  }
]
```

### 1.6 Scope & Stats

#### `GET /api/scopes`
List all knowledge scopes with document counts.

#### `GET /api/stats`
Vault statistics.

**Response:**
```json
{
  "total_documents": 150,
  "by_type": {"learning": 80, "pattern": 20},
  "by_scope": {"synapse": 100, "shared": 50},
  "by_oracle": {"doctorboyz": 120}
}
```

### 1.7 Project Registry

#### `POST /api/register`
Register a project for cross-project search.

**Request:** `{"project_path": "/path/to/project", "scope": "my-project"}`

#### `POST /api/unregister`
Remove a project registration.

**Request:** `{"scope": "my-project"}`

#### `GET /api/projects`
List all registered projects.

### 1.8 Health

#### `GET /api/health`
Basic health check.

**Response:** `{"status": "ok", "qdrant": true, "embedding": true}`

#### `GET /api/health/live`
Liveness probe. Returns `{"alive": true}`.

#### `GET /api/health/ready`
Readiness probe. Checks PostgreSQL, Qdrant, and Embedding availability.

**Response:**
```json
{
  "ready": true,
  "pg": true,
  "qdrant": true,
  "embedding": true
}
```

### 1.9 Ingest Extensions

#### `POST /api/ingest/youtube`
Extract YouTube transcript and push to vault. Falls back to basic URL ingestion.

**Request:** `{"url": "https://youtube.com/watch?v=...", "scope": "shared"}`

#### `POST /api/ingest/website`
Scrape website content and push to vault.

**Request:** `{"url": "https://example.com", "scope": "shared"}`

#### `POST /api/ingest/file`
Upload a file (multipart/form-data), parse content (txt, md, pdf, docx), and push to vault.

### 1.10 Chat

#### `POST /api/chat`
Stream a chat response using search context + Ollama LLM.

**Request:**
```json
{
  "query": "How does connection pooling work?",
  "model": "qwen2.5:7b",
  "scope": "synapse",
  "scopes": ["synapse", "shared"]
}
```

**Response:** `text/plain` streaming response. The first chunk is a metadata prefix `__SOURCES__[{...}]__SOURCES__` containing citation information, followed by the LLM-generated text.

### 1.11 Utilities

#### `POST /api/resolve-links`
Resolve Obsidian-style `[[Link]]` targets to document IDs.

**Request:** `{"content": "See [[Connection Pooling]] for details", "scope": "synapse"}`

**Response:**
```json
{
  "resolved": {"Connection Pooling": "550e8400-..."},
  "unresolved": []
}
```

#### `POST /api/suggest-scope`
Use LLM to suggest the best scope for given content.

**Request:** `{"content": "...", "scopes": ["synapse", "other"], "model": "qwen2.5:7b"}`

#### `GET /api/models`
List available Ollama models.

---

## 2. MCP Tools Interface

The MCP server (`src/mcp/server.py`) exposes 14 tools via stdio, designed for agent-first knowledge access. All tools return `[TextContent]` with JSON-encoded results.

| Tool | Description |
|------|-------------|
| `synapse_search` | Hybrid dense+keyword search. Returns ranked results. |
| `synapse_push` | Add knowledge to vault. Auto-detects oracle metadata. |
| `synapse_supersede` | Supersede a document. Old doc marked, never deleted. |
| `synapse_trace` | Create a trace link between two documents. |
| `synapse_trace_chain` | Follow trace chain from a document. |
| `synapse_concepts` | List or search concepts. |
| `synapse_get` | Retrieve full document by ID, including chain. |
| `synapse_scope` | List all scopes with counts. |
| `synapse_stats` | Vault statistics. |
| `synapse_list` | List documents with filters. |
| `synapse_register` | Register a project for cross-project search. |
| `synapse_unregister` | Remove a project registration. |
| `synapse_projects` | List registered projects. |
| `synapse_search_cross` | Search across multiple scopes. |

### Example: `synapse_search` Input Schema
```json
{
  "query": "string",
  "scope": "string (optional)",
  "doc_type": "string (optional)",
  "oracle": "string (optional)",
  "source_project": "string (optional)",
  "concepts": ["string"],
  "limit": 10,
  "mode": "hybrid"
}
```

### Example: `synapse_push` Input Schema
```json
{
  "title": "string",
  "content": "string",
  "scope": "shared",
  "doc_type": "learning",
  "source_file": "string (optional)",
  "source_project": "string (optional)",
  "concepts": ["string"],
  "tags": ["string"],
  "oracle_name": "string",
  "brain_path": "string",
  "brain_tier": "string"
}
```

---

## 3. CLI Commands

Entry point: `synapse` (defined in `pyproject.toml` as `src.main:cli_main`).

### Server Commands
- `synapse serve` — Start HTTP API server (port 8420 by default).
- `synapse mcp` — Start MCP stdio server.
- `synapse stop` — Stop running daemon via SIGTERM.
- `synapse status` — Show daemon and system status (includes DB stats, scopes, local-only violations).

### Knowledge Operations (JSON output)
- `synapse push --title "..." --content "..." --scope my-project`
- `synapse push --file path/to/doc.md --scope my-project`
- `synapse search "query" --scope my-project --mode hybrid`
- `synapse search-cross "query" --scopes proj-a,proj-b`
- `synapse get <doc-id> [--no-chain]`
- `synapse list --scope my-project --limit 20`
- `synapse scope` — List all scopes.
- `synapse stats` — Vault statistics.
- `synapse supersede <old-id> --new-content "..." [--new-title "..."] [--reason "..."]`
- `synapse trace --source <id> --target <id> --relation derived_from [--confidence 1.0]`
- `synapse trace-chain <doc-id> [--direction both] [--max-depth 5]`
- `synapse concepts [--search "async"] [--limit 50]`

### Project Management
- `synapse register --path /my/project --scope my-project`
- `synapse unregister my-project`
- `synapse projects` — List registered projects.

### Maintenance
- `synapse init --path . --scope my-project [--dry-run]` — Scan files + LLM summarization.
- `synapse reconcile [--scope my-project] [--dry-run]` — Defrag duplicates + detect/fix conflicts.
- `synapse scan` — Scan all registered projects for new files.
- `synapse install-hooks [--dry-run] [--python-path ...] [--script-path ...] [--settings-path ...]` — Register synapse hooks in `~/.claude/settings.json`.

### Global Flags (per command)
Most knowledge commands accept:
- `--scope`, `--doc-type`, `--oracle`, `--source-project`
- `--concepts` (comma-separated)
- `--limit`, `--mode` (`hybrid`, `dense`, `fts`)

---

## 4. Extension Points / Hooks

### 4.1 PostToolUse Auto-Ingest Hook
Installed by `synapse install-hooks`. Triggers on `Write|Edit|MultiEdit` operations in Claude Code.

**Behavior:**
- Checks if the modified file path contains `κ` or `ψ` (oracle brain structure).
- Finds the oracle project root by walking up to a directory containing `CLAUDE.md`.
- Extracts metadata (`oracle_name`, `brain_path`, `brain_tier`, `doc_type`, `scope`) via `src.ingest.oracle_paths`.
- Pushes the file content to synapse via the `Push` pipeline.

**Hook Definition:**
```json
{
  "matcher": "Write|Edit|MultiEdit",
  "hooks": [
    {
      "type": "command",
      "command": "python -m src.ingest.hook_handler \"$CLAUDE_CODE_FILEPATH\"",
      "timeout": 30
    }
  ]
}
```

### 4.2 PreToolUse Context Injection Hook
Installed alongside the ingest hook. Triggers on `Read|Glob|Grep`.

**Purpose:** Injects relevant synapse search results into the Claude Code context before tool execution, enabling the agent to access its own knowledge vault during development.

### 4.3 Hook Handler Entry Points
The hook handler (`src.ingest.hook_handler.py`) accepts the file path via:
1. CLI argument (`sys.argv[1]`)
2. Environment variable (`CLAUDE_CODE_FILEPATH`)
3. Stdin JSON (`{"tool_input": {"file_path": "..."}}`)

If no path is provided, it exits silently (non-blocking).

---

## 5. Integration Patterns

### 5.1 Three-Way Access Model
```
Oracle Skill (auto)  → hook_handler → MCP push (auto-ingest κ/ψ files)
Direct MCP (manual)  → synapse_search, synapse_push, etc. in conversation
CLI (terminal)       → synapse push/search/init/reconcile/etc.
HTTP API             → curl localhost:8420/api/search, /api/push, etc.
```

### 5.2 Dual-Store Write Pattern
All pushes write to **both** PostgreSQL and Qdrant:
1. **PostgreSQL**: Canonical store for documents, FTS, concepts, traces, scopes, stats.
2. **Qdrant**: Vector store for dense semantic search.

If Qdrant is unavailable, the system falls back to FTS-only mode (`indexed_pg_only` status).

### 5.3 Oracle-Aware Doc Types
The `oracle_paths.py` module maps the `κ/ψ` brain structure to `doc_type` and `brain_tier`:

| Path Pattern | Doc Type | Brain Tier |
|--------------|----------|------------|
| `ψ/memory/learnings/` | `learning` | `extrinsic` |
| `ψ/memory/retrospectives/` | `retro` | `extrinsic` |
| `ψ/outbox/` | `handoff` | `extrinsic` |
| `κ/extrinsic/wisdom/knowledge/` | `wisdom` | `extrinsic` |
| `κ/extrinsic/wisdom/reference/` | `reference` | `extrinsic` |
| `κ/extrinsic/experience/learn/` | `learning` | `extrinsic` |
| `κ/extrinsic/experience/work/logs/` | `log` | `extrinsic` |
| `κ/intrinsic/instinct/` | `instinct` | `intrinsic` |
| `κ/intrinsic/identity/` | `instinct` | `intrinsic` |
| `κ/intrinsic/inherit/` | `instinct` | `intrinsic` |

### 5.4 Obsidian Link Resolution
Content containing `[[Link Title]]` or `[[Link Title|Display]]` is automatically parsed during push. The system attempts to resolve links to existing documents (by exact title, case-insensitive title, source_file, or FTS fallback) and creates `references` trace links.

### 5.5 Config Hot-Reload
The `Settings` dataclass supports reloading via SIGHUP. `Settings.from_yaml()` loads `~/.synapse/config.yaml`, falling back to environment variables for missing keys.

---

## 6. Plugin / Middleware Architecture

Synapse v3 does not use a formal plugin system (no entry points or dynamic loading). Instead, it employs a **component-based architecture** where stores, embedders, and search strategies are swappable via dependency injection.

### 6.1 Swappable Components

| Component | Default | Interface | Swap Method |
|-----------|---------|-----------|-------------|
| Document Store | `PgStore` | `add`, `get`, `search_fts`, `supersede`, `list_docs`, `list_scopes`, `stats`, `add_trace`, `get_trace_chain`, `list_concepts` | Replace `src/db/pg_store.py` or inject new class |
| Vector Store | `QdrantStore` | `connect`, `upsert`, `search`, `mark_superseded`, `delete` | Replace `src/db/qdrant_store.py` |
| Embedder | `OllamaEmbedder` | `embed`, `embed_batch`, `check` | Replace `src/embed/ollama.py` |
| Search | `HybridSearch` | `search`, `search_cross_scope` | Replace `src/retrieve/hybrid_search.py` |
| Cache | `SearchCache` | `get`, `put`, `invalidate`, `clear`, `stats` | Replace `src/cache.py` |

### 6.2 Extension via Ingest Pipelines
New ingest sources can be added as FastAPI routes in `src/api/routes.py` following the pattern of `/api/ingest/youtube` and `/api/ingest/website`:
1. Accept input parameters.
2. Extract/fetch content.
3. Call `push.push_text(..., source_type="<new_source>")`.

### 6.3 Middleware Patterns
- **Local-Only Enforcement** (`src/local_only.py`): Validates all external URLs are localhost/Unix sockets. Violations are reported in `synapse status`.
- **Dedup Middleware** (`PgStore.add()`): Content is deduplicated by `(content_hash, scope)`.
- **Search Cache Middleware** (`HybridSearch`): LRU + TTL cache sits in front of search operations.

---

## 7. Data Models and Schemas

### 7.1 PostgreSQL Schema (`src/db/schema.sql`)

#### `knowledge_documents` (Core Table)
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, `gen_random_uuid()` |
| `title` | TEXT | NOT NULL |
| `content` | TEXT | NOT NULL |
| `content_hash` | TEXT | NOT NULL |
| `doc_type` | TEXT | NOT NULL DEFAULT `'learning'` |
| `scope` | TEXT | NOT NULL DEFAULT `'shared'` |
| `source_file` | TEXT | |
| `source_type` | TEXT | NOT NULL DEFAULT `'manual'` |
| `source_project` | TEXT | |
| `oracle_name` | TEXT | |
| `brain_path` | TEXT | |
| `brain_tier` | TEXT | |
| `concepts` | JSONB | DEFAULT `'[]'` |
| `tags` | JSONB | DEFAULT `'[]'` |
| `superseded_by` | UUID | FK `knowledge_documents(id)` |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT `NOW()` |
| `updated_at` | TIMESTAMPTZ | |
| `search_vector` | tsvector | Auto-updated via trigger |
| `summary` | TEXT | Added via `ALTER TABLE` |

**Constraints:**
- `UNIQUE(content_hash, scope)` — deduplication.
- `superseded_by IS NULL` is the active document filter used in almost all queries.

**Indexes:**
- `idx_doc_search` (GIN on `search_vector`)
- `idx_doc_scope` (partial, `superseded_by IS NULL`)
- `idx_doc_type` (partial)
- `idx_doc_oracle` (partial)
- `idx_doc_hash`
- `idx_doc_brain_tier` (partial)
- `idx_doc_source_project` (partial)

**Trigger:**
- `trg_search_vector` (BEFORE INSERT OR UPDATE): Builds weighted tsvector from `title` (weight A), `content` (weight B), and `concepts` (weight C).

#### `supersede_log`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `old_id` | UUID | FK `knowledge_documents(id)` |
| `new_id` | UUID | FK `knowledge_documents(id)` |
| `reason` | TEXT | DEFAULT `'updated'` |
| `timestamp` | TIMESTAMPTZ | DEFAULT `NOW()` |

#### `scope_registry`
| Column | Type | Constraints |
|--------|------|-------------|
| `name` | TEXT | PK |
| `description` | TEXT | |
| `doc_count` | INTEGER | DEFAULT 0 |
| `oracle_name` | TEXT | |
| `created_at` | TIMESTAMPTZ | DEFAULT `NOW()` |

Updated atomically on document insert (`ON CONFLICT DO UPDATE`).

#### `concepts`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `name` | TEXT | UNIQUE |
| `description` | TEXT | |
| `created_at` | TIMESTAMPTZ | DEFAULT `NOW()` |

#### `document_concepts` (Junction Table)
| Column | Type | Constraints |
|--------|------|-------------|
| `doc_id` | UUID | FK |
| `concept_id` | UUID | FK |
| PK | (`doc_id`, `concept_id`) |

#### `trace` (Provenance Graph)
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `source_id` | UUID | FK `knowledge_documents(id)` |
| `target_id` | UUID | FK `knowledge_documents(id)` |
| `relation` | TEXT | NOT NULL |
| `confidence` | REAL | DEFAULT 1.0 |
| `created_at` | TIMESTAMPTZ | DEFAULT `NOW()` |

**Indexes:** `idx_trace_source`, `idx_trace_target`.

#### `registered_projects`
| Column | Type | Constraints |
|--------|------|-------------|
| `scope` | TEXT | PK |
| `project_path` | TEXT | NOT NULL |
| `registered_at` | TIMESTAMPTZ | DEFAULT `NOW()` |

### 7.2 Qdrant Collection Schema
- **Collection Name:** `synapse_vectors` (configurable via `SYNAPSE_QDRANT_COLLECTION`)
- **Vector Params:** `size=768`, `distance=Cosine`
- **Payload Fields:**
  - `title` (string)
  - `scope` (string)
  - `doc_type` (string)
  - `oracle_name` (string, optional)
  - `brain_tier` (string, optional)
  - `concepts` (list of strings, optional)
  - `superseded` (bool) — used as a mandatory filter in all searches.

### 7.3 Configuration Model (`src/config.py`)
`Settings` dataclass with defaults from environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` / `SYNAPSE_DB_URL` | `postgresql://admin:88888888@localhost:5432/synapse` | PostgreSQL DSN |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant URL |
| `SYNAPSE_QDRANT_COLLECTION` | `synapse_vectors` | Qdrant collection name |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `EMBEDDING_DIM` | `768` | Embedding dimension |
| `EMBEDDING_TIMEOUT` | `30` | Embedding request timeout (seconds) |
| `SYNAPSE_HOST` | `0.0.0.0` | HTTP API host |
| `SYNAPSE_PORT` | `8420` | HTTP API port |
| `SYNAPSE_LOG_LEVEL` | `INFO` | Logging level |
| `SEARCH_WEIGHTS` | `0.6,0.4` | RRF weights (dense, fts) |
| `CACHE_TTL` | `300` | Search cache TTL (seconds) |
| `CACHE_MAX_SIZE` | `1000` | Search cache max entries |
| `SYNAPSE_PID_FILE` | `~/.synapse/synapse.pid` | Daemon PID file path |
| `SYNAPSE_SCAN_INTERVAL` | `0` | Background scan interval (seconds, 0=disabled) |
| `SYNAPSE_RECONCILE_HOUR` | `2` | Nightly reconcile hour (0-23) |
| `SYNAPSE_CONFIG` | `""` | Path to YAML config file |

---

## 8. Key Files Reference

| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI app + CLI entry point + argument parser |
| `src/api/routes.py` | HTTP API routes (18 endpoints) |
| `src/mcp/server.py` | MCP stdio server (14 tools) |
| `src/cli.py` | Async component lifecycle (get_components, cleanup) |
| `src/config.py` | Settings dataclass + YAML hot-reload |
| `src/db/schema.sql` | PostgreSQL schema definition |
| `src/db/pg_store.py` | PostgreSQL CRUD, FTS, traces, stats |
| `src/db/qdrant_store.py` | Qdrant vector operations |
| `src/embed/ollama.py` | Async Ollama embedder with retry |
| `src/ingest/push.py` | Dual-store write pipeline |
| `src/ingest/hook_handler.py` | PostToolUse auto-ingest handler |
| `src/ingest/oracle_paths.py` | `κ/ψ` path -> metadata mapping |
| `src/ingest/obsidian_links.py` | `[[Link]]` parsing and trace creation |
| `src/ingest/concepts.py` | Hashtag + CamelCase concept extraction |
| `src/retrieve/hybrid_search.py` | RRF fusion search + cross-scope search |
| `src/cache.py` | LRU + TTL search cache |
| `src/registry.py` | Project registration + backup/restore |
| `src/daemon.py` | PID file, signal handling (SIGTERM/SIGHUP) |
| `src/scheduler.py` | Background scan + nightly reconcile |
| `src/hooks/installer.py` | `~/.claude/settings.json` hook installer |
