# Synapse — Hybrid Knowledge Framework

```
    ╭─────────────────────── ╭─────────────────────── ╭───────────────────────
    │                       │                       │
    │  ─ ─ ─ ─ ─ ─ ─ ─    │                       │    ─ ─ ─ ─ ─ ─ ─ ─
    │   AXON TERMINAL       │   SYNAPTIC CLEFT      │   DENDRITE / RECEPTOR
    │                       │                       │
    │    ╭──────────╮       │    ◇ neurotransmitter  │       ╭──────────╮
    │    │ ▒▒▒▒▒▒▒▒ │       │    ◇  (knowledge)     │       │ ◈◈◈◈◈◈◈ │
    │    │ ▒ vesicle▒│──────┼──◇────◇────◇─────────┼──────▶│ ◈ receptor◈│
    │    │ ▒▒▒▒▒▒▒▒ │       │    ◇  flows across    │       │ ◈◈◈◈◈◈◈ │
    │    ╰──────────╯       │    ◇  the gap         │       ╰──────────╯
    │                       │                       │
    │    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓    │                       │    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    │    ▓ source files ▓   │    .synapse/          │    ▓ knowledge  ▓
    │    ▓ ψ/ docs  code ▓  │    vault.db + vectors  │    ▓ retrieved  ▓
    │    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓    │                       │    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    │                       │                       │
    ╰───────────────────────╰───────────────────────╰───────────────────────
          PRESYNAPTIC              THE SYNAPSE            POSTSYNAPTIC
         (Stage 1 input)         (this framework)       (Stage 2 output)
```

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
              │  + 40% FTS5)    │             │         │
              └────────┬────────┘             │         │
                       │                      │         │
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
    │   CLAUDE.md + ψ/)  │
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
pip install -e ~/.claude/skills/synapse

# Initialize vault in a project
synapse init --scope emily-oracle

# Push knowledge
synapse push ψ/memory/learnings/docker-patterns.md
synapse push --title "Docker patterns" --text "Use compose v2..." --scope shared

# Search
synapse search "docker infrastructure patterns"
synapse search --scope ai-server "redis cache"
synapse search --mode fts "exact keyword"

# Check status
synapse status
synapse scope
```

## Retrieval Priority

Synapse is **Stage 2** — consulted after primary context is exhausted:

```
Stage 1 (อ่านก่อน — อยู่ใน context แล้ว)
├── CLAUDE.md                          ← rules, identity
├── .claude/docs/                      ← project docs
└── ψ/ (psi vault) ถ้ามี               ← learnings, retros, handoffs

Stage 2 (ค้นหาเมื่อ Stage 1 ไม่พอ)
└── .synapse/ (database vault)          ← hybrid search เจาะจง
```

Projects without ψ/ vault still have Stage 1 (CLAUDE.md + .claude/docs), then synapse supplements when specific knowledge is needed.

## Architecture

```
.synapse/                   ← Database vault (separate from ψ/)
├── vault.db                ← SQLite (FTS5 + metadata + scope + supersession)
├── vectors/                ← LanceDB (dense vectors, local files)
└── config.yaml             ← Scope, models, retrieval settings

ψ/                          ← Source of truth (human-readable)
├── memory/learnings/       → auto-indexed via PostToolUse hook
└── memory/retrospectives/  → auto-indexed via PostToolUse hook
```

| | ψ/ (psi) | .synapse/ (vault) |
|---|---|---|
| What | Oracle brain — markdown files | Database vault — SQLite + LanceDB |
| Who reads | Humans, Claude (Read) | synapse search, MCP tools |
| Format | .md (human-readable) | binary DB + vector index |
| Commit | No (vault state) | No (.gitignore) |

ψ/ = source of truth, .synapse/ = search index

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

Hybrid achieves perfect R@10 — combining dense + keyword covers both semantic and exact matches.

### Query Latency

| Mode | Avg latency | Notes |
|------|-------------|-------|
| FTS5 | 0.3ms | Pure SQLite, no embedding call |
| Dense | 60.6ms | Includes Ollama embed (first query ~232ms cold) |
| Hybrid | 50.1ms | Dense + FTS5 combined, RRF merge |

First dense query is slower (Ollama model load). Subsequent queries are ~45-55ms.

### Indexing Speed

| Doc size | SQLite only | SQLite + LanceDB (with embed) |
|----------|-------------|-------------------------------|
| Short (39 chars) | 0.1ms | 160ms |
| Medium (1K chars) | 0.0ms | 59ms |
| Long (1.4K chars) | 0.0ms | 106ms |

SQLite indexing is near-instant. Embedding cost dominates — amortized with Ollama model warm.

### Scope Filtering

| Filter | Top-3 results |
|--------|--------------|
| scope=emily-oracle | project-specific results |
| scope=all (default) | all results, best match first |

### Vault Stats

| Metric | Value |
|--------|-------|
| Documents | 13 |
| Vectors | 23 (768-dim) |
| Scopes | emily-oracle: 13 docs |
| Doc types | learning: 13 |
| Superseded | 0 |
| Embedding model | nomic-embed-text (Ollama, local) |
| Chunk max | 4000 chars, 200 overlap |

## Commands

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

## MCP Tools

Available in Claude Code without `/synapse` prefix:

| Tool | Description |
|------|-------------|
| `synapse_init` | Create vault in project |
| `synapse_push` | Add knowledge |
| `synapse_search` | Hybrid search |
| `synapse_scope` | List scopes |
| `synapse_status` | Vault statistics |

## Auto-Indexing (Hook)

PostToolUse hook automatically indexes files written to:
- `*/memory/learnings/*.md`
- `*/memory/retrospectives/*.md`

Scope is auto-detected from file path.

## Scope System

Every document has a scope:
- **shared** — knowledge all projects use (docker patterns, security, etc.)
- **\<project-name\>** — project-specific (emily-oracle, ai-server, etc.)

Scope is resolved: explicit `--scope` > auto-detect from path > default `shared`.

## Supersession (Nothing is Deleted)

Following arra-oracle's principle: documents are never deleted, only superseded. When a document is updated, the old version gets `superseded_by` pointing to the new version. Search results exclude superseded documents.

## Dependencies

```
lancedb>=0.6.0    # Vector storage
httpx>=0.27.0     # Ollama API client
pyyaml>=6.0       # Config file
mcp>=1.0.0        # MCP SDK (optional, for Claude Code integration)
```

Requires Ollama running locally with `nomic-embed-text` model for vector search.

## Roadmap

- **v1** — Local skill (SQLite + LanceDB, CLI, MCP, hooks) ✅
- **v1.1** — Tests, rebuild command, better error handling
- **v2** — Service mode (MCP server as daemon, cross-project shared vault)
- **v3** — Platform (Qdrant/Postgres options, API, multi-user)

## Credit

Synthesis of patterns from:
- **MemPalace** — verbatim storage + scope (wing/room)
- **arra-oracle** — supersession + FTS5
- **SocratiCode** — RRF fusion + AST chunking
- **Graphify** — knowledge graph + confidence scoring
- **OpenKB** — wiki-style compilation + hash dedup