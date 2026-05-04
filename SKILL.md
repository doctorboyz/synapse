# /synapse — Hybrid Knowledge Framework

> Synapse: the junction where knowledge connects.
> Inspired by: MemPalace, arra-oracle, SocratiCode, Graphify, OpenKB

## Retrieval Priority

Synapse is **Stage 2** retrieval — consulted after primary context is exhausted:

```
Stage 1 (read first — already in context)
├── CLAUDE.md                          ← rules, identity
├── .claude/docs/                      ← project docs
└── project knowledge files            ← learnings, retros, handoffs

Stage 2 (search when Stage 1 is not enough)
└── .synapse/ (database vault)         ← targeted hybrid search
```

Projects without a knowledge vault still have Stage 1 (CLAUDE.md + .claude/docs),
then synapse supplements when specific knowledge is needed.

## Commands

```
/synapse init                    # สร้าง .synapse/ vault ใน project ใหม่
/synapse init --scope my-project # สร้างพร้อมกำหนด scope เริ่มต้น

/synapse push <file_or_text>     # เพิ่มความรู้เข้า vault (ไฟล์ path ไหนก็ได้ หรือ text paste)
/synapse push --scope shared     # เพิ่มเข้า shared scope
/synapse push --type pattern     # เพิ่ม doc_type อื่น (learning/pattern/architecture/retro)

/synapse search <query>          # ค้นหา hybrid (dense + FTS5 + RRF)
/synapse search --scope X        # ค้นหาใน scope เฉพาะ
/synapse search --mode dense     # dense vectors เท่านั้น
/synapse search --mode fts       # keyword เท่านั้น

/synapse status                   # ดู vault stats (docs, scopes, vectors)
/synapse scope                    # ลิสต์ scopes ทั้งหมด
```

## Architecture

```
.synapse/                   ← Database vault
├── vault.db                ← SQLite (FTS5 + metadata + scope)
├── vectors/                ← LanceDB (dense vectors, local files)
└── config.yaml             ← Scope, models, retrieval settings

Source files/               ← Human-readable knowledge
├── learnings/              ← auto-indexed via PostToolUse hook
└── retrospectives/         ← auto-indexed via PostToolUse hook

Store:
├── LanceDB (dense vectors)     ← semantic search (nomic-embed-text 768-dim)
├── SQLite FTS5 (keyword)       ← exact term search
└── RRF fusion (60/40)          ← combine both results

Ingest:
├── /synapse push              ← manual (ไฟล์จากที่ไหนก็ได้ หรือ text paste)
├── PostToolUse hook            ← auto (learnings/ + retrospectives/)
└── /rrr integration            ← semi-auto

Retrieve:
├── Hybrid search (dense + FTS5 → RRF)
├── Scope filtering (shared / project)
└── Priority: Stage 2 (after CLAUDE.md, .claude/docs, project knowledge)
```

## Source Files vs .synapse/

| | Source files | .synapse/ (vault) |
|---|---|---|
| **คือ** | Knowledge base — markdown files | Database vault — SQLite + LanceDB |
| **เก็บ** | learnings, retros, drafts | vault.db + vectors/ |
| **ใครอ่าน** | มนุษย์, Claude (Read) | synapse search, MCP tools |
| **format** | .md (มนุษย์อ่านได้) | binary DB + vector index |
| **commit** | yes | ไม่ commit (.gitignore) |

Source files = human-readable truth, .synapse/ = search index

## Scope

Every document has a scope:
- `shared` — knowledge all projects use (docker patterns, security, etc.)
- `<project-name>` — project-specific (my-project, another-project, etc.)

Scope is auto-detected from file path or explicitly set via --scope.

## Embedding

Default: Ollama `nomic-embed-text` (768-dim, local, free)
Chunking: 4000 chars max, 200 char overlap at paragraph/sentence boundaries

## MCP Tools

Available in Claude Code (no `/synapse` prefix needed):
- `synapse_init` — create vault in project
- `synapse_push` — add knowledge
- `synapse_search` — hybrid search
- `synapse_scope` — list scopes
- `synapse_status` — vault status

## Auto (Hook)

PostToolUse Write/Edit triggers auto-index when writing to:
- `*/learnings/*.md`
- `*/retrospectives/*.md`