# /synapse — Hybrid Knowledge Framework

> Synapse: the junction where knowledge connects.
> Inspired by: MemPalace, arra-oracle, SocratiCode, Graphify, OpenKB

## Retrieval Priority

Synapse is **Stage 2** retrieval — consulted after primary context is exhausted:

```
Stage 1 (อ่านก่อน — อยู่ใน context แล้ว)
├── CLAUDE.md                          ← rules, identity
├── .claude/docs/                      ← project docs
└── ψ/ (psi vault) ถ้ามี               ← learnings, retros, handoffs

Stage 2 (ค้นหาเมื่อ Stage 1 ไม่พอ)
└── .synapse/ (database vault)          ← hybrid search เจาะจง
```

Projects without ψ/ vault still have Stage 1 (CLAUDE.md + .claude/docs),
then synapse supplements when specific knowledge is needed.

## Commands

```
/synapse init                    # สร้าง .synapse/ vault ใน project ใหม่
/synapse init --scope ai-server  # สร้างพร้อมกำหนด scope เริ่มต้น

/synapse push <file_or_text>     # เพิ่มความรู้เข้า vault (ไฟล์ path ไหนก็ได้ หรือ text paste)
/synapse push --scope shared     # เพิ่มเข้า shared scope
/synapse push --type pattern     # เพิ่ม doc_type อื่น (learning/pattern/architecture/retro)

/synapse search <query>          # ค้นหา hybrid (dense + FTS5 + RRF)
/synapse search --scope X        # ค้นหาใน scope เฉพาะ
/synapse search --mode dense     # dense vectors เท่านั้น
/synapse search --mode fts       # keyword เท่านั้น

/synapse status                   # ดู vault stats (docs, scopes, vectors)
/synapse scope                    # ลิสต์ scopes ทั้งหมด
/synapse rebuild                  # สร้าง indexes ใหม่
```

## Architecture

```
.synapse/                   ← Database vault (แยกจาก ψ/)
├── vault.db                ← SQLite (FTS5 + metadata + scope)
├── vectors/                ← LanceDB (dense vectors, local files)
└── config.yaml             ← Scope, models, retrieval settings

ψ/                          ← Source of truth (มนุษย์อ่าน)
├── memory/learnings/       ← เข้า synapse อัตโนมัติ (PostToolUse hook)
└── memory/retrospectives/  ← เข้า synapse อัตโนมัติ (PostToolUse hook)

Store:
├── LanceDB (dense vectors)     ← semantic search (nomic-embed-text 768-dim)
├── SQLite FTS5 (keyword)       ← exact term search
└── RRF fusion (60/40)          ← combine both results

Ingest:
├── /synapse push              ← manual (ไฟล์จากที่ไหนก็ได้ หรือ text paste)
├── PostToolUse hook            ← auto (ψ/memory/learnings/ + retrospectives/)
└── /rrr integration            ← semi-auto

Retrieve:
├── Hybrid search (dense + FTS5 → RRF)
├── Scope filtering (shared / project)
└── Priority: Stage 2 (after CLAUDE.md, .claude/docs, ψ/)
```

## ψ/ vs .synapse/

| | ψ/ (psi) | .synapse/ (vault) |
|---|---|---|
| **คือ** | Oracle brain — ไฟล์ markdown | Database vault — SQLite + LanceDB |
| **เก็บ** | learnings, retros, inbox, drafts | vault.db + vectors/ |
| **ใครอ่าน** | มนุษย์, Claude (Read) | synapse search, MCP tools |
| **format** | .md (มนุษย์อ่านได้) | binary DB + vector index |
| **commit** | ไม่ commit | ไม่ commit (.gitignore) |

ψ/ = source of truth, .synapse/ = search index

## Scope

Every document has a scope:
- `shared` — knowledge all projects use (docker patterns, security, etc.)
- `<project-name>` — project-specific (emily-oracle, ai-server, etc.)

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
- `*/memory/learnings/*.md`
- `*/memory/retrospectives/*.md`