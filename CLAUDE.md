# Synapse v3

Hybrid Knowledge Framework — PostgreSQL + Qdrant + MCP

## Stack

- Python 3.12+, asyncpg, FastAPI, MCP SDK
- PostgreSQL (tsvector FTS), Qdrant (vector search), Ollama (embeddings)
- Hybrid search: RRF fusion 60% dense / 40% FTS

## Commands

```bash
synapse serve    # Start HTTP API server (port 8420)
synapse mcp      # Start MCP stdio server
pytest tests/ -v # Run all tests
```

## MCP Tools

synapse_search, synapse_push, synapse_supersede, synapse_trace, synapse_trace_chain, synapse_concepts, synapse_get, synapse_scope, synapse_stats, synapse_list

## Architecture

- `src/db/pg_store.py` — PostgreSQL CRUD, FTS, supersession, concepts, trace
- `src/db/qdrant_store.py` — Qdrant vector operations
- `src/embed/ollama.py` — Async embedding with retry
- `src/ingest/push.py` — Push pipeline (dual-store write, dedup)
- `src/ingest/oracle_paths.py` — κ/ψ path → doc_type, oracle_name, brain_tier
- `src/ingest/hook_handler.py` — PostToolUse auto-ingest for oracle brain files
- `src/retrieve/hybrid_search.py` — RRF fusion with FTS fallback
- `src/mcp/server.py` — 10 MCP tools via stdio
- `src/api/routes.py` — HTTP API mirroring MCP tools
- `src/main.py` — FastAPI app + CLI entry point

## Design Principles

1. Nothing is deleted — supersession only
2. Oracle-aware doc_types (kappa/psi brain structure)
3. source_project tracks origin (separate from scope/namespace)
4. FTS fallback when Qdrant unavailable
5. Dedup by (content_hash, scope)

## Branch History

- `main` — v1: Claude Code skill (SQLite + ChromaDB)
- `v2` — v2: Service mode daemon, shared vault, async
- `v3` — v3: PostgreSQL + Qdrant hybrid search (merged from mysynapse)