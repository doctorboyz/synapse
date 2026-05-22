# Synapse v3 — API Surface Reference

> Comprehensive documentation of all public APIs, extension points, integration patterns,
> and plugin/middleware architecture. Generated 2026-05-05 from source analysis.

---

## 1. MCP Tools (10 Tools)

Synapse exposes 10 MCP tools over the stdio transport. All tools return `TextContent` wrapping a JSON payload. Errors are returned as `{"error": "<message>"}` objects, never as MCP error codes.

### 1.1 synapse_search

Hybrid dense+keyword search across the knowledge vault.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | **yes** | — | Search query text |
| `scope` | string | no | null | Filter to a specific scope |
| `doc_type` | string | no | null | Filter by document type (see valid types below) |
| `oracle` | string | no | null | Filter by oracle name |
| `source_project` | string | no | null | Filter by source project |
| `concepts` | array[string] | no | null | Filter by concept tags |
| `limit` | integer | no | 10 | Maximum results to return |
| `mode` | enum | no | "hybrid" | Search mode: `hybrid`, `dense`, or `fts` |

**Response**: JSON array of result objects:
```json
[
  {
    "id": "uuid",
    "title": "string",
    "scope": "string",
    "doc_type": "string",
    "oracle_name": "string|null",
    "source_project": "string|null",
    "score": 0.0123
  }
]
```

**Search modes**:
- `hybrid` — Qdrant dense (60%) + PostgreSQL tsvector FTS (40%), fused via Reciprocal Rank Fusion. Falls back to FTS-only if Qdrant or Ollama is unavailable.
- `dense` — Qdrant vector similarity only. Requires Qdrant + OllamaEmbedder. Raises `SearchError` if unavailable.
- `fts` — PostgreSQL tsvector keyword search only.

---

### 1.2 synapse_push

Add knowledge to the vault. Auto-detects oracle metadata from `source_file` path.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `title` | string | **yes** | — | Document title |
| `content` | string | **yes** | — | Document content (markdown) |
| `scope` | string | no | "shared" | Knowledge scope |
| `doc_type` | string | no | "learning" | Document type (see valid types below) |
| `source_file` | string | no | null | Original file path (used for oracle metadata extraction) |
| `source_project` | string | no | null | Project that sent this knowledge |
| `concepts` | array[string] | no | null | Concept tags |
| `tags` | array[string] | no | null | Freeform tags (stored as JSONB) |
| `oracle_name` | string | no | null | Oracle name |
| `brain_path` | string | no | null | Relative path within oracle brain structure |
| `brain_tier` | string | no | null | `extrinsic` or `intrinsic` |

**Response**:
```json
{"id": "uuid", "scope": "shared", "status": "indexed"}
```
Possible `status` values:
- `"indexed"` — Successfully written to PostgreSQL and Qdrant
- `"indexed_pg_only"` — Written to PostgreSQL only (embedding/vector failed)
- `"duplicate"` — Content hash + scope already exists; no write performed

**Deduplication**: Content is SHA-256 hashed (first 16 hex chars). If a document with the same `content_hash` AND `scope` exists, the push is rejected as a duplicate.

---

### 1.3 synapse_supersede

Replace a document with updated knowledge. The old document is never deleted; it is marked with `superseded_by`.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `old_id` | string | **yes** | — | UUID of the document to supersede |
| `new_content` | string | **yes** | — | Updated content |
| `new_title` | string | no | null | Optional new title (defaults to old title) |
| `reason` | string | no | "updated" | Reason for supersession (logged) |

**Response**:
```json
{"id": "uuid-of-new-doc", "superseded": "uuid-of-old-doc", "status": "superseded"}
```

**Behavior**:
- Creates a new document inheriting all metadata (scope, doc_type, oracle_name, etc.) from the old document
- Sets `superseded_by` on the old document to point to the new one
- Logs the supersession in the `supersede_log` table
- Marks the Qdrant vector as superseded (if available)
- Raises `ValueError` if old document not found or already superseded

---

### 1.4 synapse_trace

Create a trace link (knowledge graph edge) between two documents.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source_id` | string | **yes** | — | UUID of the source document |
| `target_id` | string | **yes** | — | UUID of the target document |
| `relation` | enum | **yes** | — | `derived_from`, `refines`, `contradicts`, `extends` |
| `confidence` | number | no | 1.0 | Confidence score (0.0–1.0) |

**Response**:
```json
{"id": "uuid", "source_id": "...", "target_id": "...", "relation": "derived_from"}
```

---

### 1.5 synapse_trace_chain

Follow a trace chain from a document, traversing the knowledge graph.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doc_id` | string | **yes** | — | UUID of the starting document |
| `direction` | enum | no | "both" | `both`, `upstream`, or `downstream` |
| `max_depth` | integer | no | 5 | Maximum traversal depth |
| `relation` | string | no | null | Filter to a specific relation type |

**Response**: JSON array of trace edges:
```json
[
  {
    "source_id": "uuid",
    "target_id": "uuid",
    "relation": "refines",
    "confidence": 1.0
  }
]
```

---

### 1.6 synapse_concepts

List or search concepts across the knowledge vault.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `search` | string | no | null | Search concepts by name (ILIKE match) |
| `limit` | integer | no | 50 | Maximum results |

**Response**: JSON array of concept objects:
```json
[
  {"name": "docker", "description": null, "doc_count": 5}
]
```

---

### 1.7 synapse_get

Retrieve a full knowledge document by UUID, including supersession history.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | string | **yes** | — | Document UUID |
| `include_chain` | boolean | no | true | Include supersession chain |

**Response**: Full document object (all columns from `knowledge_documents` table). If `include_chain=true` and the document is superseded, a `supersession_chain` array is appended. Returns `{"error": "not found"}` if the UUID does not exist.

---

### 1.8 synapse_scope

List all knowledge scopes with document counts.

| Parameters | None |

**Response**: JSON array:
```json
[
  {"name": "shared", "description": null, "doc_count": 42, "oracle_name": null}
]
```

---

### 1.9 synapse_stats

Get knowledge vault statistics.

| Parameters | None |

**Response**:
```json
{
  "total_documents": 100,
  "by_type": {"learning": 50, "pattern": 20, "retro": 10, ...},
  "by_scope": {"shared": 60, "emily": 40},
  "by_oracle": {"emily": 40}
}
```

All counts exclude superseded documents.

---

### 1.10 synapse_list

List documents with filters. Returns summaries (not full content).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scope` | string | no | null | Filter by scope |
| `doc_type` | string | no | null | Filter by document type |
| `oracle` | string | no | null | Filter by oracle name |
| `limit` | integer | no | 20 | Maximum results |
| `offset` | integer | no | 0 | Pagination offset |
| `order` | enum | no | "newest" | Sort: `newest` or `oldest` |

**Response**: JSON array of document summaries:
```json
[
  {
    "id": "uuid",
    "title": "string",
    "scope": "shared",
    "doc_type": "learning",
    "oracle_name": "emily",
    "source_project": "my-project",
    "created_at": "2026-05-05T12:00:00+00:00"
  }
]
```

---

## 2. HTTP API Endpoints

The FastAPI HTTP server mirrors the MCP tool interface, providing the same capabilities for Docker/service access. All endpoints are under the `/api` prefix. Base URL defaults to `http://0.0.0.0:8420`.

### 2.1 POST /api/search

Request body (JSON):
```json
{
  "query": "string (required)",
  "scope": "string|null",
  "doc_type": "string|null",
  "oracle": "string|null",
  "source_project": "string|null",
  "concepts": ["string"]|null,
  "limit": 10,
  "mode": "hybrid"
}
```
Response: Same as `synapse_search` MCP tool.

### 2.2 POST /api/push

Request body (JSON):
```json
{
  "title": "string (required)",
  "content": "string (required)",
  "scope": "shared",
  "doc_type": "learning",
  "source_file": "string|null",
  "source_type": "api",
  "source_project": "string|null",
  "concepts": ["string"]|null,
  "tags": ["string"]|null,
  "oracle_name": "string|null",
  "brain_path": "string|null",
  "brain_tier": "string|null"
}
```
Response: Same as `synapse_push` MCP tool. Note: HTTP endpoint defaults `source_type` to `"api"` (MCP defaults to `"manual"`).

### 2.3 POST /api/webhook

Webhook endpoint for external project integrations. Identical to `/api/push` but defaults `source_type` to `"webhook"`. All body fields from `/api/push` are accepted.

### 2.4 POST /api/supersede

Request body (JSON):
```json
{
  "old_id": "uuid (required)",
  "new_content": "string (required)",
  "reason": "updated",
  "new_title": "string|null"
}
```

### 2.5 POST /api/trace

Request body (JSON):
```json
{
  "source_id": "uuid (required)",
  "target_id": "uuid (required)",
  "relation": "derived_from|refines|contradicts|extends (required)",
  "confidence": 1.0
}
```

### 2.6 GET /api/trace/{doc_id}

Query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `direction` | string | "both" | `both`, `upstream`, `downstream` |
| `max_depth` | integer | 5 | Max traversal depth |
| `relation` | string | null | Filter by relation type |

### 2.7 GET /api/concepts

Query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | string | null | Search by name |
| `limit` | integer | 50 | Max results |

### 2.8 GET /api/documents/{doc_id}

Query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_chain` | boolean | true | Include supersession chain |

Returns 404 if document not found.

### 2.9 GET /api/scopes

No parameters. Returns scope list.

### 2.10 GET /api/stats

No parameters. Returns vault statistics.

### 2.11 GET /api/documents

Query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scope` | string | null | Filter by scope |
| `doc_type` | string | null | Filter by type |
| `oracle` | string | null | Filter by oracle |
| `limit` | integer | 20 | Max results |
| `offset` | integer | 0 | Pagination offset |
| `order` | string | "newest" | `newest` or `oldest` |

### 2.12 GET /api/health

No parameters. Returns:
```json
{
  "status": "ok",
  "qdrant": true|false,
  "embedding": true|false
}
```

---

## 3. Extension Points / Hooks

### 3.1 hook_handler.py — PostToolUse Auto-Ingest

**File**: `/src/ingest/hook_handler.py`

This is the Claude Code PostToolUse hook. When Claude writes or edits a file under a `kappa/` or `psi/` path, this handler automatically ingests the file into Synapse.

**Activation path**: The hook is triggered for files where `is_oracle_brain_path()` returns true — i.e., the path contains a directory named `κ` or `ψ`.

**Flow**:
1. `is_oracle_brain_path(file_path)` — checks if path contains `κ` or `ψ` directory
2. `find_oracle_root(file_path)` — walks up the directory tree to find the project root (directory containing `CLAUDE.md`)
3. `extract_metadata(file_path, oracle_root)` — resolves doc_type, brain_tier, oracle_name from the path (see oracle_paths below)
4. `Push.push_text(...)` — writes to PostgreSQL and optionally Qdrant

**CLI entry point**: `python -m src.ingest.hook_handler <file_path>`

The handler can receive the file path either:
- As a command-line argument: `sys.argv[1]`
- Via stdin JSON: `{"file_path": "...", "tool_input": {"file_path": "..."}}`

**Graceful degradation**: If Qdrant or Ollama is unavailable, the hook still ingests into PostgreSQL (embedder set to None, `embed=False`).

**How to wire into Claude Code** (settings.json):
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "command": "python -m src.ingest.hook_handler",
        "input_format": "json"
      }
    ]
  }
}
```

### 3.2 oracle_paths.py — Path-to-Metadata Mapping

**File**: `/src/ingest/oracle_paths.py`

This is the central configuration for mapping oracle brain file paths to Synapse metadata. It defines the rules that determine `doc_type` and `brain_tier` from a file's position in the directory tree.

**Path rules** (`ORACLE_PATH_RULES`):

| Pattern | doc_type | brain_tier |
|---------|----------|------------|
| `ψ/memory/learnings/` | learning | extrinsic |
| `ψ/memory/retrospectives/` | retro | extrinsic |
| `ψ/outbox/` | handoff | extrinsic |
| `κ/extrinsic/wisdom/knowledge/` | wisdom | extrinsic |
| `κ/extrinsic/wisdom/reference/` | reference | extrinsic |
| `κ/extrinsic/experience/learn/` | learning | extrinsic |
| `κ/extrinsic/experience/work/logs/` | log | extrinsic |
| `κ/intrinsic/instinct/` | instinct | intrinsic |
| `κ/intrinsic/identity/` | instinct | intrinsic |
| `κ/intrinsic/inherit/` | instinct | intrinsic |

**Fallback**: Any file that matches the oracle brain path (κ/ or ψ/) but does not match any rule gets `doc_type="note"` and `brain_tier="extrinsic"`.

**Valid doc types** (`VALID_DOC_TYPES`):
`learning`, `pattern`, `retro`, `reference`, `handoff`, `protocol`, `wisdom`, `instinct`, `log`, `note`

**Valid trace relations** (`VALID_TRACE_RELATIONS`):
`derived_from`, `refines`, `contradicts`, `extends`

**How to add a new doc type**:
1. Add the type string to `VALID_DOC_TYPES` in `oracle_paths.py`
2. Optionally add a path rule to `ORACLE_PATH_RULES` mapping a directory pattern to the new type
3. The PostgreSQL schema does not enforce doc_type as an enum — any string is accepted at the DB level. The validation is application-level only.

**`extract_oracle_name(repo_path)`**: Strips `-oracle` suffix from the repository basename. Example: `/path/to/emily-oracle` becomes `emily`.

---

## 4. Integration Patterns

### 4.1 Claude Code Integration (MCP stdio)

Claude Code connects to Synapse via the MCP stdio protocol. The transport is defined in `src/mcp/server.py`:

```python
async with stdio_server() as (read_stream, write_stream):
    await app.run(read_stream, write_stream, app.create_initialization_options())
```

**Setup**: Add to Claude Code's MCP server configuration:
```json
{
  "mcpServers": {
    "synapse": {
      "command": "synapse",
      "args": ["mcp"]
    }
  }
}
```

Or equivalently:
```json
{
  "mcpServers": {
    "synapse": {
      "command": "python",
      "args": ["-m", "src.mcp.server"]
    }
  }
}
```

### 4.2 HTTP Service Integration

For Docker containers or non-MCP clients, use the HTTP API:

```bash
synapse serve    # Starts FastAPI on 0.0.0.0:8420
```

**Initialization flow** (`src/main.py`):
1. `startup()` creates `PgStore`, connects, runs `init_schema()` (idempotent)
2. Attempts Qdrant connection; falls back to FTS-only mode if unavailable
3. Creates `OllamaEmbedder`, calls `init_routes()` to wire dependencies into the router

### 4.3 Webhook Integration (External Projects)

External projects can push knowledge via `POST /api/webhook`:
```bash
curl -X POST http://localhost:8420/api/webhook \
  -H "Content-Type: application/json" \
  -d '{"title": "CI pattern", "content": "Use compose v2..."}'
```

The `source_type` is automatically set to `"webhook"`. This distinguishes externally-pushed documents from those ingested via MCP (`"manual"`) or hooks (`"hook"`).

### 4.4 Hook-Based Auto-Ingest Integration

When a file is written under a `κ/` or `ψ/` directory path, the PostToolUse hook auto-ingests it with:
- `source_type = "hook"`
- `source_project = <oracle repo basename>`
- Oracle metadata auto-extracted from the path

---

## 5. Plugin / Middleware Architecture

### 5.1 Configuration-Driven Behavior

All runtime behavior is configurable via environment variables, managed through `src/config.py` `Settings` dataclass:

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| `database_url` | `DATABASE_URL` | `postgresql://admin:88888888@localhost:5432/mysynapse` | PostgreSQL connection string |
| `qdrant_url` | `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `qdrant_collection` | `QDRANT_COLLECTION` | `mysynapse_vectors` | Qdrant collection name |
| `ollama_url` | `OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `embedding_model` | `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `embedding_dim` | `EMBEDDING_DIM` | 768 | Vector dimensionality |
| `embedding_timeout` | `EMBEDDING_TIMEOUT` | 30 | Ollama request timeout (seconds) |
| `api_host` | `MYSYNAPSE_HOST` | `0.0.0.0` | HTTP server bind address |
| `api_port` | `MYSYNAPSE_PORT` | 8420 | HTTP server bind port |
| `log_level` | `LOG_LEVEL` | `INFO` | Logging level |
| `search_weights` | `SEARCH_WEIGHTS` | `0.6,0.4` | RRF weights: [dense, fts] |
| `search_rrf_k` | (hardcoded) | 60 | RRF k constant |
| `cache_ttl` | `CACHE_TTL` | 300 | Cache time-to-live (seconds) |
| `cache_max_size` | `CACHE_MAX_SIZE` | 1000 | Maximum cache entries |

### 5.2 Dual-Store Architecture (Pluggable Backends)

The system writes to two stores simultaneously:

1. **PostgreSQL** (`PgStore`) — Always active. Stores full documents, FTS index, metadata, traces, concepts. Required.
2. **Qdrant** (`QdrantStore`) — Optional. Stores dense vectors with payload filtering. If unavailable, the system falls back to FTS-only search.

The `Push` class orchestrates dual writes:
```python
push = Push(pg, qdrant, embedder)  # qdrant and embedder can be None
```

The `HybridSearch` class handles degradation:
- If Qdrant+embedder available: hybrid RRF fusion (default)
- If Qdrant or embedder unavailable: FTS-only fallback
- `mode="dense"` requires both; raises `SearchError` if missing

### 5.3 Embedding Provider (Pluggable)

The `OllamaEmbedder` class can be replaced with any class that implements:
- `async embed(text: str) -> list[float]` — embed a single text
- `async check() -> bool` — health check

Current implementation:
- Model: `nomic-embed-text` (768 dimensions)
- Max chunk size: 4000 characters (truncated)
- Retry: 2 retries with exponential backoff (0.5s, 1.0s, 2.0s)
- Batch: Semaphore(4) for concurrency control

### 5.4 Search Fusion (Configurable Weights)

The `HybridSearch` class uses Reciprocal Rank Fusion (RRF) to merge dense and keyword results:
```python
score = weight / (k + rank)
```

Default weights: `[0.6, 0.4]` (dense=60%, fts=40%), configurable via `SEARCH_WEIGHTS` env var.
RRF k constant: 60 (hardcoded in `Settings.search_rrf_k`).

### 5.5 Schema (Idempotent Migrations)

The PostgreSQL schema (`src/db/schema.sql`) is run on every startup via `PgStore.init_schema()`. All DDL uses `IF NOT EXISTS`, making it safe for repeated execution.

**Tables**:
- `knowledge_documents` — Core document store with tsvector, JSONB concepts/tags, supersession
- `supersede_log` — Audit trail for supersessions
- `scope_registry` — Scope names with document counts and optional oracle association
- `concepts` — Concept dictionary
- `document_concepts` — Many-to-many between documents and concepts
- `trace` — Knowledge graph edges (source, target, relation, confidence)

**Indexes** (all conditional on `superseded_by IS NULL`):
- GIN on `search_vector` (full-text search)
- B-tree on `scope`, `doc_type`, `oracle_name`, `brain_tier`, `source_project`
- B-tree on `content_hash` (deduplication)

**Trigger**: `trg_search_vector` auto-populates `search_vector` from title (weight A), content (weight B), and concepts (weight C) using English tsvector.

### 5.6 Adding New Extension Points

**New doc types**: Add to `VALID_DOC_TYPES` set and optionally to `ORACLE_PATH_RULES` in `oracle_paths.py`. No schema change required.

**New trace relations**: Add to `VALID_TRACE_RELATIONS` set in `oracle_paths.py`. The `trace` table stores relation as free text; validation is application-level.

**New oracle path patterns**: Append a `(pattern, doc_type, brain_tier)` tuple to `ORACLE_PATH_RULES`. The `pattern` is matched with Python `in` (substring match) against the relative path.

**New search mode**: Extend `HybridSearch.search()` with a new `mode` branch. Register the mode in the MCP tool's `inputSchema` enum and the HTTP endpoint's documentation.

**New embedding provider**: Implement `embed(text) -> list[float]` and `check() -> bool` async methods. Pass the new provider to `Push` and `HybridSearch` constructors.

**New HTTP endpoint**: Add a route function to `src/api/routes.py` under the `router` APIRouter. Follow the existing pattern of calling `pg.*` or `search.*` methods.

**New MCP tool**: Add a `Tool(...)` definition to `TOOL_DEFINITIONS` in `src/mcp/server.py`, then add a handler branch in the `call_tool` function.

---

## 6. Key Source Files

| File | Purpose |
|------|---------|
| `src/mcp/server.py` | MCP stdio server — 10 tool definitions and dispatch |
| `src/api/routes.py` | FastAPI HTTP routes — mirrors MCP interface |
| `src/ingest/hook_handler.py` | PostToolUse hook — auto-ingest on file write |
| `src/ingest/oracle_paths.py` | Path-to-metadata mapping, validation constants |
| `src/ingest/push.py` | Knowledge ingestion — dual-store write orchestration |
| `src/retrieve/hybrid_search.py` | Hybrid search — RRF fusion of dense + keyword |
| `src/db/pg_store.py` | PostgreSQL store — CRUD, FTS, supersession, traces |
| `src/db/qdrant_store.py` | Qdrant vector store — upsert, search, mark superseded |
| `src/db/schema.sql` | Idempotent PostgreSQL schema |
| `src/embed/ollama.py` | Async Ollama embedder with retry and batch |
| `src/config.py` | Settings dataclass from environment variables |
| `src/main.py` | FastAPI app + CLI entry point (`serve` / `mcp`) |

---

## 7. Quick Reference: Enumerated Values

### Document Types
`learning` | `pattern` | `retro` | `reference` | `handoff` | `protocol` | `wisdom` | `instinct` | `log` | `note`

### Trace Relations
`derived_from` | `refines` | `contradicts` | `extends`

### Search Modes
`hybrid` | `dense` | `fts`

### Source Types (internal)
`manual` (MCP) | `api` (HTTP push) | `webhook` (webhook) | `hook` (auto-ingest)

### Brain Tiers
`extrinsic` | `intrinsic`

### Push Status Values
`indexed` | `indexed_pg_only` | `duplicate`
