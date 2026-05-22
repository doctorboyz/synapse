# Synapse v3 — ภาพรวมโปรเจกต์

> Hybrid Knowledge Framework — PostgreSQL + Qdrant + MCP

Synapse เป็นเฟรมเวิร์กจัดการความรู้แบบ local-first ทำงานบนเครื่องเดียว ไม่มีการส่งข้อมูลออก network ภายนอกเด็ดขาด ระบบอ่านไฟล์ สร้าง vector embedding เก็บลงฐานข้อมูล ตรวจจับความขัดแย้ง และกระทำการคืนสภาพ — ทั้งหมดบนเครื่องของคุณเอง

---

## การเข้าถึง 3 ทาง (3-Way Access)

Synapse ให้บริการผ่าน 3 ช่องทางหลัก ที่มีความสามารถเท่ากัน:

| ช่องทาง | การใช้งาน | โปรโตคอล | เหมาะสำหรับ |
|---------|----------|----------|-------------|
| **CLI** | Terminal โดยตรง | `synapse <command>` | ผู้ใช้งาน, scripting, CI/CD |
| **MCP** | Claude Code / AI agent | stdio JSON-RPC | AI agent ที่ต้องการเข้าถึงคลังความรู้ |
| **HTTP API** | REST API | HTTP JSON (port 8420) | Docker service, แอปพลิเคชันภายนอก |

### ตัวอย่างเปรียบเทียบ — ค้นหาความรู้

```bash
# CLI
synapse search "error handling patterns"

# MCP (เรียกผ่าน AI agent)
synapse_search(query="error handling patterns")

# HTTP API
curl -X POST http://localhost:8420/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "error handling patterns"}'
```

---

## สถาปัตยกรรม (Architecture)

```
                        ┌─────────────────────────────────────────────┐
                        │            ชั้นเข้าถึง (Access Layer)            │
                        │                                             │
                        │  ┌─────┐    ┌─────────┐    ┌───────────┐   │
                        │  │ CLI │    │  MCP    │    │  HTTP API │   │
                        │  │     │    │ (stdio) │    │ (port     │   │
                        │  │     │    │         │    │  8420)    │   │
                        │  └──┬──┘    └────┬────┘    └─────┬─────┘   │
                        └─────┼────────────┼───────────────┼─────────┘
                              │            │               │
                        ┌─────┼────────────┼───────────────┼─────────┐
                        │     └────────────┼───────────────┘         │
                        │            ชั้นนำเข้า (Ingest Layer)          │
                        │                                              │
                        │  ┌──────────┐  ┌──────────────┐  ┌────────┐│
                        │  │   Push   │  │  Init Scan   │  │  Hook  ││
                        │  │ Pipeline │  │  (ไฟล์ทั้งหมด) │  │Handler ││
                        │  └────┬─────┘  └──────┬───────┘  └───┬────┘│
                        │       │               │              │      │
                        │  ┌────┴─────┐  ┌──────┴───────┐     │      │
                        │  │  Oracle  │  │   Scheduler  │     │      │
                        │  │  Paths   │  │  (scan loop) │     │      │
                        │  └──────────┘  └──────────────┘     │      │
                        └─────────────────────────────┬───────┘      │
                                              ┌──────┴───────┐      │
                        ┌─────────────────────┼──────────────┼──────┼─┐
                        │     ชั้นค้นคืน (Retrieve Layer)    │      │ │
                        │                     │              │      │ │
                        │  ┌──────────────────┴───┐  ┌─────┴────┐ │ │
                        │  │    Hybrid Search       │  │  Cache   │ │ │
                        │  │  (RRF Fusion)         │  │ (LRU+TTL)│ │ │
                        │  │  dense 60% + FTS 40%  │  └──────────┘ │ │
                        │  └────────┬─────────────┘               │ │
                        └────────────┼─────────────────────────────┘ │
                                     │                               │
                        ┌────────────┼───────────────────────────────┘
                        │     ชั้นฐานข้อมูล (Storage Layer)     │
                        │                                    │
                        │  ┌─────────────┐   ┌────────────┐  │
                        │  │ PostgreSQL  │   │   Qdrant   │  │
                        │  │ (CRUD, FTS, │   │  (Vector   │  │
                        │  │  supersede, │   │   Search)  │  │
                        │  │  concepts,  │   │  COSINE)   │  │
                        │  │  trace)     │   │            │  │
                        │  └──────┬──────┘   └─────┬──────┘  │
                        │         │                │         │
                        │  ┌──────┴──────┐   ┌─────┴──────┐  │
                        │  │  tsvector   │   │  Payload   │  │
                        │  │  GIN Index  │   │  Filter    │  │
                        │  └─────────────┘   └────────────┘  │
                        └─────────────────────────────────────┘
                                     │
                        ┌────────────┼──────────────────────┐
                        │     ชั้น Embedding (Embed Layer)    │
                        │                                   │
                        │  ┌───────────────┐                │
                        │  │    Ollama     │                │
                        │  │  (nomic-embed │                │
                        │  │   -text 768d) │                │
                        │  │  async+retry  │                │
                        │  └───────────────┘                │
                        └──────────────────────────────────┘

                        ┌──────────────────────────────────┐
                        │   ชั้น Reconcile (บำรุงรักษา)       │
                        │                                   │
                        │  ┌─────────┐    ┌───────────────┐ │
                        │  │ Defrag  │    │     Detox     │ │
                        │  │(กระทัด   │    │ (ตรวจความ    │ │
                        │  │ ข้อมูลซ้ำ)│    │  ขัดแย้ง+แก้ไข)│ │
                        │  └─────────┘    └───────┬───────┘ │
                        │                          │         │
                        │                  ┌──────┴──────┐  │
                        │                  │  LLM       │  │
                        │                  │ (qwen2.5)  │  │
                        │                  └────────────┘  │
                        └──────────────────────────────────┘
```

---

## Stack เทคโนโลยี

| ส่วนประกอบ | เทคโนโลยี | รายละเอียด |
|-----------|----------|-----------|
| Runtime | Python 3.12+ | async/await, type hints |
| Database | PostgreSQL | asyncpg, tsvector FTS |
| Vector Store | Qdrant | COSINE distance, payload filter |
| Embedding | Ollama | nomic-embed-text, 768 dims |
| LLM | qwen2.5:7b | สรุป, ตรวจจับ conflict, synthesis |
| Web Framework | FastAPI | uvicorn, async routes |
| MCP SDK | mcp | stdio JSON-RPC |
| Search | RRF Fusion | 60% dense / 40% FTS |
| Cache | LRU + TTL | Thread-safe, configurable |

---

## หลักการออกแบบ (Design Principles)

### 1. Local-Only — ไม่ออก network เด็ดขาด

ทุกการเชื่อมต่อต้องเป็น localhost, Unix socket หรือ `0.0.0.0` (Docker เท่านั้น) ระบบจะตรวจสอบและแจ้งเตือนหากพบ URL ที่ไม่ใช่ local

```bash
# ถูกต้อง — localhost
DATABASE_URL=postgresql://admin:pass@localhost:5432/synapse
QDRANT_URL=http://localhost:6333

# ผิด — จะถูกตรวจจับเป็น violation
DATABASE_URL=postgresql://admin:pass@db.example.com:5432/synapse
```

### 2. Nothing is Deleted — supersession เท่านั้น

ไม่มีการลบข้อมูล การอัปเดตทำผ่าน supersession: เอกสารเก่าถูก mark ว่า `superseded_by` เอกสารใหม่ และบันทึกลง `supersede_log`

### 3. Oracle-Aware doc_types

ระบบรู้จักโครงสร้าง kappa/psi (κ/ψ) ของ Oracle brain และ map path ไปยัง doc_type อัตโนมัติ:

| Path | doc_type | brain_tier |
|------|----------|-----------|
| ψ/memory/learnings/ | learning | extrinsic |
| ψ/memory/retrospectives/ | retro | extrinsic |
| ψ/outbox/ | handoff | extrinsic |
| κ/extrinsic/wisdom/knowledge/ | wisdom | extrinsic |
| κ/extrinsic/wisdom/reference/ | reference | extrinsic |
| κ/extrinsic/experience/learn/ | learning | extrinsic |
| κ/extrinsic/experience/work/logs/ | log | extrinsic |
| κ/intrinsic/instinct/ | instinct | intrinsic |
| κ/intrinsic/identity/ | instinct | intrinsic |
| κ/intrinsic/inherit/ | instinct | intrinsic |

### 4. source_project แยกจาก scope

`source_project` ระบุโปรเจกต์ต้นทาง ส่วน `scope` เป็น namespace สำหรับจัดกลุ่มข้อมูล ทั้งสองอยู่ในระดับเดียวกันแต่ทำหน้าที่ต่างกัน

### 5. FTS Fallback

เมื่อ Qdrant ไม่พร้อมใช้งาน ระบบจะ fall back ไปใช้ PostgreSQL tsvector full-text search โดยอัตโนมัติ

### 6. Dedup by (content_hash, scope)

ตรวจสอบเอกสารซ้ำด้วย hash ของเนื้อหา + scope หากเจอจะข้ามและคืนสถานะ `duplicate`

---

## โหมดการทำงาน

### Single Command Mode

รันคำสั่งเดี่ยวแล้วจบ — เชื่อมต่อฐานข้อมูล ทำงาน ปิดการเชื่อมต่อ

```bash
synapse push --title "My Note" --content "Hello world"
synapse search "hello"
synapse stats
```

### Service Mode (Daemon)

รัน HTTP API server แบบ long-running:

```bash
synapse serve    # เริ่ม HTTP API ที่ port 8420
```

### MCP Mode

รันเป็น MCP stdio server สำหรับ AI agent:

```bash
synapse mcp      # เริ่ม MCP stdio server
```