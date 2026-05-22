# 08 — Ingest Pipeline

> ระบบนำเข้าข้อมูลของ Synapse: push pipeline, init scan, hook handler, oracle path mapping

---

## ภาพรวม

ระบบนำเข้าข้อมูล (Ingest) รับข้อมูลจาก 4 ช่องทาง แล้วเขียนลงทั้ง PostgreSQL และ Qdrant:

```
ช่องทางนำเข้า:
1. CLI/API (push_text)     → ข้อความโดยตรง
2. CLI/API (push_file)     → อ่านไฟล์ → push_text
3. Init Scan               → สแกนโฟลเดอร์ → อ่านไฟล์ทีละไฟล์ → push_text
4. Hook Handler            → PostToolUse auto-ingest → push_text

Push Pipeline (push_text):
  1. validate doc_type
  2. pg.add() → dedup check → INSERT
  3. embed content (optional)
  4. qdrant.upsert() (if available)
```

---

## Push Pipeline

**ไฟล์:** `src/ingest/push.py`

คลาส `Push` เป็นจุดเข้าหลักสำหรับนำเข้าข้อมูล ประสานงานเขียนลงทั้ง PostgreSQL และ Qdrant

### Constructor

```python
Push(pg: PgStore, qdrant: QdrantStore | None = None, embedder: OllamaEmbedder | None = None)
```

### push_text()

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

**ขั้นตอนการทำงาน:**

1. ตรวจสอบ `doc_type` ด้วย `validate_doc_type()` — โยน `ValueError` หากไม่ถูกต้อง
2. เรียก `pg.add()` → หาก `status == "duplicate"` คืนทันทีโดยไม่ embed
3. หาก `embed=True` และ qdrant + embedder พร้อมใช้:
   - embed เนื้อหาด้วย `embedder.embed(content)`
   - เรียก `qdrant.upsert()` เพื่อเก็บเวกเตอร์
   - หาก embed ล้มเหลว → ตั้ง `status = "indexed_pg_only"`
4. คืนผลลัพธ์: `{id, scope, status}`

**source_type ที่รองรับ:**

| source_type | แหล่งที่มา |
|-------------|----------|
| `manual` | CLI/API push โดยตรง |
| `api` | HTTP API push |
| `webhook` | Webhook push |
| `hook` | PostToolUse hook auto-ingest |
| `init_scan` | Init scan ครั้งแรก |

### push_file()

```python
async def push_file(
    file_path: str,
    scope: str | None = None,
    doc_type: str | None = None,
    embed: bool = True
) -> dict
```

**ขั้นตอนการทำงาน:**

1. อ่านไฟล์จาก `file_path` ด้วย `Path.read_text()`
2. ใช้ `Path.stem` เป็น title
3. หากไม่ระบุ scope/doc_type → เรียก `extract_metadata()` เพื่อดึงจาก path
4. ส่งต่อไป `push_text()` ด้วย `source_type="manual"`

---

## Oracle Paths

**ไฟล์:** `src/ingest/oracle_paths.py`

แมป path จากโครงสร้าง kappa/psi ของ Oracle brain ไปเป็น metadata อัตโนมัติ

### ORACLE_PATH_RULES — 10 กฎการแมป

| Path Pattern | doc_type | brain_tier |
|-------------|----------|-----------|
| `p/memory/learnings/` | `learning` | `extrinsic` |
| `p/memory/retrospectives/` | `retro` | `extrinsic` |
| `p/outbox/` | `handoff` | `extrinsic` |
| `k/extrinsic/wisdom/knowledge/` | `wisdom` | `extrinsic` |
| `k/extrinsic/wisdom/reference/` | `reference` | `extrinsic` |
| `k/extrinsic/experience/learn/` | `learning` | `extrinsic` |
| `k/extrinsic/experience/work/logs/` | `log` | `extrinsic` |
| `k/intrinsic/instinct/` | `instinct` | `intrinsic` |
| `k/intrinsic/identity/` | `instinct` | `intrinsic` |
| `k/intrinsic/inherit/` | `instinct` | `intrinsic` |

### VALID_DOC_TYPES

```python
{"learning", "pattern", "retro", "reference", "handoff", "protocol", "wisdom", "instinct", "log", "note"}
```

### VALID_TRACE_RELATIONS

```python
{"derived_from", "refines", "contradicts", "extends"}
```

### ฟังก์ชัน

| ฟังก์ชัน | ลายเซ็น | คำอธิบาย |
|----------|---------|----------|
| `extract_oracle_name()` | `(repo_path: str) -> str` | ดึงชื่อ oracle จาก basename ตัด `-oracle` ออก |
| `extract_metadata()` | `(file_path: str, repo_root: str) -> dict` | คำนวณ relative path ตรวจกับ `ORACLE_PATH_RULES` คืน `{oracle_name, brain_path, brain_tier, doc_type, scope}` ค่าเริ่มต้น: `doc_type="note"`, `brain_tier="extrinsic"`, `scope=oracle_name` |
| `validate_doc_type()` | `(doc_type: str) -> str` | โยน `ValueError` หาก doc_type ไม่อยู่ใน `VALID_DOC_TYPES` |
| `validate_trace_relation()` | `(relation: str) -> str` | โยน `ValueError` หาก relation ไม่อยู่ใน `VALID_TRACE_RELATIONS` |

### ตัวอย่างการ extract_metadata

```python
# Path ตรงกับ rule
extract_metadata("/home/user/caretaker-oracle/p/memory/learnings/lesson.md",
                "/home/user/caretaker-oracle")
# → {
#     "oracle_name": "caretaker",
#     "brain_path": "p/memory/learnings/lesson.md",
#     "brain_tier": "extrinsic",
#     "doc_type": "learning",
#     "scope": "caretaker"
#   }

# Path ไม่ตรงกับ rule (ใช้ default)
extract_metadata("/home/user/caretaker-oracle/notes/random.md",
                "/home/user/caretaker-oracle")
# → {
#     "oracle_name": "caretaker",
#     "brain_path": "notes/random.md",
#     "brain_tier": "extrinsic",
#     "doc_type": "note",
#     "scope": "caretaker"
#   }
```

---

## Hook Handler

**ไฟล์:** `src/ingest/hook_handler.py`

รับข้อมูลอัตโนมัติจาก Claude Code PostToolUse hooks เมื่อมีการเขียน/แก้ไขไฟล์ในโครงสร้าง k หรือ p

### การตั้งค่า Hook

เพิ่มใน `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "command": "python -m src.ingest.hook_handler \"$FILE_PATH\""
      }
    ]
  }
}
```

### ฟังก์ชัน

| ฟังก์ชัน | คำอธิบาย |
|----------|----------|
| `is_oracle_brain_path(file_path)` | ตรวจว่า path อยู่ในโครงสร้าง k หรือ p หรือไม่ |
| `find_oracle_root(file_path)` | ตามหา directory ที่มี `CLAUDE.md` (oracle root) |
| `async ingest_file(file_path)` | นำเข้าไฟล์เข้า synapse โดยอัตโนมัติ |
| `main()` | รับ file path จาก argv หรือ stdin JSON |

### ขั้นตอนการทำงานของ ingest_file()

1. ตรวจสอบว่าไฟล์มีอยู่จริงและเป็น oracle brain path
2. หา oracle root (directory ที่มี `CLAUDE.md`) ถ้าไม่พบ → ข้าม
3. ดึง metadata ด้วย `extract_metadata()`
4. สร้าง `PgStore` แยกต่างหาก (ไม่ใช้ connection pool ร่วมกับ server)
5. พยายามสร้าง `QdrantStore` และ `OllamaEmbedder`
   - หาก Qdrant ล้มเหลว → ใส่เฉพาะ PostgreSQL
   - หาก Ollama ล้มเหลว → ใส่เฉพาะ PostgreSQL (ไม่ embed)
6. เรียก `push.push_text()` ด้วย `source_type="hook"`
7. ปิดการเชื่อมต่อใน `finally`

**ข้อสังเกต:** Hook handler สร้าง database connections ของตัวเองแยกจาก server process เพราะทำงานใน process แยก (CLI subprocess)

---

## Init Scan

**ไฟล์:** `src/ingest/init_scan.py`

สแกนไฟล์ทั้งหมดในโปรเจกต์และนำเข้าเข้า vault ครั้งแรก

### การเรียกใช้

```bash
# สแกนโปรเจกต์ปัจจุบัน
synapse init

# สแกน path ที่ระบุ
synapse init --path /path/to/project

# ทดลองดูผล (dry-run)
synapse init --path /path/to/project --dry-run
```

### ฟังก์ชันหลัก

```python
async def init_scan(
    path: str,
    scope: str | None = None,
    dry_run: bool = False,
) -> dict
```

### ขั้นตอนการทำงาน

1. ตรวจสอบ path ว่าเป็น directory ที่มีอยู่จริง
2. เรียก `scan_files()` เพื่อรวบรวมไฟล์ทั้งหมด
3. สร้าง `PgStore`, พยายามสร้าง `QdrantStore` และ `OllamaEmbedder`
4. สำหรับแต่ละไฟล์:
   - อ่านเนื้อหาด้วย `read_file_content()`
   - ดึง metadata ด้วย `extract_metadata()`
   - หากเนื้อหายาวกว่า 2000 ตัวอักษร และ Ollama พร้อมใช้ → สรุปด้วย LLM (qwen2.5:7b)
   - เรียก `push.push_text()` ด้วย `source_type="init_scan"`
5. คืนผลลัพธ์รวม

### ประเภทไฟล์ที่รองรับ

```python
SCAN_EXTENSIONS = {".md", ".txt", ".rst", ".pdf", ".docx"}
```

- `.md`, `.txt`, `.rst` — อ่านด้วย `Path.read_text(encoding="utf-8")`
- `.pdf` — อ่านด้วย `pypdf.PdfReader` (ต้องติดตั้ง `synapse[init]`)
- `.docx` — อ่านด้วย `python-docx` (ต้องติดตั้ง `synapse[init]`)

### ไดเรกทอรีที่ข้าม

```python
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache"}
```

ไดเรกทอรีที่ขึ้นต้นด้วย `.` จะถูกข้ามด้วย

### ผลลัพธ์

```json
{
  "total_files": 42,
  "indexed": 35,
  "duplicates": 5,
  "errors": 2,
  "llm_summarized": 10,
  "files": [
    {
      "path": "README.md",
      "status": "indexed",
      "id": "uuid-here",
      "scope": "myproject"
    }
  ]
}
```

### LLM Summarization

สำหรับไฟล์ที่เนื้อหายาวกว่า 2000 ตัวอักษร ระบบจะใช้ qwen2.5:7b สรุปเนื้อหาก่อน ingest:

```python
async def summarize_with_llm(content: str, title: str, embedder: OllamaEmbedder) -> str | None:
    prompt = (
        f"Summarize the following document concisely, preserving key information. "
        f"Keep the summary under 500 words.\n\n"
        f"Title: {title}\n\n"
        f"Content:\n{content[:8000]}"
    )
    # เรียก Ollama API
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/generate",
            json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False},
        )
    # คืน summary หรือ None หาก LLM ไม่พร้อมใช้
```

หาก LLM ล้มเหลว ระบบจะ ingest เนื้อหาต้นฉบับแทน (ไม่โยน exception)