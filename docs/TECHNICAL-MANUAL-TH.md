# Synapse v3 — คู่มือเทคนิค

> Hybrid Knowledge Framework — PostgreSQL + Qdrant + MCP

---

## สารบัญ

1. [ภาพรวมสถาปัตยกรรม](#1-ภาพรวมสถาปัตยกรรม)
2. [การตั้งค่า (Config)](#2-การตั้งค่า-config)
3. [CLI — จุดเข้าใช้งาน](#3-cli--จุดเข้าใช้งาน)
4. [ชั้นฐานข้อมูล (Database Layer)](#4-ชั้นฐานข้อมูล-database-layer)
   - 4.1 [PostgreSQL Store](#41-postgresql-store)
   - 4.2 [Qdrant Store](#42-qdrant-store)
   - 4.3 [Schema](#43-schema)
5. [ชั้น Embedding](#5-ชั้น-embedding)
6. [ชั้นนำเข้า (Ingest Layer)](#6-ชั้นนำเข้า-ingest-layer)
   - 6.1 [Push Pipeline](#61-push-pipeline)
   - 6.2 [Oracle Paths](#62-oracle-paths)
   - 6.3 [Hook Handler](#63-hook-handler)
7. [ชั้นค้นคืน (Retrieve Layer)](#7-ชั้นค้นคืน-retrieve-layer)
8. [MCP Server — 10 เครื่องมือ](#8-mcp-server--10-เครื่องมือ)
9. [HTTP API](#9-http-api)
10. [ตารางเปรียบเทียบ MCP vs HTTP](#10-ตารางเปรียบเทียบ-mcp-vs-http)

---

## 1. ภาพรวมสถาปัตยกรรม

```
┌──────────────────────────────────────────────────────┐
│                    ผู้ใช้ / เอเจนต์                      │
│          (Claude Code MCP / HTTP Client)             │
└──────────────┬───────────────────┬──────────────────┘
               │                   │
        ┌──────▼──────┐    ┌──────▼──────┐
        │ MCP Server  │    │  HTTP API   │
        │  (stdio)    │    │  (port 8420)│
        └──────┬──────┘    └──────┬──────┘
               │                   │
        ┌──────▼───────────────────▼──────┐
        │          Push / HybridSearch    │
        │     (orchestration layer)       │
        └──┬──────────┬──────────┬───────┘
           │          │          │
    ┌──────▼───┐ ┌───▼───┐ ┌───▼────────┐
    │ PgStore  │ │Qdrant │ │OllamaEmbed  │
    │ (FTS)    │ │(dense)│ │(nomic-768)  │
    └──────────┘ └───────┘ └─────────────┘
```

**หลักการออกแบบหลัก:**

- **ไม่มีการลบ** — ใช้ระบบ supersede แทนการลบ ข้อมูลเก่ายังคงอยู่
- **Qdrant ไม่บังคับ** — หาก Qdrant ไม่พร้อมใช้งาน ระบบจะ fallback เป็น FTS-only
- **Oracle-aware** — แมป path จากโครงสร้าง κ/ψ ไปเป็น doc_type และ brain_tier อัตโนมัติ
- **Dedup** — ใช้ content_hash + scope เป็น unique constraint

---

## 2. การตั้งค่า (Config)

**ไฟล์:** `src/config.py`

คลาส `Settings` เป็น dataclass ที่อ่านค่าจาก environment variables:

| Environment Variable | Type | Default | คำอธิบาย |
|---|---|---|---|
| `DATABASE_URL` | `str` | `postgresql://admin:88888888@localhost:5432/mysynapse` | connection string ของ PostgreSQL |
| `QDRANT_URL` | `str` | `http://localhost:6333` | URL ของ Qdrant server |
| `QDRANT_COLLECTION` | `str` | `mysynapse_vectors` | ชื่อ collection ใน Qdrant |
| `OLLAMA_URL` | `str` | `http://localhost:11434` | URL ของ Ollama API |
| `EMBEDDING_MODEL` | `str` | `nomic-embed-text` | ชื่อโมเดล embedding |
| `EMBEDDING_DIM` | `int` | `768` | ขนาดเวกเตอร์ embedding |
| `EMBEDDING_TIMEOUT` | `int` | `30` | timeout การ embed (วินาที) |
| `MYSYNAPSE_HOST` | `str` | `0.0.0.0` | bind address ของ HTTP server |
| `MYSYNAPSE_PORT` | `int` | `8420` | port ของ HTTP server |
| `LOG_LEVEL` | `str` | `INFO` | logging level |
| `SEARCH_WEIGHTS` | `list[float]` | `[0.6, 0.4]` | น้ำหนัก RRF fusion (dense, FTS) |
| `SEARCH_RRF_K` | `int` | `60` | ค่าคงที่ k ของสูตร RRF |
| `CACHE_TTL` | `int` | `300` | cache TTL (วินาที) |
| `CACHE_MAX_SIZE` | `int` | `1000` | จำนวนรายการ cache สูงสุด |

---

## 3. CLI — จุดเข้าใช้งาน

**ไฟล์:** `src/main.py`

Entry point ลงทะเบียนใน `pyproject.toml` เป็น `synapse = "src.main:cli_main"`

### คำสั่ง

```bash
synapse serve    # เริ่ม HTTP API server (uvicorn)
synapse mcp      # เริ่ม MCP stdio server (สำหรับ Claude Code)
```

### วงจรการทำงานของ `serve`

1. สร้าง `Settings()` จาก environment variables
2. สร้าง `PgStore` → `connect()` → `init_schema()` (idempotent)
3. พยายามสร้าง `QdrantStore` → `connect()` — หากล้มเหลว ตั้ง `_qdrant = None` และทำงานในโหมด FTS-only
4. สร้าง `OllamaEmbedder`
5. เรียก `init_routes(pg, qdrant, embedder)` เพื่อเชื่อม globals เข้ากับ API router
6. uvicorn รัน FastAPI app บน `host:port` ที่กำหนด

### วงจรการทำงานของ `mcp`

1. เรียก `create_app()` ซึ่งทำขั้นตอนเดียวกับ `serve` ข้อ 1-5
2. สร้าง MCP `Server("synapse")`
3. ลงทะเบียน `list_tools` และ `call_tool` handlers
4. รันผ่าน `stdio_server()` context

---

## 4. ชั้นฐานข้อมูล (Database Layer)

### 4.1 PostgreSQL Store

**ไฟล์:** `src/db/pg_store.py`

คลาส `PgStore` — จัดเก็นข้อมูลหลัก รองรับ FTS ค้นหา, supersede, concepts, trace

#### Constructor

```python
PgStore(settings: Settings | None = None)
```

สร้าง connection pool (`min_size=2, max_size=10`) ตอน `connect()`

#### เมธอด CRUD

| เมธอด | พารามิเตอร์หลัก | ค่าคืน | คำอธิบาย |
|---|---|---|---|
| `add()` | `title, content, scope="shared", doc_type="learning", source_file, source_type="manual", source_project, oracle_name, brain_path, brain_tier, concepts, tags` | `dict` | เพิ่มเอกสาร คำนวณ `content_hash` (SHA-256[:16]) ตรวจซ้ำด้วย `(content_hash, scope)` ถ้าซ้ำคืน `status="duplicate"` |
| `get()` | `doc_id, include_chain=False` | `dict | None` | ดึงเอกสารตาม UUID หาก `include_chain=True` และมี `superseded_by` จะตามลิงก์ไปเอกสารใหม่ |
| `supersede()` | `old_id, new_content, reason="updated", new_title` | `dict` | สร้างเอกสารใหม่ คัดลอก metadata จากเอกสารเก่า ตั้ง `superseded_by` บนเอกสารเก่า บันทึกใน `supersede_log` |

#### เมธอดค้นหา (FTS)

```python
async def search_fts(
    query: str,
    scope: str | None = None,
    doc_type: str | None = None,
    oracle: str | None = None,
    source_project: str | None = None,
    limit: int = 10
) -> list[dict]
```

- สร้าง tsquery จากคำค้นหา (เชื่อมด้วย `|` = OR)
- กรองเฉพาะเอกสารที่ `superseded_by IS NULL`
- รองรับตัวกรองเพิ่มเติม: `scope`, `doc_type`, `oracle`, `source_project`
- เรียงลำดับตาม `ts_rank` จากมากไปน้อย
- คืนค่า: `[{id, title, scope, doc_type, oracle_name, source_project, score}]`

#### เมธอด Concepts

| เมธอด | พารามิเตอร์ | คำอธิบาย |
|---|---|---|
| `list_concepts(search=None, limit=50)` | ค้นหา/แสดง concepts ทั้งหมด กรองด้วย `ILIKE` หากมี `search` เรียงตาม `doc_count DESC` |

#### เมธอด Trace

| เมธอด | พารามิเตอร์ | คำอธิบาย |
|---|---|---|
| `add_trace(source_id, target_id, relation, confidence=1.0)` | เพิ่มลิงก์ระหว่างเอกสาร `relation` เป็นได้: `derived_from`, `refines`, `contradicts`, `extends` |
| `get_trace_chain(doc_id, direction="both", max_depth=5, relation=None)` | เดินตามกราฟ trace แบบ BFS `direction` เป็นได้: `upstream`, `downstream`, `both` |

#### เมธอด Scope & Stats

| เมธอด | คำอธิบาย |
|---|---|
| `list_scopes()` | ดึงรายการ scope ทั้งหมดจาก `scope_registry` |
| `stats()` | คืนสถิติ: `{total_documents, by_type, by_scope, by_oracle}` (ไม่นับเอกสารที่ถูก supersede) |
| `list_docs(scope, doc_type, oracle, limit=20, offset=0, order="newest")` | แสดงรายการเอกสารแบบแบ่งหน้า |

---

### 4.2 Qdrant Store

**ไฟล์:** `src/db/qdrant_store.py`

คลาส `QdrantStore` — จัดเก็นเวกเตอร์ embedding รองรับ payload filtering

#### Constructor

```python
QdrantStore(settings: Settings | None = None)
```

สร้าง `AsyncQdrantClient` ตอน `connect()` หาก collection ไม่มีจะสร้างใหม่ด้วย `VectorParams(size=embedding_dim, distance=COSINE)`

#### เมธอด

| เมธอด | พารามิเตอร์ | ค่าคืน | คำอธิบาย |
|---|---|---|---|
| `upsert()` | `doc_id, vector, title, scope, doc_type="learning", oracle_name, brain_tier, concepts` | `None` | เพิ่ม/อัปเดตเวกเตอร์ แปลง `doc_id` เป็น UUID hex สร้าง payload พร้อม `superseded=False` |
| `search()` | `vector, scope, doc_type, oracle, source_project, concepts, limit=10` | `list[dict]` | ค้นหาเวกเตอร์ด้วย cosine similarity กรองด้วย payload (เฉพาะ `superseded=False`) |
| `mark_superseded()` | `doc_id` | `None` | ตั้ง `superseded=True` บน payload ของเอกสารเก่า (silently catch exceptions) |
| `delete()` | `doc_id` | `None` | ลบ point ออกจาก Qdrant (silently catch exceptions) |

> **หมายเหตุ:** `mark_superseded()` และ `delete()` ไม่โยน exception หากล้มเหลว เพราะ PostgreSQL เป็นแหล่งข้อมูลหลัก (source of truth) และ Qdrant เป็นแค่ดัชนีอนุพันธ์

---

### 4.3 Schema

**ไฟล์:** `src/db/schema.sql`

Schema ทำงานแบบ idempotent (รันซ้ำได้) ประกอบด้วย:

#### ตาราง `knowledge_documents`

| คอลัมน์ | ประเภท | ข้อจำกัด |
|---|---|---|
| `id` | `UUID` | PK, auto-gen |
| `title` | `TEXT` | NOT NULL |
| `content` | `TEXT` | NOT NULL |
| `content_hash` | `TEXT` | NOT NULL, ส่วนหนึ่งของ UNIQUE(content_hash, scope) |
| `doc_type` | `TEXT` | NOT NULL DEFAULT 'learning' |
| `scope` | `TEXT` | NOT NULL DEFAULT 'shared' |
| `source_file` | `TEXT` | |
| `source_type` | `TEXT` | NOT NULL DEFAULT 'manual' |
| `source_project` | `TEXT` | |
| `oracle_name` | `TEXT` | |
| `brain_path` | `TEXT` | |
| `brain_tier` | `TEXT` | |
| `concepts` | `JSONB` | DEFAULT '[]' |
| `tags` | `JSONB` | DEFAULT '[]' |
| `superseded_by` | `UUID` | FK → knowledge_documents(id) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |
| `updated_at` | `TIMESTAMPTZ` | |
| `search_vector` | `tsvector` | auto-generated |

**Trigger `trg_search_vector`:** สร้าง tsvector จาก:
- `title` → weight A (สูงสุด)
- `content` → weight B
- `concepts` (JSONB text) → weight C

**Partial indexes** (เฉพาะ `WHERE superseded_by IS NULL`):
- `idx_doc_scope` บน `scope`
- `idx_doc_type` บน `doc_type`
- `idx_doc_oracle` บน `oracle_name`
- `idx_doc_brain_tier` บน `brain_tier`
- `idx_doc_source_project` บน `source_project`

#### ตาราง `supersede_log`

| คอลัมน์ | ประเภท | ข้อจำกัด |
|---|---|---|
| `id` | `UUID` | PK |
| `old_id` | `UUID` | FK → knowledge_documents |
| `new_id` | `UUID` | FK → knowledge_documents |
| `reason` | `TEXT` | DEFAULT 'updated' |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |

#### ตาราง `scope_registry`

| คอลัมน์ | ประเภท | ข้อจำกัด |
|---|---|---|
| `name` | `TEXT` | PK |
| `description` | `TEXT` | |
| `doc_count` | `INTEGER` | DEFAULT 0 |
| `oracle_name` | `TEXT` | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |

#### ตาราง `concepts`

| คอลัมน์ | ประเภท | ข้อจำกัด |
|---|---|---|
| `id` | `UUID` | PK |
| `name` | `TEXT` | NOT NULL UNIQUE |
| `description` | `TEXT` | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |

#### ตาราง `document_concepts` (junction)

| คอลัมน์ | ประเภท | ข้อจำกัด |
|---|---|---|
| `doc_id` | `UUID` | FK → knowledge_documents |
| `concept_id` | `UUID` | FK → concepts |

PK: `(doc_id, concept_id)`

#### ตาราง `trace`

| คอลัมน์ | ประเภท | ข้อจำกัด |
|---|---|---|
| `id` | `UUID` | PK |
| `source_id` | `UUID` | FK → knowledge_documents |
| `target_id` | `UUID` | FK → knowledge_documents |
| `relation` | `TEXT` | NOT NULL |
| `confidence` | `REAL` | DEFAULT 1.0 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() |

---

## 5. ชั้น Embedding

**ไฟล์:** `src/embed/ollama.py`

### ค่าคงที่

| ชื่อ | ค่า | คำอธิบาย |
|---|---|---|
| `MAX_CHUNK_CHARS` | `4000` | จำนวนตัวอักษรสูงสุดที่จะส่ง embed (ตัดทอนหากเกิน) |

### คลาส `OllamaEmbedder`

```python
OllamaEmbedder(settings: Settings | None = None)
```

ภายในตั้งค่า:
- `_max_retries = 2`
- `_batch_semaphore = asyncio.Semaphore(4)` (จำกัด concurrency สำหรับ batch)

#### เมธอด

| เมธอด | ลายเซ็น | คำอธิบาย |
|---|---|---|
| `embed()` | `async def embed(text: str) -> list[float]` | ตัดทอนข้อความเกิน 4000 ตัวอักษร → POST `/api/embed` → คืนเวกเตอร์ 768 มิติ ลองใหม่สูงสุด 2 ครั้งด้วย exponential backoff (0.5s, 1s) โยน `EmbeddingError` หากล้มเหลวทั้งหมด |
| `embed_batch()` | `async def embed_batch(texts: list[str]) -> list[list[float]]` | จำกัด concurrency ด้วย semaphore=4 เรียก `embed()` ทีละรายการตามลำดับ |
| `check()` | `async def check() -> bool` | เรียก `embed("health check")` คืน `True` หากสำเร็จ `False` หากล้มเหลว |

### คลาส `EmbeddingError`

Exception สำหรับ embed ล้มเหลว สืบทอดจาก `Exception`

---

## 6. ชั้นนำเข้า (Ingest Layer)

### 6.1 Push Pipeline

**ไฟล์:** `src/ingest/push.py`

คลาส `Push` — ประสานงานเขียนข้อมูลลงทั้ง PostgreSQL และ Qdrant

```python
Push(pg: PgStore, qdrant: QdrantStore | None = None, embedder: OllamaEmbedder | None = None)
```

#### `push_text()`

```python
async def push_text(
    title: str,
    content: str,
    scope: str = "shared",
    doc_type: str = "learning",
    source_file: str | None = None,
    source_type: str = "manual",
    source_project: str | None = None,
    oracle_name: str | None = None,
    brain_path: str | None = None,
    brain_tier: str | None = None,
    concepts: list[str] | None = None,
    tags: list[str] | None = None,
    embed: bool = True
) -> dict
```

**ขั้นตอน:**
1. ตรวจสอบ `doc_type` ด้วย `validate_doc_type()`
2. เรียก `pg.add()` → หาก `status == "duplicate"` คืนทันที
3. หาก `embed=True` และ qdrant+embedder พร้อมใช้:
   - embed เนื้อหา → `qdrant.upsert()`
   - หาก embed ล้มเหลว → ตั้ง `status = "indexed_pg_only"`
4. คืนผลลัพธ์: `{id, scope, status}`

#### `push_file()`

```python
async def push_file(
    file_path: str,
    scope: str | None = None,
    doc_type: str | None = None,
    embed: bool = True
) -> dict
```

**ขั้นตอน:**
1. อ่านไฟล์ ใช้ `Path.stem` เป็น title
2. หากไม่ระบุ scope/doc_type → เรียก `extract_metadata()` เพื่อดึงจาก path
3. ส่งต่อไป `push_text()` ด้วย `source_type="manual"`

---

### 6.2 Oracle Paths

**ไฟล์:** `src/ingest/oracle_paths.py`

แมป path จากโครงสร้าง κ/ψ ไปเป็น metadata อัตโนมัติ

#### ค่าคงที่

**`ORACLE_PATH_RULES`** — 10 กฎการแมป:

| Path Pattern | doc_type | brain_tier |
|---|---|---|
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

**`VALID_DOC_TYPES`** = `{learning, pattern, retro, reference, handoff, protocol, wisdom, instinct, log, note}`

**`VALID_TRACE_RELATIONS`** = `{derived_from, refines, contradicts, extends}`

#### ฟังก์ชัน

| ฟังก์ชัน | ลายเซ็น | คำอธิบาย |
|---|---|---|
| `extract_oracle_name()` | `(repo_path: str) -> str` | ดึงชื่อ oracle จาก basename ของ path ตัด `-oracle` ออก |
| `extract_metadata()` | `(file_path: str, repo_root: str) -> dict` | คำนวณ relative path ตรวจกับ `ORACLE_PATH_RULES` คืน `{oracle_name, brain_path, brain_tier, doc_type, scope}` ค่าเริ่มต้น: `doc_type="note"`, `brain_tier="extrinsic"`, `scope=oracle_name` |
| `validate_doc_type()` | `(doc_type: str) -> str` | โยน `ValueError` หาก doc_type ไม่อยู่ใน `VALID_DOC_TYPES` |
| `validate_trace_relation()` | `(relation: str) -> str` | โยน `ValueError` หาก relation ไม่อยู่ใน `VALID_TRACE_RELATIONS` |

---

### 6.3 Hook Handler

**ไฟล์:** `src/ingest/hook_handler.py`

รับข้อมูลอัตโนมัติจาก Claude Code PostToolUse hooks

#### ฟังก์ชัน

| ฟังก์ชัน | คำอธิบาย |
|---|---|
| `is_oracle_brain_path(file_path)` | ตรวจว่า path อยู่ในโครงสร้าง κ หรือ ψ หรือไม่ |
| `find_oracle_root(file_path)` | ตามหา directory ที่มี `CLAUDE.md` (oracle root) |
| `async ingest_file(file_path)` | นำเข้าไฟล์เข้า synapse โดยอัตโนมัติ สร้าง PgStore/Qdrant/OllamaEmbedder แยกต่างหาก ถ้า Qdrant หรือ Ollama ไม่พร้อมใช้ → ใส่เฉพาะ PostgreSQL ส่ง `source_type="hook"` |
| `main()` | รับ file path จาก `sys.argv[1]` หรือ JSON stdin จากนั้นเรียก `ingest_file()` |

**ขั้นตอนการทำงานของ `ingest_file()`:**

1. ตรวจสอบว่าไฟล์มีอยู่จริงและเป็น oracle brain path
2. หา oracle root → ดึง metadata ด้วย `extract_metadata()`
3. สร้าง `PgStore`, พยายามสร้าง `QdrantStore` (หากล้มเหลว → `None`)
4. สร้าง `OllamaEmbedder`, ตรวจสุขภาพด้วย `embedder.check()` (หากล้มเหลว → `None`)
5. เรียก `push.push_text()` ด้วย `source_type="hook"`
6. ปิดการเชื่อมต่อใน `finally`

---

## 7. ชั้นค้นคืน (Retrieve Layer)

**ไฟล์:** `src/retrieve/hybrid_search.py`

### ฟังก์ชัน `reciprocal_rank_fusion()`

```python
def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    weights: list[float] | None = None,
    k: int = 60
) -> list[dict]
```

**สูตร RRF:** `score = Σ(weight_i / (k + rank_i))` สำหรับแต่ละ list

- หากไม่ระบุ weights → ใช้ `[1.0/N] * N` (เท่ากันทุก list)
- รวมผลลัพธ์จากหลาย list โดยเก็บ metadata ของผลลัพธ์แรกที่พบแต่ละ doc_id
- เรียงลำดับตามคะแนนรวมจากมากไปน้อย

### คลาส `HybridSearch`

```python
HybridSearch(
    pg: PgStore,
    qdrant: QdrantStore | None = None,
    embedder: OllamaEmbedder | None = None,
    weights: list[float] | None = None,    # default: [0.6, 0.4]
    rrf_k: int = 60
)
```

#### เมธอด `search()`

```python
async def search(
    query: str,
    scope: str | None = None,
    doc_type: str | None = None,
    oracle: str | None = None,
    source_project: str | None = None,
    concepts: list[str] | None = None,
    limit: int = 10,
    mode: str = "hybrid"
) -> list[dict]
```

**โหมดการค้นหา 3 แบบ:**

| โหมด | พฤติกรรม | ข้อกำหนด |
|---|---|---|
| `"hybrid"` (default) | embed query → ค้นหา Qdrant + FTS → รวมด้วย RRF | หาก Qdrant/Embedder ไม่พร้อม → fallback เป็น FTS-only |
| `"dense"` | embed query → ค้นหา Qdrant เท่านั้น | ต้องมี Qdrant + Embedder โยน `SearchError` หากขาด |
| `"fts"` | ค้นหาด้วย PostgreSQL tsvector เท่านั้น | ไม่ต้องการ Qdrant หรือ Embedder |

**การ fallback ของ hybrid mode:**
1. หาก Qdrant หรือ Embedder ไม่พร้อม → ค้นหา FTS-only
2. หาก embed สำเร็จแต่ Qdrant search ล้มเหลว → โยน exception
3. หาก embed ล้มเหลว (`EmbeddingError`) → fallback เป็น FTS-only

### คลาส `SearchError`

Exception สำหรับการค้นหาล้มเหลว สืบทอดจาก `Exception`

---

## 8. MCP Server — 10 เครื่องมือ

**ไฟล์:** `src/mcp/server.py`

MCP Server ทำงานผ่าน stdio protocol เปิดใช้งานด้วย `synapse mcp`

### รายการเครื่องมือ

| # | ชื่อ | พารามิเตอร์บังคับ | พารามิเตอร์เลือก | คำอธิบาย |
|---|---|---|---|---|
| 1 | `synapse_search` | `query` | `scope, doc_type, oracle, source_project, concepts, limit=10, mode="hybrid"` | ค้นหาความรู้แบบ hybrid/FTS/dense |
| 2 | `synapse_push` | `title, content` | `scope="shared", doc_type="learning", source_file, source_project, concepts, tags, oracle_name, brain_path, brain_tier` | เพิ่มเอกสารใหม่เข้าระบบ |
| 3 | `synapse_supersede` | `old_id, new_content` | `new_title, reason="updated"` | แทนที่เอกสารเก่าด้วยเนื้อหาใหม่ |
| 4 | `synapse_trace` | `source_id, target_id, relation` | `confidence=1.0` | สร้างลิงก์ trace ระหว่างเอกสาร |
| 5 | `synapse_trace_chain` | `doc_id` | `direction="both", max_depth=5, relation` | เดินตามกราฟ trace จากเอกสาร |
| 6 | `synapse_concepts` | (ไม่มี) | `search, limit=50` | แสดง/ค้นหา concepts ทั้งหมด |
| 7 | `synapse_get` | `id` | `include_chain=True` | ดึงเอกสารตาม UUID |
| 8 | `synapse_scope` | (ไม่มี) | (ไม่มี) | แสดงรายการ scope ทั้งหมด |
| 9 | `synapse_stats` | (ไม่มี) | (ไม่มี) | แสดงสถิติ vault |
| 10 | `synapse_list` | (ไม่มี) | `scope, doc_type, oracle, limit=20, offset=0, order="newest"` | แสดงรายการเอกสารแบบแบ่งหน้า |

### การสร้าง MCP Server

```python
async def create_app(settings: Settings | None = None) -> Server
```

1. สร้าง `Settings`, `PgStore`, พยายามสร้าง `QdrantStore`
2. สร้าง `OllamaEmbedder`
3. สร้าง `Push` และ `HybridSearch`
4. สร้าง `Server("synapse")` ลงทะเบียน `list_tools` และ `call_tool`
5. คืน server

---

## 9. HTTP API

**ไฟล์:** `src/api/routes.py`

API Router ที่ทำงานบน `/api` prefix ให้บริการผ่าน HTTP สำหรับ Docker/service deployment

### การเริ่มต้น

```python
init_routes(pg_store, qdrant_store, embedder_client)
```

ตั้งค่า globals: `pg`, `qdrant`, `embedder`, `push`, `search`

### Endpoints

| Method | Path | พารามิเตอร์ (body/query) | คำอธิบาย |
|---|---|---|---|
| `POST` | `/api/search` | `{query, scope?, doc_type?, oracle?, source_project?, concepts?, limit=10, mode="hybrid"}` | ค้นหาแบบ hybrid |
| `POST` | `/api/push` | `{title, content, scope="shared", doc_type="learning", source_file?, source_type="api", source_project?, concepts?, tags?, oracle_name?, brain_path?, brain_tier?}` | เพิ่มเอกสาร |
| `POST` | `/api/webhook` | `{title, content, ...}` (auto `source_type="webhook"`) | รับข้อมูลจากภายนอก |
| `POST` | `/api/supersede` | `{old_id, new_content, reason="updated", new_title?}` | แทนที่เอกสาร |
| `POST` | `/api/trace` | `{source_id, target_id, relation, confidence=1.0}` | สร้าง trace link |
| `GET` | `/api/trace/{doc_id}` | `?direction=both&max_depth=5&relation=` | ตาม trace chain |
| `GET` | `/api/concepts` | `?search=&limit=50` | แสดง/ค้นหา concepts |
| `GET` | `/api/documents/{doc_id}` | `?include_chain=True` | ดึงเอกสาร (404 หากไม่พบ) |
| `GET` | `/api/documents` | `?scope=&doc_type=&oracle=&limit=20&offset=0&order=newest` | แสดงรายการเอกสาร |
| `GET` | `/api/scopes` | (ไม่มี) | แสดง scope ทั้งหมด |
| `GET` | `/api/stats` | (ไม่มี) | แสดงสถิติ |
| `GET` | `/api/health` | (ไม่มี) | ตรวจสอบสุขภาพ: `{status, qdrant, embedding}` |

### การตอบสนองพิเศษ

- `/api/documents/{doc_id}` → คืน HTTP 404 พร้อม `{"detail": "Document not found"}` หากไม่พบ
- `/api/health` → ตรวจสอบ Qdrant (bool) และ Ollama (`embedder.check()`) ไม่โยน exception หากล้มเหลว

---

## 10. ตารางเปรียบเทียบ MCP vs HTTP

| ฟังก์ชัน | MCP Tool | HTTP Endpoint | ข้อแตกต่าง |
|---|---|---|---|
| ค้นหา | `synapse_search` | `POST /api/search` | พารามิเตอร์เหมือนกัน |
| เพิ่มเอกสาร | `synapse_push` | `POST /api/push` | HTTP มี `source_type="api"` เป็น default |
| รับจาก webhook | — | `POST /api/webhook` | HTTP-only, auto `source_type="webhook"` |
| แทนที่ | `synapse_supersede` | `POST /api/supersede` | HTTP เรียก `qdrant.mark_superseded()` เพิ่มเติม |
| สร้าง trace | `synapse_trace` | `POST /api/trace` | เหมือนกัน |
| ตาม trace chain | `synapse_trace_chain` | `GET /api/trace/{doc_id}` | พารามิเตอร์เหมือนกัน (เป็น query params) |
| แสดง concepts | `synapse_concepts` | `GET /api/concepts` | เหมือนกัน |
| ดึงเอกสาร | `synapse_get` | `GET /api/documents/{doc_id}` | HTTP คืน 404 หากไม่พบ |
| แสดง scope | `synapse_scope` | `GET /api/scopes` | เหมือนกัน |
| สถิติ | `synapse_stats` | `GET /api/stats` | เหมือนกัน |
| แสดงรายการ | `synapse_list` | `GET /api/documents` | เหมือนกัน |
| ตรวจสอบสุขภาพ | — | `GET /api/health` | HTTP-only |

---

## ภาคผนวก: รูปแบบการตอบสนอง

### Push Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "scope": "shared",
  "status": "indexed"          // หรือ "duplicate" หรือ "indexed_pg_only"
}
```

### Search Response

```json
[
  {
    "id": "550e8400-...",
    "title": "Docker Patterns",
    "scope": "shared",
    "doc_type": "learning",
    "oracle_name": "emily",
    "source_project": "emily-oracle",
    "score": 0.0153
  }
]
```

### Stats Response

```json
{
  "total_documents": 150,
  "by_type": {"learning": 80, "pattern": 40, "retro": 30},
  "by_scope": {"shared": 100, "emily": 50},
  "by_oracle": {"emily": 50}
}
```

### Health Response

```json
{
  "status": "ok",
  "qdrant": true,
  "embedding": true
}
```