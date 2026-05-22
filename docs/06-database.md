# 06 — ฐานข้อมูล (Database)

> PostgreSQL schema, Qdrant collections, FTS tsvector, indexes, dedup mechanism

Synapse ใช้ระบบฐานข้อมูลคู่: PostgreSQL สำหรับ CRUD, full-text search, และ metadata — Qdrant สำหรับ vector search ทั้งสองทำงานร่วมกันผ่าน hybrid search ด้วย RRF fusion

---

## ภาพรวมสถาปัตยกรรม

```
                    ┌──────────────────────┐
                    │   Application Layer   │
                    └──────┬───────┬────────┘
                           │       │
              ┌────────────▼──┐  ┌─▼────────────┐
              │  PostgreSQL   │  │    Qdrant     │
              │  (source of   │  │  (derivative   │
              │   truth)      │  │   index)      │
              │              │  │               │
              │ - CRUD       │  │ - Vectors     │
              │ - FTS        │  │ - COSINE      │
              │ - Supersede  │  │ - Payload     │
              │ - Concepts   │  │   Filter      │
              │ - Trace      │  │               │
              │ - Registry   │  └───────────────┘
              └──────────────┘
```

**หลักการ:** PostgreSQL เป็นแหล่งข้อมูลหลัก (source of truth) Qdrant เป็นดัชนีอนุพันธ์ การล้มเหลวของ Qdrant ไม่ทำให้ระบบล่ม (fallback เป็น FTS-only)

---

## PostgreSQL Schema

**ไฟล์:** `src/db/schema.sql`

Schema ทำงานแบบ idempotent — รันซ้ำได้โดยไม่เกิด error `init_schema()` ถูกเรียกทุกครั้งที่ server start

### ตาราง `knowledge_documents`

| คอลัมน์ | ประเภท | ข้อจำกัด | คำอธิบาย |
|---------|--------|---------|----------|
| `id` | `UUID` | PK, auto-gen | รหัสเอกสาร |
| `title` | `TEXT` | NOT NULL | ชื่อเอกสาร |
| `content` | `TEXT` | NOT NULL | เนื้อหาเอกสาร |
| `content_hash` | `TEXT` | NOT NULL, UNIQUE(content_hash, scope) | SHA-256 ตัดทอน 16 ตัวอักษร |
| `doc_type` | `TEXT` | NOT NULL DEFAULT 'learning' | ประเภทเอกสาร |
| `scope` | `TEXT` | NOT NULL DEFAULT 'shared' | namespace |
| `source_file` | `TEXT` | - | path ของไฟล์ต้นฉบับ |
| `source_type` | `TEXT` | NOT NULL DEFAULT 'manual' | manual / api / webhook / hook / init_scan |
| `source_project` | `TEXT` | - | โปรเจกต์ต้นทาง |
| `oracle_name` | `TEXT` | - | ชื่อ Oracle |
| `brain_path` | `TEXT` | - | path ในโครงสร้าง k/p |
| `brain_tier` | `TEXT` | - | intrinsic / extrinsic |
| `concepts` | `JSONB` | DEFAULT '[]' | concepts array |
| `tags` | `JSONB` | DEFAULT '[]' | tags array |
| `superseded_by` | `UUID` | FK -> knowledge_documents(id) | เอกสารที่แทนที่ |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | เวลาสร้าง |
| `updated_at` | `TIMESTAMPTZ` | - | เวลาอัปเดต |
| `search_vector` | `tsvector` | auto-generated | full-text search vector |

#### Unique Constraint

```sql
UNIQUE(content_hash, scope)
```

ใช้สำหรับ dedup: เอกสารที่มีเนื้อหาเดียวกันใน scope เดียวกันจะถูกปฏิเสธที่ระดับ database

### ตาราง `supersede_log`

| คอลัมน์ | ประเภท | ข้อจำกัด | คำอธิบาย |
|---------|--------|---------|----------|
| `id` | `UUID` | PK | รหัส log |
| `old_id` | `UUID` | FK -> knowledge_documents | เอกสารเก่า |
| `new_id` | `UUID` | FK -> knowledge_documents | เอกสารใหม่ |
| `reason` | `TEXT` | DEFAULT 'updated' | เหตุผลการ supersede |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | เวลาที่ supersede |

### ตาราง `scope_registry`

| คอลัมน์ | ประเภท | ข้อจำกัด | คำอธิบาย |
|---------|--------|---------|----------|
| `name` | `TEXT` | PK | ชื่อ scope |
| `description` | `TEXT` | - | รายละเอียด |
| `doc_count` | `INTEGER` | DEFAULT 0 | จำนวนเอกสาร |
| `oracle_name` | `TEXT` | - | Oracle ที่เกี่ยวข้อง |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | เวลาสร้าง |

### ตาราง `concepts`

| คอลัมน์ | ประเภท | ข้อจำกัด | คำอธิบาย |
|---------|--------|---------|----------|
| `id` | `UUID` | PK | รหัส concept |
| `name` | `TEXT` | NOT NULL UNIQUE | ชื่อ concept |
| `description` | `TEXT` | - | รายละเอียด |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | เวลาสร้าง |

### ตาราง `document_concepts` (junction)

| คอลัมน์ | ประเภท | ข้อจำกัด | คำอธิบาย |
|---------|--------|---------|----------|
| `doc_id` | `UUID` | FK -> knowledge_documents | เอกสาร |
| `concept_id` | `UUID` | FK -> concepts | Concept |

PK: `(doc_id, concept_id)`

### ตาราง `trace`

| คอลัมน์ | ประเภท | ข้อจำกัด | คำอธิบาย |
|---------|--------|---------|----------|
| `id` | `UUID` | PK | รหัส trace |
| `source_id` | `UUID` | FK -> knowledge_documents | เอกสารต้นทาง |
| `target_id` | `UUID` | FK -> knowledge_documents | เอกสารปลายทาง |
| `relation` | `TEXT` | NOT NULL | derived_from / refines / contradicts / extends |
| `confidence` | `REAL` | DEFAULT 1.0 | คะแนนความมั่นใจ |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | เวลาสร้าง |

### ตาราง `registered_projects`

| คอลัมน์ | ประเภท | ข้อจำกัด | คำอธิบาย |
|---------|--------|---------|----------|
| `scope` | `TEXT` | PK | ชื่อ scope |
| `project_path` | `TEXT` | NOT NULL | path ของโปรเจกต์ |
| `registered_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | เวลาลงทะเบียน |

---

## Indexes

### GIN Index (Full-Text Search)

```sql
CREATE INDEX IF NOT EXISTS idx_doc_search
ON knowledge_documents USING GIN(search_vector);
```

GIN index สำหรับ tsvector ช่วยให้ `@@` operator ทำงานอย่างมีประสิทธิภาพ

### Partial Indexes (เฉพาะเอกสารที่ยังไม่ถูก supersede)

```sql
CREATE INDEX IF NOT EXISTS idx_doc_scope
ON knowledge_documents(scope) WHERE superseded_by IS NULL;

CREATE INDEX IF NOT EXISTS idx_doc_type
ON knowledge_documents(doc_type) WHERE superseded_by IS NULL;

CREATE INDEX IF NOT EXISTS idx_doc_oracle
ON knowledge_documents(oracle_name) WHERE superseded_by IS NULL;

CREATE INDEX IF NOT EXISTS idx_doc_brain_tier
ON knowledge_documents(brain_tier) WHERE superseded_by IS NULL;

CREATE INDEX IF NOT EXISTS idx_doc_source_project
ON knowledge_documents(source_project) WHERE superseded_by IS NULL;
```

Partial indexes ทำให้ query ที่กรอง `superseded_by IS NULL` ทำงานเร็วขึ้น เพราะ index ไม่รวมเอกสารที่ถูก supersede

###  indexes อื่นๆ

```sql
CREATE INDEX IF NOT EXISTS idx_doc_hash
ON knowledge_documents(content_hash);

CREATE INDEX IF NOT EXISTS idx_dc_doc
ON document_concepts(doc_id);

CREATE INDEX IF NOT EXISTS idx_dc_concept
ON document_concepts(concept_id);

CREATE INDEX IF NOT EXISTS idx_trace_source
ON trace(source_id);

CREATE INDEX IF NOT EXISTS idx_trace_target
ON trace(target_id);
```

---

## tsvector Generation

### Trigger Function

```sql
CREATE OR REPLACE FUNCTION update_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.content, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(
            (SELECT string_agg(value::text, ' ')
             FROM jsonb_array_elements_text(NEW.concepts) AS value), ''
        )), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

### Weight Hierarchy

| ฟิลด์ | Weight | ผลกระทบต่อการจัดอันดับ |
|-------|--------|----------------------|
| `title` | `A` (สูงสุด) | คำในชื่อมีน้ำหนักมากที่สุด |
| `content` | `B` | เนื้อหามีน้ำหนักปานกลาง |
| `concepts` | `C` | concepts มีน้ำหนักต่ำสุด |

Trigger ทำงานก่อน INSERT และ UPDATE ทุกครั้ง:

```sql
CREATE TRIGGER trg_search_vector
    BEFORE INSERT OR UPDATE ON knowledge_documents
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();
```

---

## Qdrant Collection

### การสร้าง Collection

```python
await client.create_collection(
    collection_name="synapse_vectors",
    vectors_config=VectorParams(
        size=768,            # embedding_dim
        distance=Distance.COSINE,
    ),
)
```

หาก collection มีอยู่แล้วจะข้ามการสร้าง

### Point Structure

แต่ละ point ใน Qdrant ประกอบด้วย:

```python
PointStruct(
    id=uuid_hex,           # UUID แปลงเป็น hex string
    vector=[...768 floats],
    payload={
        "title": "...",
        "scope": "...",
        "doc_type": "...",
        "superseded": False,
        "oracle_name": "...",   # optional
        "brain_tier": "...",    # optional
        "concepts": [...],      # optional
        "created_at": "",
    }
)
```

### Payload Filtering

Qdrant ใช้ payload filter เพื่อกรองผลลัพธ์:

```python
conditions = [
    FieldCondition(key="superseded", match=MatchValue(value=False)),
    FieldCondition(key="scope", match=MatchValue(value="myproject")),
    FieldCondition(key="doc_type", match=MatchValue(value="pattern")),
]

search_filter = Filter(must=conditions)
results = await client.query_points(
    collection_name="synapse_vectors",
    query=vector,
    query_filter=search_filter,
    limit=10,
    with_payload=True,
)
```

### Mark Superseded

เมื่อเอกสารถูก supersede ใน PostgreSQL Qdrant payload จะถูกอัปเดต:

```python
await client.set_payload(
    collection_name="synapse_vectors",
    payload={"superseded": True},
    points=[uuid_hex],
)
```

การอัปเดตนี้ทำแบบ best-effort: หาก Qdrant ไม่พร้อม จะไม่โยน exception (เพราะ PostgreSQL เป็น source of truth)

---

## Connection Pool

### PostgreSQL (asyncpg)

```python
pool = await asyncpg.create_pool(
    database_url,
    min_size=2,
    max_size=10,
)
```

- `min_size=2`: รักษา 2 connections ไว้เสมอ
- `max_size=10`: สูงสุด 10 connections พร้อมกัน

### Qdrant (AsyncQdrantClient)

```python
client = AsyncQdrantClient(url="http://localhost:6333")
```

Qdrant client จัดการ connection pool ภายในเอง

---

## Dedup Mechanism

Dedup ทำงานที่ 2 ระดับ:

### 1. Database Level (hard constraint)

```sql
UNIQUE(content_hash, scope)
```

`content_hash` คือ SHA-256 ตัดทอนเหลือ 16 ตัวอักษรแรก หากมีเอกสารที่มี hash + scope เดียวกัน INSERT จะล้มเหลว

### 2. Application Level (soft check)

```python
async def add(self, title, content, scope, ...):
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    existing = await conn.fetchrow(
        "SELECT id FROM knowledge_documents WHERE content_hash = $1 AND scope = $2",
        content_hash, scope,
    )
    if existing:
        return {"id": str(existing["id"]), "scope": scope, "status": "duplicate"}
```

ตรวจสอบก่อน INSERT หากพบข้อมูลซ้ำจะคืน `status="duplicate"` ทันทีโดยไม่เขียนซ้ำ

---

## การจัดการ Lifecycle

### Connect

```python
pg = PgStore(settings)
await pg.connect()        # สร้าง connection pool
await pg.init_schema()    # สร้าง/อัปเดต schema (idempotent)
```

### Close

```python
await pg.close()          # ปิด connection pool
```

### Qdrant Fallback

```python
qdrant = None
try:
    qdrant = QdrantStore(settings)
    await qdrant.connect()
except Exception:
    log.warning("Qdrant not available, running in FTS-only mode")
    qdrant = None
```

หาก Qdrant ไม่พร้อมใช้งาน ระบบจะทำงานในโหมด FTS-only อัตโนมัติ