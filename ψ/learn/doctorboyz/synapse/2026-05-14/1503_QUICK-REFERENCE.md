# Synapse v3 Quick Reference

> Hybrid Knowledge Framework — PostgreSQL + Qdrant + MCP. Local-first, zero network egress.

---

## What It Does

Synapse is a local-first knowledge vault that ingests documents, embeds them as vectors, and provides hybrid search (dense vectors + full-text search fused via RRF). It never deletes anything — only supersedes. It runs entirely on your machine with no external data egress.

**Core philosophy**: Stage 2 retrieval. Synapse supplements primary context (CLAUDE.md, project docs) when those are insufficient.

---

## Installation

### From Source (Recommended)

```bash
git clone <repo>
cd synapse
pip install -e ".[dev]"
```

### Docker

```bash
docker build -t synapse:latest .
docker run -p 8420:8420 synapse:latest
```

### Dependencies

Requires:
- Python 3.12+
- PostgreSQL (with `pgcrypto` extension)
- Qdrant (optional — falls back to FTS-only if unavailable)
- Ollama running locally (default model: `nomic-embed-text`, 768-dim)

---

## Key Features

| Feature | What It Does |
|---------|-------------|
| **Hybrid Search** | Dense vectors (60%) + PostgreSQL tsvector FTS (40%) fused with RRF |
| **Supersession** | Nothing is deleted — old docs are marked `superseded_by` → new doc |
| **Trace Chain** | Link documents with relations: `derived_from`, `refines`, `contradicts`, `extends` |
| **Cross-Project Search** | Search across multiple registered scopes simultaneously |
| **Auto-Ingest Hooks** | PostToolUse hook auto-indexes `*/learnings/*.md` and `*/retrospectives/*.md` |
| **Local-Only Enforcement** | All connections must be localhost/Unix socket — no external network |
| **Search Cache** | LRU + TTL cache for repeated queries |
| **Scheduled Scan** | Background daemon scans registered projects for new files |
| **Config Hot-Reload** | SIGHUP reloads YAML config without restart |
| **Oracle-Aware** | Auto-detects `doc_type`, `oracle_name`, `brain_tier`, `brain_path` from `κ/ψ` file paths |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://admin:88888888@localhost:5432/synapse` | PostgreSQL connection |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `EMBEDDING_DIM` | `768` | Vector dimension |
| `SYNAPSE_HOST` | `0.0.0.0` | HTTP server bind address |
| `SYNAPSE_PORT` | `8420` | HTTP server port |
| `SEARCH_WEIGHTS` | `0.6,0.4` | RRF weights (dense, FTS) |
| `CACHE_TTL` | `300` | Cache TTL in seconds |
| `CACHE_MAX_SIZE` | `1000` | Max cache entries |
| `SYNAPSE_SCAN_INTERVAL` | `0` | Background scan interval in seconds (0 = off) |
| `SYNAPSE_RECONCILE_HOUR` | `2` | Hour to run daily reconcile (0-23) |

### YAML Config

Place at `~/.synapse/config.yaml`:

```yaml
database_url: "postgresql://admin:pass@localhost:5432/synapse"
qdrant_url: "http://localhost:6333"
ollama_url: "http://localhost:11434"
embedding_model: "nomic-embed-text"
api_host: "0.0.0.0"
api_port: 8420
log_level: "INFO"
search_weights: [0.6, 0.4]
cache_ttl: 300
cache_max_size: 1000
scan_interval: 600
```

**Priority**: Environment variables > YAML config > defaults. Reload with `kill -HUP $(cat ~/.synapse/synapse.pid)`.

---

## CLI Commands Reference

### Server

| Command | Description |
|---------|-------------|
| `synapse serve` | Start HTTP API server (port 8420) |
| `synapse mcp` | Start MCP stdio server |
| `synapse stop` | Stop running daemon |
| `synapse status` | Show daemon and system status |

### Knowledge Operations

| Command | Description |
|---------|-------------|
| `synapse push --title "..." --content "..." --scope my-project` | Add text to vault |
| `synapse push --file path/to/doc.md --scope my-project` | Ingest file |
| `synapse search "query" --scope my-project --mode hybrid` | Search vault |
| `synapse search-cross "query" --scopes proj-a,proj-b` | Cross-project search |
| `synapse get <doc-id>` | Retrieve full document by ID |
| `synapse list --scope my-project --limit 20` | List documents |
| `synapse scope` | List all scopes |
| `synapse stats` | Vault statistics |
| `synapse supersede <old-id> --new-content "..."` | Supersede a document |
| `synapse trace --source <id> --target <id> --relation derived_from` | Link documents |
| `synapse trace-chain <id> --direction both` | Follow trace chain |
| `synapse concepts --search "async"` | List/search concepts |

### Project Management

| Command | Description |
|---------|-------------|
| `synapse register --path /my/project --scope my-project` | Register project |
| `synapse unregister my-project` | Remove registration |
| `synapse projects` | List registered projects |

### Maintenance

| Command | Description |
|---------|-------------|
| `synapse init --path . --scope my-project [--dry-run]` | Scan files + build vault |
| `synapse reconcile [--scope my-project] [--dry-run]` | Defrag duplicates + detect conflicts |
| `synapse scan` | Scan all registered projects for new files |
| `synapse install-hooks [--dry-run]` | Register PostToolUse hooks in `~/.claude/settings.json` |

### Search Modes

- `hybrid` (default) — RRF fusion of dense + FTS
- `dense` — Vector similarity only (Qdrant)
- `fts` — PostgreSQL tsvector keyword search only

---

## API Endpoints Reference

Base URL: `http://localhost:8420/api`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/search` | Hybrid search |
| `POST` | `/push` | Add knowledge |
| `POST` | `/webhook` | Push via webhook (sets `source_type: webhook`) |
| `POST` | `/supersede` | Supersede document |
| `POST` | `/trace` | Create trace link |
| `GET` | `/trace/{doc_id}` | Get trace chain |
| `GET` | `/concepts` | List concepts |
| `GET` | `/documents/{doc_id}` | Get document by ID |
| `GET` | `/documents` | List documents (with filters) |
| `GET` | `/scopes` | List scopes |
| `GET` | `/stats` | Vault stats |
| `GET` | `/health` | Health check |
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe (checks PG, Qdrant, embedding) |
| `POST` | `/register` | Register project |
| `POST` | `/unregister` | Unregister project |
| `GET` | `/projects` | List projects |
| `POST` | `/search-cross` | Cross-scope search |
| `POST` | `/resolve-links` | Resolve Obsidian `[[link]]` targets |
| `POST` | `/ingest/youtube` | Extract YouTube transcript and index |
| `POST` | `/ingest/website` | Scrape website and index |
| `POST` | `/ingest/file` | Upload file, parse, and index |
| `POST` | `/suggest-scope` | LLM-suggested scope for content |
| `POST` | `/chat` | Streamed chat with search context + Ollama LLM |
| `GET` | `/models` | List available Ollama models |

---

## MCP Tools Reference

All tools available via stdio JSON-RPC. Called directly in Claude Code without prefix.

| Tool | Required Args | Optional Args |
|------|--------------|---------------|
| `synapse_search` | `query` | `scope`, `doc_type`, `oracle`, `source_project`, `concepts`, `limit` (10), `mode` (hybrid) |
| `synapse_push` | `title`, `content` | `scope` (shared), `doc_type` (learning), `source_file`, `source_project`, `concepts`, `tags`, `oracle_name`, `brain_path`, `brain_tier` |
| `synapse_supersede` | `old_id`, `new_content` | `new_title`, `reason` (updated) |
| `synapse_trace` | `source_id`, `target_id`, `relation` | `confidence` (1.0) |
| `synapse_trace_chain` | `doc_id` | `direction` (both), `max_depth` (5), `relation` |
| `synapse_concepts` | — | `search`, `limit` (50) |
| `synapse_get` | `id` | `include_chain` (true) |
| `synapse_scope` | — | — |
| `synapse_stats` | — | — |
| `synapse_list` | — | `scope`, `doc_type`, `oracle`, `limit` (20), `offset` (0), `order` (newest) |
| `synapse_register` | `project_path` | `scope` |
| `synapse_unregister` | `scope` | — |
| `synapse_projects` | — | — |
| `synapse_search_cross` | `query`, `scopes` | `limit` (10), `mode` (hybrid) |

---

## Database Schema (PostgreSQL)

**Main tables:**
- `knowledge_documents` — Core docs with `search_vector` tsvector, `superseded_by` UUID, JSONB `concepts`/`tags`
- `supersede_log` — Audit trail of supersessions
- `scope_registry` — Scope metadata with doc counts
- `concepts` + `document_concepts` — Many-to-many concept tagging
- `trace` — Document relation graph (`derived_from`, `refines`, `contradicts`, `extends`)
- `registered_projects` — Cross-project search registry

**Indexes**: GIN on `search_vector`, partial indexes on `scope`/`doc_type`/`oracle`/`brain_tier` excluding superseded docs.

---

## 3-Way Access

```
Oracle Skill (auto)  → hook_handler → MCP push (auto-ingest κ/ψ files)
Direct MCP (manual)  → synapse_search, synapse_push, etc. in conversation
CLI (terminal)       → synapse push/search/init/reconcile/etc.
HTTP API             → curl localhost:8420/api/search, /api/push, etc.
```

---

## Quick Start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Ensure PostgreSQL and Ollama are running

# 3. Initialize a project
synapse init --path . --scope my-project

# 4. Push some knowledge
synapse push --title "Docker Patterns" --content "Use compose v2..." --scope shared

# 5. Search
synapse search "docker patterns" --scope shared

# 6. Start the API server (optional)
synapse serve
```

---

## Doc Types

`learning`, `pattern`, `architecture`, `retro`, `reference`, `handoff`, `protocol`, `wisdom`, `instinct`, `log`, `note`

Auto-detected from `κ/ψ` brain paths: `ψ/learn/...` → `doc_type=learning`, `brain_tier=psi`.

---

*Generated from synapse v3 source on 2026-05-14.*
