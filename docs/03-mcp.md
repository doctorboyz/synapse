# 03 — MCP Tools Reference

> เครื่องมือ MCP ทั้ง 14 ตัวสำหรับ AI agent เข้าถึงคลังความรู้

MCP (Model Context Protocol) server ทำงานผ่าน stdio transport ช่วยให้ AI agent เช่น Claude Code สามารถเข้าถึงคลังความรู้ Synapse ได้โดยตรง

---

## การเริ่ม MCP Server

```bash
synapse mcp
```

หรือระบุใน Claude Code config:

```json
{
  "mcpServers": {
    "synapse": {
      "command": "synapse",
      "args": ["mcp"]
    }
  }
}
```

---

## สารบัญเครื่องมือ

| # | ชื่อเครื่องมือ | หมวด | คำอธิบาย |
|---|--------------|------|----------|
| 1 | `synapse_search` | Retrieve | ค้นหาความรู้แบบ hybrid |
| 2 | `synapse_push` | Ingest | เพิ่มความรู้เข้าคลัง |
| 3 | `synapse_supersede` | Version | อัปเดตเอกสารแบบ supersession |
| 4 | `synapse_trace` | Relation | สร้าง trace link |
| 5 | `synapse_trace_chain` | Relation | ตามลูกโซ่ trace |
| 6 | `synapse_concepts` | Metadata | แสดง/ค้นหา concepts |
| 7 | `synapse_get` | Retrieve | ดึงเอกสารตาม ID |
| 8 | `synapse_scope` | Retrieve | แสดง scope ทั้งหมด |
| 9 | `synapse_stats` | Retrieve | สถิติคลังความรู้ |
| 10 | `synapse_list` | Retrieve | แสดงรายการเอกสาร |
| 11 | `synapse_register` | Registry | ลงทะเบียนโปรเจกต์ |
| 12 | `synapse_unregister` | Registry | ยกเลิกลงทะเบียน |
| 13 | `synapse_projects` | Registry | แสดงโปรเจกต์ที่ลงทะเบียน |
| 14 | `synapse_search_cross` | Retrieve | ค้นหาข้ามหลาย scope |

---

## Retrieve Tools

### 1. `synapse_search`

ค้นหาความรู้ในคลังด้วย hybrid dense+keyword search คืนผลลัพธ์เรียงตามคะแนน

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `query` | string | **ใช่** | - | คำค้นหา |
| `scope` | string | ไม่ | - | กรองตาม scope |
| `doc_type` | string | ไม่ | - | กรองตาม doc_type |
| `oracle` | string | ไม่ | - | กรองตาม oracle name |
| `source_project` | string | ไม่ | - | กรองตาม source project |
| `concepts` | array[string] | ไม่ | - | กรองตาม concepts |
| `limit` | integer | ไม่ | `10` | จำนวนผลลัพธ์สูงสุด |
| `mode` | string | ไม่ | `"hybrid"` | โหมด: `hybrid`, `dense`, `fts` |

**ตัวอย่าง:**

```json
{
  "query": "error handling patterns",
  "scope": "myproject",
  "limit": 5,
  "mode": "hybrid"
}
```

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

### 2. `synapse_get`

ดึงเอกสารตาม UUID รวม supersession history

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `id` | string | **ใช่** | - | UUID ของเอกสาร |
| `include_chain` | boolean | ไม่ | `true` | รวม supersession chain |

**ตัวอย่าง:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "include_chain": true
}
```

**ผลลัพธ์:**

```json
{
  "id": "a1b2c3d4-...",
  "title": "Error Handling Best Practices",
  "content": "Always catch specific exceptions...",
  "scope": "shared",
  "doc_type": "pattern",
  "superseded_by": null,
  "supersession_chain": [],
  "concepts": ["error-handling", "python"],
  "tags": ["best-practices"],
  "created_at": "2025-01-15 10:30:00"
}
```

หากไม่พบเอกสาร:

```json
{"error": "not found"}
```

---

### 3. `synapse_list`

แสดงรายการเอกสารพร้อมตัวกรอง คืนเฉพาะสรุป

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `scope` | string | ไม่ | - | กรองตาม scope |
| `doc_type` | string | ไม่ | - | กรองตาม doc_type |
| `oracle` | string | ไม่ | - | กรองตาม oracle name |
| `limit` | integer | ไม่ | `20` | จำนวนผลลัพธ์สูงสุด |
| `offset` | integer | ไม่ | `0` | offset สำหรับ pagination |
| `order` | string | ไม่ | `"newest"` | `newest` หรือ `oldest` |

**ตัวอย่าง:**

```json
{
  "scope": "myproject",
  "doc_type": "learning",
  "limit": 10,
  "offset": 0,
  "order": "newest"
}
```

---

### 4. `synapse_scope`

แสดง scope ทั้งหมดพร้อมจำนวนเอกสาร — ไม่มีพารามิเตอร์

**ผลลัพธ์:**

```json
[
  {"name": "myproject", "description": null, "doc_count": 42, "oracle_name": "caretaker"},
  {"name": "shared", "description": null, "doc_count": 15, "oracle_name": null}
]
```

---

### 5. `synapse_stats`

แสดงสถิติคลังความรู้ — ไม่มีพารามิเตอร์

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

### 6. `synapse_search_cross`

ค้นหาข้ามหลาย scope รวมผลลัพธ์ตามคะแนนสูงสุด

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `query` | string | **ใช่** | - | คำค้นหา |
| `scopes` | array[string] | **ใช่** | - | list ของ scope names |
| `limit` | integer | ไม่ | `10` | จำนวนผลลัพธ์สูงสุด |
| `mode` | string | ไม่ | `"hybrid"` | โหมดค้นหา |

**ตัวอย่าง:**

```json
{
  "query": "deployment patterns",
  "scopes": ["team-alpha", "team-beta", "shared"],
  "limit": 10,
  "mode": "hybrid"
}
```

---

## Ingest Tools

### 7. `synapse_push`

เพิ่มความรู้เข้าคลัง — auto-detect oracle metadata จาก `source_file` path

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `title` | string | **ใช่** | - | ชื่อเอกสาร |
| `content` | string | **ใช่** | - | เนื้อหา (markdown) |
| `scope` | string | ไม่ | `"shared"` | scope/namespace |
| `doc_type` | string | ไม่ | `"learning"` | ประเภทเอกสาร |
| `source_file` | string | ไม่ | - | path ของไฟล์ต้นฉบับ |
| `source_project` | string | ไม่ | - | โปรเจกต์ต้นทาง |
| `concepts` | array[string] | ไม่ | - | concepts list |
| `tags` | array[string] | ไม่ | - | tags list |
| `oracle_name` | string | ไม่ | - | ชื่อ oracle |
| `brain_path` | string | ไม่ | - | brain path (k/p relative) |
| `brain_tier` | string | ไม่ | - | brain tier (intrinsic/extrinsic) |

**doc_type ที่รองรับ:** `learning`, `pattern`, `retro`, `reference`, `handoff`, `protocol`, `wisdom`, `instinct`, `log`, `note`

**ตัวอย่าง:**

```json
{
  "title": "Python Error Handling",
  "content": "Always catch specific exceptions. Never use bare except clauses.",
  "scope": "myproject",
  "doc_type": "learning",
  "concepts": ["error-handling", "python"],
  "tags": ["best-practices"],
  "source_project": "myapp"
}
```

**ผลลัพธ์:**

```json
{
  "id": "uuid-here",
  "scope": "myproject",
  "status": "indexed"
}
```

หากเนื้อหาซ้ำ (`content_hash` + scope เดียวกัน):

```json
{
  "id": "existing-uuid",
  "scope": "myproject",
  "status": "duplicate"
}
```

---

## Version Tools

### 8. `synapse_supersede`

อัปเดตเอกสารด้วย supersession — เอกสารเก่าไม่ถูกลบ ถูก mark ว่า `superseded_by`

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `old_id` | string | **ใช่** | - | UUID ของเอกสารเก่า |
| `new_content` | string | **ใช่** | - | เนื้อหาใหม่ |
| `new_title` | string | ไม่ | ใช้ title เดิม | ชื่อใหม่ |
| `reason` | string | ไม่ | `"updated"` | เหตุผลของการ supersede |

**ตัวอย่าง:**

```json
{
  "old_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "new_content": "Updated: always catch specific exceptions and log context.",
  "reason": "added logging advice"
}
```

**ผลลัพธ์:**

```json
{
  "id": "new-uuid-here",
  "superseded": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "superseded"
}
```

---

## Relation Tools

### 9. `synapse_trace`

สร้าง trace link ระหว่างเอกสาร 2 ฉบับ เพื่อบันทึกความสัมพันธ์

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `source_id` | string | **ใช่** | - | UUID เอกสารต้นทาง |
| `target_id` | string | **ใช่** | - | UUID เอกสารปลายทาง |
| `relation` | string | **ใช่** | - | ประเภทความสัมพันธ์ |
| `confidence` | number | ไม่ | `1.0` | คะแนนความมั่นใจ (0-1) |

**relation ที่รองรับ:** `derived_from`, `refines`, `contradicts`, `extends`

**ตัวอย่าง:**

```json
{
  "source_id": "doc-a-uuid",
  "target_id": "doc-b-uuid",
  "relation": "refines",
  "confidence": 0.85
}
```

---

### 10. `synapse_trace_chain`

ตามลูกโซ่ trace จากเอกสารหนึ่ง คืนเอกสารที่เชื่อมโยงทั้งหมด

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `doc_id` | string | **ใช่** | - | UUID เอกสารเริ่มต้น |
| `direction` | string | ไม่ | `"both"` | `both`, `upstream`, `downstream` |
| `max_depth` | integer | ไม่ | `5` | ความลึกสูงสุด |
| `relation` | string | ไม่ | - | กรองเฉพาะ relation type |

**ตัวอย่าง:**

```json
{
  "doc_id": "a1b2c3d4-...",
  "direction": "upstream",
  "max_depth": 3
}
```

**ผลลัพธ์:**

```json
[
  {
    "source_id": "uuid-source",
    "target_id": "uuid-target",
    "relation": "derived_from",
    "confidence": 1.0
  },
  {
    "source_id": "uuid-other",
    "target_id": "uuid-source",
    "relation": "refines",
    "confidence": 0.9
  }
]
```

---

## Metadata Tools

### 11. `synapse_concepts`

แสดงหรือค้นหา concepts ทั้งหมดในคลัง

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `search` | string | ไม่ | - | ค้นหา concept ตามชื่อ |
| `limit` | integer | ไม่ | `50` | จำนวนผลลัพธ์สูงสุด |

**ตัวอย่าง:**

```json
{
  "search": "error",
  "limit": 20
}
```

**ผลลัพธ์:**

```json
[
  {"name": "error-handling", "description": null, "doc_count": 5},
  {"name": "error-recovery", "description": null, "doc_count": 2}
]
```

---

## Registry Tools

### 12. `synapse_register`

ลงทะเบียนโปรเจกต์กับคลังความรู้ เพื่อเปิดใช้ cross-project search

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `project_path` | string | **ใช่** | - | path ของโปรเจกต์ |
| `scope` | string | ไม่ | auto-detect | ชื่อ scope |

**ตัวอย่าง:**

```json
{
  "project_path": "/Users/user/code/myproject",
  "scope": "myproject"
}
```

**ผลลัพธ์:**

```json
{
  "scope": "myproject",
  "project_path": "/Users/user/code/myproject",
  "status": "registered"
}
```

---

### 13. `synapse_unregister`

ยกเลิกลงทะเบียนโปรเจกต์ออกจากคลังความรู้

| พารามิเตอร์ | ประเภท | จำเป็น | Default | คำอธิบาย |
|-------------|--------|--------|---------|----------|
| `scope` | string | **ใช่** | - | ชื่อ scope ที่จะยกเลิก |

**ตัวอย่าง:**

```json
{
  "scope": "myproject"
}
```

**ผลลัพธ์:**

```json
{
  "scope": "myproject",
  "status": "unregistered"
}
```

---

### 14. `synapse_projects`

แสดงโปรเจกต์ที่ลงทะเบียนทั้งหมด — ไม่มีพารามิเตอร์

**ผลลัพธ์:**

```json
[
  {
    "scope": "myproject",
    "project_path": "/Users/user/code/myproject",
    "registered_at": "2025-01-15 10:30:00"
  },
  {
    "scope": "shared",
    "project_path": "/Users/user/code/shared-knowledge",
    "registered_at": "2025-01-16 14:00:00"
  }
]
```

---

## ตารางเปรียบเทียบ MCP vs CLI

| เครื่องมือ MCP | คำสั่ง CLI | ความแตกต่าง |
|----------------|-----------|-------------|
| `synapse_search` | `synapse search` | MCP ใส่ concepts เป็น array, CLI ใส่เป็น comma-separated |
| `synapse_push` | `synapse push` | MCP ไม่รองรับ `--file`, ต้องส่ง content โดยตรง |
| `synapse_supersede` | `synapse supersede` | เหมือนกัน |
| `synapse_trace` | `synapse trace` | เหมือนกัน |
| `synapse_trace_chain` | `synapse trace-chain` | MCP เพิ่ม `relation` filter |
| `synapse_concepts` | `synapse concepts` | เหมือนกัน |
| `synapse_get` | `synapse get` | เหมือนกัน |
| `synapse_scope` | `synapse scope` | เหมือนกัน |
| `synapse_stats` | `synapse stats` | เหมือนกัน |
| `synapse_list` | `synapse list` | เหมือนกัน |
| `synapse_register` | `synapse register` | เหมือนกัน |
| `synapse_unregister` | `synapse unregister` | เหมือนกัน |
| `synapse_projects` | `synapse projects` | เหมือนกัน |
| `synapse_search_cross` | `synapse search-cross` | MCP ใส่ scopes เป็น array, CLI ใส่เป็น comma-separated |

### คำสั่ง CLI ที่ไม่มีใน MCP

| คำสั่ง CLI | เหตุผล |
|-----------|--------|
| `synapse serve` | Service lifecycle — ไม่ใช่ knowledge operation |
| `synapse mcp` | Service lifecycle |
| `synapse init` | ใช้ครั้งเดียวตอนตั้งค่า — ไม่ใช่ตอน agent ทำงาน |
| `synapse reconcile` | บำรุงรักษา — admin เป็นผู้รัน |
| `synapse stop` | Daemon lifecycle |
| `synapse status` | System status |
| `synapse scan` | Scheduled maintenance |