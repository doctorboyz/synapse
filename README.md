# Synapse — Hybrid Knowledge Framework

> **"The junction where knowledge connects."**

```
                          KNOWLEDGE IN
                              │
                              │
                 ┌────────────┴────────────┐
                 │      PUSH / HOOK        │
                 │   (ingest layer)        │
                 └────────────┬────────────┘
                              │
                     ┌────────┴────────┐
                     │   CHUNK + EMBED │
                     │  (4000 chars,   │
                     │   nomic-768d)   │
                     └────────┬────────┘
                              │
                 ┌────────────┼────────────┐
                 │            │            │
         ┌───────┴──────┐     │    ┌───────┴──────┐
         │              │     │    │              │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │ LANCE-  │   │         │   │ SQLITE  │   │         │
    │ DB      │   │         │   │ FTS5    │   │         │
    │ ▓▓▓▓▓▓▓ │   │         │   │ ▓▓▓▓▓▓▓ │   │         │
    │ dense   │   │         │   │ keyword │   │         │
    │ vectors │   │         │   │ search  │   │         │
    └────┬────┘   │         │   └────┬────┘   │         │
         │        │         │        │        │         │
         └────────┴────┬────┴────────┘        │         │
                       │                      │         │
              ┌────────┴────────┐             │         │
              │   RRF FUSION    │             │         │
              │  (60% dense     │             │         │
              │  + 40% FTS5)   │             │         │
              └────────┬────────┘             │         │
                       │        ┌─────────────┴────────┐
                       │        │    SCOPE FILTER       │
                       │        │  shared / project      │
                       │        └─────────────┬────────┘
                       │                      │
              ┌────────┴──────────────────────┘
              │
              │
    ┌─────────┴──────────┐
    │     SEARCH OUT     │
    │  (Stage 2 — after  │
    │   project docs)     │
    └────────────────────┘

    ◂──────────────────────────────────────────▸
              NEURON ─ SYNAPSE ─ NEURON
         (source files)  (this)   (knowledge)
```

> "The junction where knowledge connects."

Local-first hybrid search: dense vectors (LanceDB) + keyword search (SQLite FTS5) fused with Reciprocal Rank Fusion. No external services required — runs entirely on your machine.

Inspired by [MemPalace](https://github.com/MemPalace/mempalace), [arra-oracle](https://github.com/nicepkg/arra), [SocratiCode](https://github.com/AcademicWorks/SocratiCode), [Graphify](https://github.com/whyhow-ai/graphify), [OpenKB](https://github.com/openknowledgefoundation/openkb).

## Quick Start

```bash
# Install
pip install -e .

# Initialize vault in a project
synapse init --scope my-project

# Push knowledge
synapse push path/to/document.md
synapse push --title "Docker patterns" --text "Use compose v2..." --scope shared

# Search
synapse search "docker infrastructure patterns"
synapse search --scope my-project "redis cache"
synapse search --mode fts "exact keyword"

# Check status
synapse status
synapse scope
```

## Retrieval Priority

Synapse is **Stage 2** — consulted after primary context is exhausted:

```
Stage 1 (read first — already in context)
├── CLAUDE.md                          ← rules, identity
├── .claude/docs/                      ← project docs
└── project knowledge files            ← learnings, retros, handoffs

Stage 2 (search when Stage 1 is not enough)
└── .synapse/ (database vault)         ← targeted hybrid search
```

Projects without a knowledge vault still have Stage 1 (CLAUDE.md + .claude/docs), then synapse supplements when specific knowledge is needed.

## Architecture

```
.synapse/                   ← Database vault
├── vault.db                ← SQLite (FTS5 + metadata + scope + supersession)
├── vectors/                ← LanceDB (dense vectors, local files)
└── config.yaml             ← Scope, models, retrieval settings

project knowledge/          ← Source files (human-readable)
├── learnings/              → auto-indexed via PostToolUse hook
└── retrospectives/         → auto-indexed via PostToolUse hook
```

| | Source files | .synapse/ (vault) |
|---|---|---|
| What | Knowledge base — markdown files | Database vault — SQLite + LanceDB |
| Who reads | Humans, Claude (Read) | synapse search, MCP tools |
| Format | .md (human-readable) | binary DB + vector index |
| Commit | Yes | No (.gitignore) |

Source files = human-readable truth, .synapse/ = search index

## Search Modes

| Mode | How | Best for | Avg latency |
|------|-----|----------|-------------|
| **hybrid** (default) | Dense (60%) + FTS5 (40%) → RRF | General — best recall | ~50ms |
| **dense** | LanceDB vector similarity | Semantic/conceptual matches | ~61ms |
| **fts** | SQLite FTS5 keyword | Exact term matching | ~0.3ms |

## Benchmarks (v1)

Test environment: MacBook, Ollama nomic-embed-text (768-dim), 13 documents, 23 vectors.

### Recall Accuracy

| Mode | R@5 | R@10 |
|------|-----|------|
| FTS5 (keyword only) | 0.80 (8/10) | 0.90 (9/10) |
| Dense (vector only) | 0.60 (6/10) | 0.80 (8/10) |
| **Hybrid (RRF 60/40)** | **0.80 (8/10)** | **1.00 (10/10)** |

### Query Latency

| Mode | Avg latency | Notes |
|------|-------------|-------|
| FTS5 | 0.3ms | Pure SQLite, no embedding call |
| Dense | 60.6ms | Includes Ollama embed (first query ~232ms cold) |
| Hybrid | 50.1ms | Dense + FTS5 combined, RRF merge |

## v2 — Service Mode (Daemon, Shared Vault)

v2 adds an optional persistent daemon that serves multiple projects from a shared vault at `~/.synapse/`.

### v2 Architecture

```
v1 (per-project, default when no daemon):
  project-a/.synapse/     ← isolated vault per project
  project-b/.synapse/

v2 (daemon, shared vault):
  ~/.synapse/             ← shared vault root
    ├── vault.db          ← SQLite WAL mode (concurrent access)
    ├── vectors/          ← LanceDB (shared)
    ├── config.yaml       ← AUTHORITATIVE runtime config (v2 schema)
    ├── projects.yaml     ← project registry
    └── daemon.lock       ← PID lock
```

### v2 CLI Commands

```bash
# Initialize shared vault
synapse init --shared

# Daemon management
synapse serve              # Start daemon (foreground)
synapse daemon             # Start daemon (background)
synapse stop                # Stop daemon

# Project registration
synapse register --scope my-project
synapse unregister my-project
synapse projects            # List registered projects

# Health check
synapse health              # Daemon status, vault stats, embedding check

# Cross-project search (also available via MCP)
synapse search "pattern" --projects project-a,project-b
```

### v2 Config Schema

```yaml
version: 2
daemon:
  host: "127.0.0.1"
  port: 8321
  socket: "~/.synapse/daemon.sock"
  pid_file: "~/.synapse/daemon.lock"
  log_level: "INFO"
  graceful_shutdown_timeout: 30

embedding:
  provider: "ollama"
  model: "nomic-embed-text"
  dim: 768
  timeout: 30
  base_url: "http://localhost:11434"
  batch_size: 1

search:
  mode: "hybrid"
  weights: {dense: 0.6, fts: 0.4}
  cache_ttl: 300
  cache_max_size: 1000

scope:
  default: "shared"
  cross_project: true

vault:
  path: "~/.synapse"
  wal_mode: true
  busy_timeout: 5000

hooks:
  auto_index: true
  trigger_paths: ["*/learnings/*.md", "*/retrospectives/*.md"]
  use_daemon: true
```

### v2 MCP Tools

Available in Claude Code without `/synapse` prefix:

| Tool | Description |
|------|-------------|
| `synapse_search` | Hybrid search (add `projects` param for cross-project) |
| `synapse_push` | Add knowledge |
| `synapse_scope` | List scopes |
| `synapse_status` | Vault statistics (daemon-aware) |
| `synapse_init` | Create vault (add `shared` param for shared vault) |
| `synapse_rebuild` | Rebuild vault indexes |
| `synapse_projects` | List registered projects and scopes |
| `synapse_register` | Register current project with shared vault |
| `synapse_unregister` | Remove project registration |
| `synapse_health` | Daemon health: uptime, vault stats, embedding |
| `synapse_search_cross` | Cross-project search across multiple scopes |

### Backward Compatibility

- v1 per-project vaults work unchanged when no daemon is running
- SQLite WAL is backward-compatible (single-connection v1 code works on WAL databases)
- v1 config.yaml (`version: 1`) still valid — daemon merges it with v2 defaults
- All existing CLI commands unchanged — new ones are additions

## v1 Commands

| Command | Description |
|---------|-------------|
| `synapse init [--scope X]` | Create .synapse/ vault in project |
| `synapse push <file>` | Add file to vault |
| `synapse push --title T --text C` | Add text to vault |
| `synapse push --scope X` | Set scope explicitly |
| `synapse push --type learning/pattern/architecture/retro` | Set doc type |
| `synapse search <query>` | Hybrid search (default) |
| `synapse search --mode dense` | Vector search only |
| `synapse search --mode fts` | Keyword search only |
| `synapse search --scope X` | Filter by scope |
| `synapse search --limit N` | Max results (default 10) |
| `synapse status` | Vault statistics |
| `synapse scope` | List all scopes |
| `synapse rebuild [--scope X] [--no-backup]` | Rebuild vault indexes from source files |

## Auto-Indexing (Hook)

PostToolUse hook automatically indexes files written to knowledge directories. For example:
- `*/learnings/*.md`
- `*/retrospectives/*.md`

Scope is auto-detected from file path.

## Rebuilding Indexes

```bash
synapse rebuild               # Rebuild from all source files
synapse rebuild --scope X      # Rebuild only a specific scope
synapse rebuild --no-backup    # Skip vault.db backup (faster)
```

## Scope System

Every document has a scope:
- **shared** — knowledge all projects use (docker patterns, security, etc.)
- **\<project-name\>** — project-specific (my-project, another-project, etc.)

Scope is resolved: explicit `--scope` > auto-detect from path > default `shared`.

## Supersession (Nothing is Deleted)

Documents are never deleted, only superseded. When updated, the old version gets `superseded_by` pointing to the new version. Search results exclude superseded documents.

## Dependencies

```
lancedb>=0.6.0    # Vector storage
httpx>=0.27.0     # Ollama API client
pyyaml>=6.0       # Config file
mcp>=1.0.0        # MCP SDK (optional, for Claude Code integration)
```

Requires Ollama running locally with `nomic-embed-text` model for vector search.

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
pytest tests/ --cov=synapse --cov-report=term-missing
```

Tests mock Ollama at the `httpx.post` level, so no running Ollama server is needed.

## Roadmap

- **v1** — Local skill (SQLite + LanceDB, CLI, MCP, hooks) ✅
- **v1.1** — Tests, rebuild command, custom exceptions, better error handling ✅
- **v2** — Service mode (MCP daemon, cross-project shared vault, async embedding, cache) ✅
- **v3** — Platform (Qdrant/Postgres options, API, multi-user)

## Credit

Synthesis of patterns from:
- **MemPalace** — verbatim storage + scope (wing/room)
- **arra-oracle** — supersession + FTS5
- **SocratiCode** — RRF fusion + AST chunking
- **Graphify** — knowledge graph + confidence scoring
- **OpenKB** — wiki-style compilation + hash dedup