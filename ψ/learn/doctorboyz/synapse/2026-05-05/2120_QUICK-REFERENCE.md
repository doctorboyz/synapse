# Synapse v3 — Quick Reference

## What It Does

Synapse v3 is a **Hybrid Knowledge Framework** that provides agent-first knowledge storage and retrieval. It combines PostgreSQL full-text search (tsvector) with Qdrant dense vector search, fusing results via **Reciprocal Rank Fusion (RRF)** at configurable weights (default 60% dense / 40% FTS). Documents are never deleted — outdated knowledge is **superseded**, preserving a full audit trail. An Oracle-aware path system maps kappa/psi brain structures to doc types and tiers automatically.

The system offers dual interfaces: a **10-tool MCP server** (stdio protocol for Claude Code integration) and an **HTTP REST API** (for Docker/service deployment), both backed by the same PostgreSQL + Qdrant + Ollama stack.

## Installation

### pip (editable, recommended for development)
```bash
pip install -e .
```

### uv
```bash
uv pip install -e .
```

### From source
```bash
git clone https://github.com/doctorboyz/synapse.git
cd synapse
pip install -e .
```

### Development dependencies
```bash
pip install -e ".[dev]"
```
Installs: `pytest>=8.0`, `pytest-asyncio>=0.24`, `pytest-cov>=5.0`, `testcontainers[postgres]>=4.0`

### Required External Services

| Service | Purpose | Default URL |
|---------|---------|-------------|
| **PostgreSQL** | Document store, FTS, metadata, trace links | `postgresql://admin:88888888@localhost:5432/mysynapse` |
| **Qdrant** | Dense vector storage (cosine similarity) | `http://localhost:6333` |
| **Ollama** | Embedding generation (nomic-embed-text, 768-dim) | `http://localhost:11434` |

> Qdrant and Ollama are optional. If Qdrant is unavailable, the system falls back to **FTS-only mode**. If Ollama is unavailable, vectors are skipped and documents are marked `indexed_pg_only`.

### Docker

```bash
docker compose -f docker/docker-compose.yml up -d
```

Uses `python:3.13-slim`, exposes port 8420, requires external `server-network` with PostgreSQL and Qdrant services.

### Python Requirement

Python >=3.12 (uses `type X | None` union syntax).

## Key Features with Examples

### CLI Commands

```bash
synapse serve    # Start HTTP API server (port 8420)
synapse mcp      # Start MCP stdio server
```

### MCP Tools (10 tools via stdio protocol)

#### 1. synapse_search — Hybrid Search
```json
{"query": "docker patterns", "scope": "my-project", "mode": "hybrid", "limit": 10}
```
- `mode`: `"hybrid"` (default), `"dense"`, or `"fts"`

#### 2. synapse_push — Add Knowledge
```json
{"title": "Docker Compose Patterns", "content": "Use compose v2...", "scope": "shared", "doc_type": "learning", "concepts": ["docker"]}
```
- Valid `doc_type`: `learning`, `pattern`, `retro`, `reference`, `handoff`, `protocol`, `wisdom`, `instinct`, `log`, `note`
- Returns `{"id": "...", "status": "indexed"}` or `{"status": "duplicate"}`

#### 3. synapse_supersede — Replace Document
```json
{"old_id": "uuid", "new_content": "Updated...", "reason": "updated"}
```

#### 4. synapse_trace — Create Trace Link
```json
{"source_id": "uuid-1", "target_id": "uuid-2", "relation": "derived_from", "confidence": 0.9}
```
- Valid `relation`: `derived_from`, `refines`, `contradicts`, `extends`

#### 5. synapse_trace_chain — Follow Trace Chain
```json
{"doc_id": "uuid", "direction": "both", "max_depth": 5, "relation": "refines"}
```

#### 6. synapse_concepts — List/Search Concepts
```json
{"search": "docker", "limit": 50}
```

#### 7. synapse_get — Retrieve Full Document
```json
{"id": "uuid", "include_chain": true}
```

#### 8. synapse_scope — List Scopes
```json
{}
```

#### 9. synapse_stats — Vault Statistics
```json
{}
```

#### 10. synapse_list — List Documents
```json
{"scope": "my-project", "doc_type": "learning", "limit": 20, "offset": 0, "order": "newest"}
```

### HTTP API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/search` | Hybrid search |
| `POST` | `/api/push` | Add knowledge document |
| `POST` | `/api/webhook` | Webhook ingest |
| `POST` | `/api/supersede` | Supersede a document |
| `POST` | `/api/trace` | Create trace link |
| `GET` | `/api/trace/{doc_id}` | Get trace chain |
| `GET` | `/api/concepts` | List/search concepts |
| `GET` | `/api/documents/{doc_id}` | Retrieve document |
| `GET` | `/api/documents` | List documents |
| `GET` | `/api/scopes` | List scopes |
| `GET` | `/api/stats` | Vault statistics |
| `GET` | `/api/health` | Health check |

Example:
```bash
curl -X POST http://localhost:8420/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "docker patterns", "mode": "hybrid", "limit": 5}'
```

### Oracle Path Mapping

| Path Pattern | doc_type | brain_tier |
|---|---|---|
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

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://admin:88888888@localhost:5432/mysynapse` | PostgreSQL connection string |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `QDRANT_COLLECTION` | `mysynapse_vectors` | Qdrant collection name |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API base URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model name |
| `EMBEDDING_DIM` | `768` | Embedding vector dimensionality |
| `EMBEDDING_TIMEOUT` | `30` | Ollama embedding request timeout (seconds) |
| `MYSYNAPSE_HOST` | `0.0.0.0` | HTTP API bind host |
| `MYSYNAPSE_PORT` | `8420` | HTTP API bind port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SEARCH_WEIGHTS` | `0.6,0.4` | RRF fusion weights (dense,fts) |
| `CACHE_TTL` | `300` | Cache time-to-live in seconds |
| `CACHE_MAX_SIZE` | `1000` | Maximum cache entries |

### Search Behavior

- **hybrid mode** (default): Embeds query via Ollama, runs both Qdrant dense search and PostgreSQL FTS, fuses with RRF. Falls back to FTS-only if Qdrant/Ollama unavailable.
- **dense mode**: Embeds query, searches Qdrant only. Requires Qdrant and Ollama.
- **fts mode**: PostgreSQL tsvector search only. No embedding needed.
- RRF formula: `score = weight / (k + rank)` where k defaults to 60.

### Fallback Behavior

- Qdrant unavailable → FTS-only mode (logged as warning)
- Ollama unavailable → documents stored in PostgreSQL only with status `indexed_pg_only`
- Hook ingestion gracefully degrades: content stored in PG even if Qdrant/Ollama fail

## Source File Map

| File | Purpose |
|------|---------|
| `src/config.py` | Settings dataclass from env vars |
| `src/main.py` | FastAPI app + CLI entry point |
| `src/mcp/server.py` | 10 MCP tools via stdio protocol |
| `src/api/routes.py` | HTTP REST API (mirrors MCP tools) |
| `src/db/pg_store.py` | PostgreSQL CRUD, FTS, supersession, concepts, trace |
| `src/db/qdrant_store.py` | Qdrant vector upsert/search/delete |
| `src/db/schema.sql` | PostgreSQL DDL (idempotent) |
| `src/embed/ollama.py` | Async Ollama embedder with retry/batch |
| `src/ingest/push.py` | Dual-store push pipeline with dedup |
| `src/ingest/oracle_paths.py` | kappapsi path-to-metadata mapping |
| `src/ingest/hook_handler.py` | PostToolUse auto-ingest for oracle files |
| `src/retrieve/hybrid_search.py` | RRF fusion search engine |