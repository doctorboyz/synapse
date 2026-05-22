# 04 — HTTP API Reference

> REST API endpoints ทั้งหมดสำหรับเข้าถึงคลังความรู้ Synapse ผ่าน HTTP

HTTP API server เริ่มด้วย `synapse serve` ที่ port 8420 (default) ทุก endpoint อยู่ภายใต้ prefix `/api`

---

## การเริ่ม Server

```bash
synapse serve
# ปรับ port ผ่าน environment variable
SYNAPSE_PORT=9000 synapse serve
```

Base URL: `http://localhost:8420/api/`

---

## สารบัญ Endpoints

| Method | Path | คำอธิบาย |
|--------|------|----------|
| POST | `/api/search` | ค้นหาความรู้แบบ hybrid |
| POST | `/api/push` | เพิ่มเอกสารเข้าคลัง |
| POST | `/api/webhook` | รับข้อมูลจาก webhook ภายนอก |
| POST | `/api/supersede` | อัปเดตเอกสารแบบ supersession |
| POST | `/api/trace` | สร้าง trace link |
| GET | `/api/trace/{doc_id}` | ตามลูกโซ่ trace |
| GET | `/api/concepts` | แสดง/ค้นหา concepts |
| GET | `/api/documents/{doc_id}` | ดึงเอกสารตาม ID |
| GET | `/api/documents` | แสดงรายการเอกสาร |
| GET | `/api/scopes` | แสดง scope ทั้งหมด |
| GET | `/api/stats` | สถิติคลังความรู้ |
| GET | `/api/health` | ตรวจสอบสุขภาพระบบ |
| GET | `/api/health/live` | Liveness probe |
| GET | `/api/health/ready` | Readiness probe |
| POST | `/api/register` | ลงทะเบียนโปรเจกต์ |
| POST | `/api/unregister` | ยกเลิกลงทะเบียน |
| GET | `/api/projects` | แสดงโปรเจกต์ที่ลงทะเบียน |
| POST | `/api/search-cross` | ค้นหาข้ามหลาย scope |

---

## Search

### `POST /api/search`

ค้นหาความรู้ด้วย hybrid search

```bash
curl -X POST http://localhost:8420/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "error handling patterns",
    "scope": "myproject",
    "doc_type": "pattern",
    "limit": 10,
    "mode": "hybrid"
  }'
```

| พารามิเตอร์ (body) | ประเภท | Default | คำอธิบาย |
|---------------------|--------|---------|----------|
| `query` | string | (จำเป็น) | คำค้นหา |
| `scope` | string | - | กรองตาม scope |
| `doc_type` | string | - | กรองตาม doc_type |
| `oracle` | string | - | กรองตาม oracle |
| `source_project` | string | - | กรองตาม source project |
| `concepts` | array[string] | - | กรองตาม concepts |
| `limit` | integer | `10` | จำนวนผลลัพธ์ |
| `mode` | string | `"hybrid"` | hybrid / dense / fts |

**ผลลัพธ์:**

```json
[
  {
    "id": "uuid-here",
    "title": "Error Handling Best Practices",
    "scope": "myproject",
    "doc_type": "pattern",
    "oracle_name": "caretaker",
    "source_project": "myapp",
    "score": 0.0321
  }
]
```

---

## Push

### `POST /api/push`

เพิ่มเอกสารเข้าคลังความรู้

```bash
curl -X POST http://localhost:8420/api/push \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Python Error Handling",
    "content": "Always catch specific exceptions. Never use bare except.",
    "scope": "myproject",
    "doc_type": "learning",
    "concepts": ["error-handling", "python"],
    "tags": ["best-practices"],
    "source_project": "myapp"
  }'
```

| พารามิเตอร์ (body) | ประเภท | Default | คำอธิบาย |
|---------------------|--------|---------|----------|
| `title` | string | (จำเป็น) | ชื่อเอกสาร |
| `content` | string | (จำเป็น) | เนื้อหา |
| `scope` | string | `"shared"` | scope/namespace |
| `doc_type` | string | `"learning"` | ประเภทเอกสาร |
| `source_file` | string | - | path ของไฟล์ต้นฉบับ |
| `source_type` | string | `"api"` | แหล่งที่มา |
| `source_project` | string | - | โปรเจกต์ต้นทาง |
| `concepts` | array[string] | - | concepts |
| `tags` | array[string] | - | tags |
| `oracle_name` | string | - | ชื่อ oracle |
| `brain_path` | string | - | brain path |
| `brain_tier` | string | - | brain tier |

**ผลลัพธ์:**

```json
{
  "id": "uuid-here",
  "scope": "myproject",
  "status": "indexed"
}
```

### `POST /api/webhook`

รับข้อมูลจาก webhook ภายนอก — เหมือน `/api/push` แต่ `source_type` เป็น `"webhook"` อัตโนมัติ

```bash
curl -X POST http://localhost:8420/api/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Auto-ingested Knowledge",
    "content": "Content from external source",
    "scope": "external"
  }'
```

---

## Supersede

### `POST /api/supersede`

อัปเดตเอกสารแบบ supersession — เอกสารเก่าไม่ถูกลบ ถูก mark ว่า `superseded_by`

```bash
curl -X POST http://localhost:8420/api/supersede \
  -H "Content-Type: application/json" \
  -d '{
    "old_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "new_content": "Updated content with corrections",
    "reason": "bug_fix"
  }'
```

| พารามิเตอร์ (body) | ประเภท | Default | คำอธิบาย |
|---------------------|--------|---------|----------|
| `old_id` | string | (จำเป็น) | UUID เอกสารเก่า |
| `new_content` | string | (จำเป็น) | เนื้อหาใหม่ |
| `new_title` | string | ใช้ title เดิม | ชื่อใหม่ |
| `reason` | string | `"updated"` | เหตุผล |

เมื่อ supersede สำเร็จ ระบบจะเรียก `qdrant.mark_superseded()` เพื่อ mark payload ใน Qdrant ด้วย

**ผลลัพธ์:**

```json
{
  "id": "new-uuid",
  "superseded": "old-uuid",
  "status": "superseded"
}
```

---

## Trace

### `POST /api/trace`

สร้าง trace link ระหว่างเอกสาร

```bash
curl -X POST http://localhost:8420/api/trace \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "uuid-a",
    "target_id": "uuid-b",
    "relation": "derived_from",
    "confidence": 0.9
  }'
```

| พารามิเตอร์ (body) | ประเภท | Default | คำอธิบาย |
|---------------------|--------|---------|----------|
| `source_id` | string | (จำเป็น) | UUID เอกสารต้นทาง |
| `target_id` | string | (จำเป็น) | UUID เอกสารปลายทาง |
| `relation` | string | (จำเป็น) | derived_from / refines / contradicts / extends |
| `confidence` | number | `1.0` | คะแนนความมั่นใจ (0-1) |

### `GET /api/trace/{doc_id}`

ตามลูกโซ่ trace จากเอกสาร

```bash
curl "http://localhost:8420/api/trace/a1b2c3d4-e5f6-7890-abcd-ef1234567890?direction=both&max_depth=5"
```

| Query Parameter | Default | คำอธิบาย |
|----------------|---------|----------|
| `direction` | `both` | both / upstream / downstream |
| `max_depth` | `5` | ความลึกสูงสุด |
| `relation` | - | กรองเฉพาะ relation type |

---

## Concepts

### `GET /api/concepts`

แสดงหรือค้นหา concepts

```bash
# แสดง concepts ทั้งหมด
curl http://localhost:8420/api/concepts

# ค้นหา
curl "http://localhost:8420/api/concepts?search=error&limit=20"
```

| Query Parameter | Default | คำอธิบาย |
|----------------|---------|----------|
| `search` | - | ค้นหาตามชื่อ (ILIKE) |
| `limit` | `50` | จำนวนผลลัพธ์สูงสุด |

**ผลลัพธ์:**

```json
[
  {"name": "error-handling", "description": null, "doc_count": 5},
  {"name": "error-recovery", "description": null, "doc_count": 2}
]
```

---

## Documents

### `GET /api/documents/{doc_id}`

ดึงเอกสารตาม ID

```bash
curl http://localhost:8420/api/documents/a1b2c3d4-e5f6-7890-abcd-ef1234567890

# ไม่รวม supersession chain
curl "http://localhost:8420/api/documents/a1b2c3d4-...?include_chain=false"
```

| Query Parameter | Default | คำอธิบาย |
|----------------|---------|----------|
| `include_chain` | `true` | รวม supersession chain |

**ผลลัพธ์:** เอกสารฉบับเต็ม หากไม่พบจะคืน HTTP 404:

```json
{"detail": "Document not found"}
```

### `GET /api/documents`

แสดงรายการเอกสารพร้อมตัวกรอง

```bash
curl "http://localhost:8420/api/documents?scope=myproject&doc_type=learning&limit=50&offset=0&order=newest"
```

| Query Parameter | Default | คำอธิบาย |
|----------------|---------|----------|
| `scope` | - | กรองตาม scope |
| `doc_type` | - | กรองตาม doc_type |
| `oracle` | - | กรองตาม oracle |
| `limit` | `20` | จำนวนผลลัพธ์ |
| `offset` | `0` | ตำแหน่งเริ่ม pagination |
| `order` | `newest` | newest / oldest |

---

## Scopes & Stats

### `GET /api/scopes`

แสดง scope ทั้งหมด

```bash
curl http://localhost:8420/api/scopes
```

### `GET /api/stats`

แสดงสถิติคลังความรู้

```bash
curl http://localhost:8420/api/stats
```

**ผลลัพธ์:**

```json
{
  "total_documents": 57,
  "by_type": {"learning": 30, "pattern": 12, "retro": 8, "note": 7},
  "by_scope": {"myproject": 42, "shared": 15},
  "by_oracle": {"caretaker": 25, "coder": 17}
}
```

---

## Health Checks

### `GET /api/health`

ตรวจสอบสุขภาพระบบรวม Qdrant และ Embedding

```bash
curl http://localhost:8420/api/health
```

**ผลลัพธ์:**

```json
{
  "status": "ok",
  "qdrant": true,
  "embedding": true
}
```

### `GET /api/health/live`

Liveness probe — ตรวจว่า process ยังทำงานอยู่

```bash
curl http://localhost:8420/api/health/live
```

**ผลลัพธ์:**

```json
{"alive": true}
```

### `GET /api/health/ready`

Readiness probe — ตรวจว่า dependencies พร้อมหรือไม่

```bash
curl http://localhost:8420/api/health/ready
```

**ผลลัพธ์:**

```json
{
  "ready": true,
  "pg": true,
  "qdrant": true,
  "embedding": false
}
```

`ready` เป็น `true` เมื่อ PostgreSQL พร้อมเท่านั้น (Qdrant และ Embedding ไม่บังคับ เป็น `false` ได้)

---

## Registry

### `POST /api/register`

ลงทะเบียนโปรเจกต์

```bash
curl -X POST http://localhost:8420/api/register \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/Users/user/code/myproject", "scope": "myproject"}'
```

### `POST /api/unregister`

ยกเลิกลงทะเบียนโปรเจกต์

```bash
curl -X POST http://localhost:8420/api/unregister \
  -H "Content-Type: application/json" \
  -d '{"scope": "myproject"}'
```

### `GET /api/projects`

แสดงโปรเจกต์ที่ลงทะเบียนทั้งหมด

```bash
curl http://localhost:8420/api/projects
```

**ผลลัพธ์:**

```json
[
  {
    "scope": "myproject",
    "project_path": "/Users/user/code/myproject",
    "registered_at": "2025-01-15 10:30:00"
  }
]
```

---

## Cross-Project Search

### `POST /api/search-cross`

ค้นหาข้ามหลาย scope รวมผลลัพธ์ตามคะแนนสูงสุด

```bash
curl -X POST http://localhost:8420/api/search-cross \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deployment patterns",
    "scopes": ["team-alpha", "team-beta", "shared"],
    "limit": 10,
    "mode": "hybrid"
  }'
```

| พารามิเตอร์ (body) | ประเภท | Default | คำอธิบาย |
|---------------------|--------|---------|----------|
| `query` | string | (จำเป็น) | คำค้นหา |
| `scopes` | array[string] | (จำเป็น) | list ของ scope names |
| `limit` | integer | `10` | จำนวนผลลัพธ์ |
| `mode` | string | `"hybrid"` | โหมดค้นหา |

---

## ข้อสังเกต

1. ทุก endpoint ตอบเป็น JSON
2. `POST /api/webhook` ต่างจาก `/api/push` เฉพาะ `source_type` ที่เป็น `"webhook"` อัตโนมัติ
3. `/api/documents/{doc_id}` เป็น endpoint เดียวที่คืน HTTP 404 เมื่อไม่พบเอกสาร
4. `/api/supersede` เรียก `qdrant.mark_superseded()` เพิ่มเติมจาก PostgreSQL supersede
5. Health checks ออกแบบตาม Kubernetes pattern: liveness, readiness