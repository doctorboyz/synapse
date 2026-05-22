# 02 — CLI Command Reference

> คำสั่ง CLI ทั้ง 21 คำสั่งสำหรับจัดการคลังความรู้ Synapse

คำสั่งทั้งหมดรันผ่าน `synapse <command>` ผลลัพธ์ออกเป็น JSON format

---

## สารบัญคำสั่ง

| # | คำสั่ง | หมวด | คำอธิบาย |
|---|--------|------|----------|
| 1 | `serve` | Service | เริ่ม HTTP API server |
| 2 | `mcp` | Service | เริ่ม MCP stdio server |
| 3 | `push` | Ingest | เพิ่มข้อมูลเข้าคลัง (ข้อความหรือไฟล์) |
| 4 | `search` | Retrieve | ค้นหาความรู้แบบ hybrid |
| 5 | `get` | Retrieve | ดึงเอกสารตาม ID |
| 6 | `list` | Retrieve | แสดงรายการเอกสาร |
| 7 | `scope` | Retrieve | แสดง scope ทั้งหมด |
| 8 | `stats` | Retrieve | สถิติคลังความรู้ |
| 9 | `supersede` | Version | อัปเดตเอกสารแบบ supersession |
| 10 | `trace` | Relation | สร้าง trace link ระหว่างเอกสาร |
| 11 | `trace-chain` | Relation | ตามลูกโซ่ trace |
| 12 | `concepts` | Metadata | แสดง/ค้นหา concepts |
| 13 | `init` | Ingest | สแกนไฟล์ทั้งหมดครั้งแรก |
| 14 | `reconcile` | Maintenance | กระทัดข้อมูลซ้ำ + ตรวจความขัดแย้ง |
| 15 | `register` | Registry | ลงทะเบียนโปรเจกต์ |
| 16 | `unregister` | Registry | ยกเลิกลงทะเบียนโปรเจกต์ |
| 17 | `projects` | Registry | แสดงโปรเจกต์ที่ลงทะเบียน |
| 18 | `search-cross` | Retrieve | ค้นหาข้ามหลาย scope |
| 19 | `stop` | Daemon | หยุด daemon |
| 20 | `status` | Daemon | แสดงสถานะระบบ |
| 21 | `scan` | Maintenance | สแกนโปรเจกต์หาไฟล์ใหม่ |

---

## Service Commands

### `synapse serve`

เริ่ม HTTP API server แบบ long-running

```bash
synapse serve
```

ค่า default: host `0.0.0.0`, port `8420` (ปรับได้ผ่าน env `SYNAPSE_HOST`, `SYNAPSE_PORT`)

```bash
# ปรับ port ผ่าน env
SYNAPSE_PORT=9000 synapse serve
```

### `synapse mcp`

เริ่ม MCP stdio server สำหรับ AI agent เช่น Claude Code

```bash
synapse mcp
```

คำสั่งนี้เริ่ม MCP server ผ่าน stdio transport ไม่มี HTTP endpoint ใช้สำหรับ agent-first access

---

## Ingest Commands

### `synapse push`

เพิ่มความรู้เข้าคลัง — รองรับทั้งข้อความโดยตรงและไฟล์

**Push ข้อความ (text):**

```bash
synapse push \
  --title "Error Handling Best Practices" \
  --content "Always catch specific exceptions. Never use bare except." \
  --scope shared \
  --doc-type learning \
  --concepts "error-handling,python" \
  --tags "best-practices" \
  --source-project myapp
```

**Push ไฟล์ (file):**

```bash
synapse push --file ./notes/architecture.md --scope myproject
```

เมื่อใช้ `--file` ระบบจะ auto-detect oracle metadata จาก path ของไฟล์

**พารามิเตอร์ทั้งหมด:**

| พารามิเตอร์ | จำเป็น | Default | คำอธิบาย |
|-------------|--------|---------|----------|
| `--title` | ใช่ (ถ้าไม่ใช้ --file) | - | ชื่อเอกสาร |
| `--content` | ใช่ (ถ้าไม่ใช้ --file) | - | เนื้อหาเอกสาร |
| `--file, -f` | ไม่ | - | path ของไฟล์ที่จะ ingest |
| `--scope` | ไม่ | `shared` | scope/namespace |
| `--doc-type` | ไม่ | `learning` | ประเภทเอกสาร |
| `--source-file` | ไม่ | - | path ของไฟล์ต้นฉบับ |
| `--source-project` | ไม่ | - | โปรเจกต์ต้นทาง |
| `--concepts` | ไม่ | - | concepts คั่นด้วย comma |
| `--tags` | ไม่ | - | tags คั่นด้วย comma |
| `--oracle-name` | ไม่ | - | ชื่อ oracle |
| `--brain-path` | ไม่ | - | brain path (k/p relative) |
| `--brain-tier` | ไม่ | - | brain tier (intrinsic/extrinsic) |

**doc_type ที่รองรับ:**

`learning`, `pattern`, `retro`, `reference`, `handoff`, `protocol`, `wisdom`, `instinct`, `log`, `note`

**ตัวอย่างผลลัพธ์:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "scope": "shared",
  "status": "indexed"
}
```

หากเป็นข้อมูลซ้ำ:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "scope": "shared",
  "status": "duplicate"
}
```

### `synapse init`

สแกนไฟล์ทั้งหมดในโปรเจกต์และสร้างฐานข้อมูลครั้งแรก

```bash
# สแกนไดเรกทอรีปัจจุบัน
synapse init

# สแกน path ที่ระบุ
synapse init --path /path/to/project

# ระบุ scope
synapse init --path /path/to/project --scope myproject

# ทดลองดูผลโดยไม่เขียนจริง
synapse init --path /path/to/project --dry-run
```

| พารามิเตอร์ | Default | คำอธิบาย |
|-------------|---------|----------|
| `--path` | `.` (ไดเรกทอรีปัจจุบัน) | ไดเรกทอรีที่จะสแกน |
| `--scope` | auto-detect จาก path | scope สำหรับเอกสาร |
| `--dry-run` | `false` | แสดงผลโดยไม่เขียนลงฐานข้อมูล |

ระบบจะข้ามไดเรกทอรี: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `env`, `.tox`, `.mypy_cache`, `.pytest_cache` และไดเรกทอรีที่ขึ้นต้นด้วย `.`

รองรับไฟล์: `.md`, `.txt`, `.rst`, `.pdf`, `.docx`

สำหรับเนื้อหาที่ยาวกว่า 2000 ตัวอักษร ระบบจะใช้ LLM (qwen2.5:7b) สรุปอัตโนมัติ

**ตัวอย่างผลลัพธ์ (dry-run):**

```json
{
  "total_files": 42,
  "indexed": 0,
  "duplicates": 0,
  "errors": 0,
  "llm_summarized": 0,
  "files": [
    {
      "path": "README.md",
      "status": "dry_run",
      "scope": "myproject",
      "doc_type": "note",
      "title": "Readme",
      "content_length": 1234
    }
  ]
}
```

---

## Retrieve Commands

### `synapse search`

ค้นหาความรู้ด้วย hybrid search (dense + FTS)

```bash
# ค้นหาพื้นฐาน
synapse search "error handling patterns"

# กรองตาม scope
synapse search "error handling" --scope myproject

# ใช้ FTS เท่านั้น (ไม่ใช้ vector)
synapse search "error handling" --mode fts

# กรองตาม doc_type
synapse search "api design" --doc-type pattern

# กรองตาม oracle
synapse search "memory" --oracle caretaker

# จำกัดจำนวนผล
synapse search "test" --limit 5
```

| พารามิเตอร์ | จำเป็น | Default | คำอธิบาย |
|-------------|--------|---------|----------|
| `query` | ใช่ | - | คำค้นหา (positional) |
| `--scope` | ไม่ | - | กรองตาม scope |
| `--doc-type` | ไม่ | - | กรองตาม doc_type |
| `--oracle` | ไม่ | - | กรองตาม oracle name |
| `--source-project` | ไม่ | - | กรองตาม source project |
| `--concepts` | ไม่ | - | กรอง concepts คั่นด้วย comma |
| `--limit` | ไม่ | `10` | จำนวนผลลัพธ์สูงสุด |
| `--mode` | ไม่ | `hybrid` | โหมดค้นหา: `hybrid`, `dense`, `fts` |

**โหมดค้นหา:**

| โหมด | การทำงาน |
|------|----------|
| `hybrid` | Qdrant dense (60%) + PostgreSQL FTS (40%) รวมด้วย RRF |
| `dense` | Qdrant vector search เท่านั้น (ต้องมี Qdrant + Ollama) |
| `fts` | PostgreSQL tsvector full-text search เท่านั้น |

### `synapse get`

ดึงเอกสารตาม UUID

```bash
synapse get a1b2c3d4-e5f6-7890-abcd-ef1234567890

# ไม่รวม supersession chain
synapse get a1b2c3d4-e5f6-7890-abcd-ef1234567890 --no-chain
```

| พารามิเตอร์ | จำเป็น | Default | คำอธิบาย |
|-------------|--------|---------|----------|
| `id` | ใช่ | - | UUID ของเอกสาร (positional) |
| `--no-chain` | ไม่ | `false` | ไม่รวม supersession chain |

### `synapse list`

แสดงรายการเอกสารพร้อมตัวกรอง

```bash
# แสดง 20 รายการล่าสุด
synapse list

# กรองตาม scope
synapse list --scope myproject

# กรองตาม doc_type พร้อม pagination
synapse list --doc-type learning --limit 50 --offset 100

# เรียงจากเก่าสุด
synapse list --order oldest
```

| พารามิเตอร์ | Default | คำอธิบาย |
|-------------|---------|----------|
| `--scope` | - | กรองตาม scope |
| `--doc-type` | - | กรองตาม doc_type |
| `--oracle` | - | กรองตาม oracle name |
| `--limit` | `20` | จำนวนผลลัพธ์สูงสุด |
| `--offset` | `0` | offset สำหรับ pagination |
| `--order` | `newest` | ลำดับ: `newest` หรือ `oldest` |

### `synapse scope`

แสดง scope ทั้งหมดพร้อมจำนวนเอกสาร

```bash
synapse scope
```

**ตัวอย่างผลลัพธ์:**

```json
[
  {"name": "myproject", "description": null, "doc_count": 42, "oracle_name": "caretaker"},
  {"name": "shared", "description": null, "doc_count": 15, "oracle_name": null}
]
```

### `synapse stats`

แสดงสถิติคลังความรู้

```bash
synapse stats
```

**ตัวอย่างผลลัพธ์:**

```json
{
  "total_documents": 57,
  "by_type": {
    "learning": 30,
    "pattern": 12,
    "retro": 8,
    "note": 7
  },
  "by_scope": {
    "myproject": 42,
    "shared": 15
  },
  "by_oracle": {
    "caretaker": 25,
    "coder": 17
  }
}
```

### `synapse search-cross`

ค้นหาข้ามหลาย scope รวมผลลัพธ์ตามคะแนนสูงสุด

```bash
synapse search-cross "error handling" --scopes project-a,project-b,shared

# จำกัดผลลัพธ์
synapse search-cross "api design" --scopes team-a,team-b --limit 5

# เลือกโหมดค้นหา
synapse search-cross "testing" --scopes myproject,shared --mode fts
```

| พารามิเตอร์ | จำเป็น | Default | คำอธิบาย |
|-------------|--------|---------|----------|
| `query` | ใช่ | - | คำค้นหา (positional) |
| `--scopes` | ใช่ | - | scope names คั่นด้วย comma |
| `--limit` | ไม่ | `10` | จำนวนผลลัพธ์สูงสุด |
| `--mode` | ไม่ | `hybrid` | โหมดค้นหา |

---

## Version Control Commands

### `synapse supersede`

อัปเดตเอกสารด้วย supersession — เอกสารเก่าไม่ถูกลบ แต่ถูก mark ว่า superseded

```bash
synapse supersede a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --new-content "Updated content with new information"

# พร้อมเปลี่ยนชื่อ
synapse supersede a1b2c3d4-... \
  --new-content "Updated content" \
  --new-title "New Title"

# ระบุเหตุผล
synapse supersede a1b2c3d4-... \
  --new-content "Fixed incorrect info" \
  --reason "bug_fix"
```

| พารามิเตอร์ | จำเป็น | Default | คำอธิบาย |
|-------------|--------|---------|----------|
| `old_id` | ใช่ | - | UUID ของเอกสารเก่า (positional) |
| `--new-content` | ใช่ | - | เนื้อหาใหม่ |
| `--new-title` | ไม่ | ใช้ title เดิม | ชื่อใหม่ |
| `--reason` | ไม่ | `updated` | เหตุผลของการ supersede |

---

## Relation Commands

### `synapse trace`

สร้าง trace link ระหว่างเอกสาร 2 ฉบับ

```bash
synapse trace \
  --source a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --target b2c3d4e5-f6a7-8901-bcde-f12345678901 \
  --relation derived_from

# พร้อม confidence score
synapse trace \
  --source a1b2c3d4-... \
  --target b2c3d4e5-... \
  --relation contradicts \
  --confidence 0.8
```

| พารามิเตอร์ | จำเป็น | Default | คำอธิบาย |
|-------------|--------|---------|----------|
| `--source` | ใช่ | - | UUID เอกสารต้นทาง |
| `--target` | ใช่ | - | UUID เอกสารปลายทาง |
| `--relation` | ใช่ | - | ประเภทความสัมพันธ์ |
| `--confidence` | ไม่ | `1.0` | คะแนนความมั่นใจ (0-1) |

**relation ที่รองรับ:**

| Relation | ความหมาย |
|----------|----------|
| `derived_from` | เอกสาร A มาจากเอกสาร B |
| `refines` | เอกสาร A ปรับปรุงเอกสาร B |
| `contradicts` | เอกสาร A ขัดแย้งกับเอกสาร B |
| `extends` | เอกสาร A ขยายเอกสาร B |

### `synapse trace-chain`

ตามลูกโซ่ trace จากเอกสารหนึ่ง

```bash
# ตามทุกทิศทาง
synapse trace-chain a1b2c3d4-e5f6-7890-abcd-ef1234567890

# ตาม upstream เท่านั้น (ย้อนกลับ)
synapse trace-chain a1b2c3d4-... --direction upstream

# จำกัดความลึก
synapse trace-chain a1b2c3d4-... --max-depth 3
```

| พารามิเตอร์ | Default | คำอธิบาย |
|-------------|---------|----------|
| `doc_id` | - | UUID เอกสารเริ่มต้น (positional, จำเป็น) |
| `--direction` | `both` | ทิศทาง: `both`, `upstream`, `downstream` |
| `--max-depth` | `5` | ความลึกสูงสุดของ chain |

---

## Metadata Commands

### `synapse concepts`

แสดงหรือค้นหา concepts ทั้งหมด

```bash
# แสดง concepts ทั้งหมด (เรียงตามจำนวนเอกสาร)
synapse concepts

# ค้นหา concept
synapse concepts --search "error"

# จำกัดจำนวน
synapse concepts --limit 20
```

| พารามิเตอร์ | Default | คำอธิบาย |
|-------------|---------|----------|
| `--search` | - | ค้นหา concept ตามชื่อ (ILIKE) |
| `--limit` | `50` | จำนวนผลลัพธ์สูงสุด |

---

## Maintenance Commands

### `synapse reconcile`

รันบำรุงรักษาคลังความรู้: กระทัดข้อมูลซ้ำ (defrag) + ตรวจจับความขัดแย้ง (detox)

```bash
# รันทั้ง defrag + detox
synapse reconcile

# จำกัดเฉพาะ scope
synapse reconcile --scope myproject

# ทดลองดูผลโดยไม่แก้ไขจริง
synapse reconcile --dry-run
```

| พารามิเตอร์ | Default | คำอธิบาย |
|-------------|---------|----------|
| `--scope` | - | จำกัดเฉพาะ scope ที่ระบุ |
| `--dry-run` | `false` | แสดงผลโดยไม่แก้ไขข้อมูล |

**Defrag** ค้นหาเอกสารที่ซ้ำกัน (title + scope เดียวกัน) และ supersede ตัวที่เก่ากว่า

**Detox** วิเคราะห์คู่เอกสารใน scope + doc_type เดียวกัน ด้วย LLM เพื่อตรวจจับความขัดแย้ง และแก้ไขโดย supersede ด้วยเนื้อหาที่ merge แล้ว

**ตัวอย่างผลลัพธ์:**

```json
{
  "defrag": {
    "duplicates_found": 3,
    "compacted": 3,
    "errors": 0,
    "groups": [
      {
        "title": "Error Handling",
        "scope": "shared",
        "count": 2,
        "keep": "uuid-newest",
        "supersede": ["uuid-older"],
        "action": "superseded"
      }
    ]
  },
  "detox": {
    "conflicts_found": 1,
    "conflicts": [],
    "resolutions": [
      {
        "old_id": "uuid-old",
        "new_id": "uuid-new",
        "reason": "contradiction: different error handling advice"
      }
    ],
    "errors": 0
  },
  "scope": "all",
  "dry_run": false
}
```

### `synapse scan`

สแกนโปรเจกต์ที่ลงทะเบียนทั้งหมดหาไฟล์ใหม่

```bash
synapse scan
```

ระบบจะตรวจสอบ `registered_projects` และสแกน path ของแต่ละโปรเจกต์ ไฟล์ใหม่จะถูก ingest อัตโนมัติ

---

## Registry Commands

### `synapse register`

ลงทะเบียนโปรเจกต์กับคลังความรู้

```bash
# ลงทะเบียน path ปัจจุบัน (auto-detect scope)
synapse register

# ระบุ path
synapse register --path /path/to/project

# ระบุ scope เอง
synapse register --path /path/to/project --scope my-custom-scope
```

| พารามิเตอร์ | Default | คำอธิบาย |
|-------------|---------|----------|
| `--path` | `.` | path ของโปรเจกต์ |
| `--scope` | auto-detect จาก path | ชื่อ scope |

Scope name ต้องเป็น lowercase, alphanumeric, ขีดกลางเท่านั้น, 1-64 ตัวอักษร

### `synapse unregister`

ยกเลิกลงทะเบียนโปรเจกต์

```bash
synapse unregister myproject
```

### `synapse projects`

แสดงโปรเจกต์ที่ลงทะเบียนทั้งหมด

```bash
synapse projects
```

**ตัวอย่างผลลัพธ์:**

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

## Daemon Commands

### `synapse stop`

หยุด daemon ที่กำลังทำงาน

```bash
synapse stop

# ระบุ PID file
synapse stop --pid-file /custom/path/synapse.pid
```

ระบบจะส่ง SIGTERM รอ 15 วินาที หากยังไม่หยุดจะส่ง SIGKILL

### `synapse status`

แสดงสถานะระบบ รวม: daemon status, local-only violations, สถิติฐานข้อมูล

```bash
synapse status

# ระบุ PID file
synapse status --pid-file /custom/path/synapse.pid
```

**ตัวอย่างผลลัพธ์:**

```json
{
  "running": false,
  "pid": null,
  "pid_file": "/home/user/.synapse/synapse.pid",
  "local_only_violations": [],
  "database": {
    "total_documents": 57,
    "by_type": {"learning": 30},
    "by_scope": {"shared": 15},
    "by_oracle": {"caretaker": 25}
  },
  "scopes": 3
}
```