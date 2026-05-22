# 10 — Scheduler & Daemon

> ระบบสแกนอัตโนมัติ: ScanScheduler, project registry, daemon lifecycle

---

## ภาพรวม

Synapse รองรับการสแกนไฟล์อัตโนมัติผ่าน ScanScheduler ซึ่งทำงานเป็น background task ตรวจสอบโปรเจกต์ที่ลงทะเบียนตามช่วงเวลาที่กำหนด

```
ระบบ Registry:
  registered_projects table
      │
      ▼
  ScanScheduler._scan_registered_projects()
      │
      ▼
  init_scan() for each project
      │
      ▼
  Push pipeline → PostgreSQL + Qdrant
```

---

## ScanScheduler

**ไฟล์:** `src/scheduler.py`

### Constructor

```python
ScanScheduler(pg: PgStore, settings: Settings, interval: int = 600)
```

| พารามิเตอร์ | Default | คำอธิบาย |
|-------------|---------|----------|
| `pg` | - | PgStore instance |
| `settings` | - | Settings instance |
| `interval` | `600` | ช่วงเวลาระหว่างการสแกน (วินาที) |

### เมธอด

| เมธอด | คำอธิบาย |
|--------|----------|
| `async start()` | เริ่ม scan loop ทำงานเป็น background task |
| `async stop()` | หยุด scan loop |
| `async scan_once()` | รันสแกนครั้งเดียวของโปรเจกต์ที่ลงทะเบียนทั้งหมด |

### Scan Loop

เมื่อเรียก `start()` scheduler จะรัน `_scan_loop()` เป็น asyncio task:

```python
async def _scan_loop(self) -> None:
    while self._running:
        try:
            await self._scan_registered_projects()
        except Exception as e:
            log.error("Scan loop error: %s", e)

        try:
            await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            break
```

- สแกนทุก `interval` วินาที (default: 600 = 10 นาที)
- หากสแกนเกิดข้อผิดพลาด → log error และรอช่วงต่อไป
- หากถูก cancel → หยุด loop

### การตั้งค่า Interval

```bash
# สแกนทุก 10 นาที (default)
SYNAPSE_SCAN_INTERVAL=600 synapse serve

# สแกนทุก 30 นาที
SYNAPSE_SCAN_INTERVAL=1800 synapse serve

# ปิดการสแกนอัตโนมัติ (default ถ้าไม่ตั้งค่า)
SYNAPSE_SCAN_INTERVAL=0 synapse serve
```

หาก `SYNAPSE_SCAN_INTERVAL=0` scheduler จะไม่เริ่มทำงาน

---

## Project Registry

**ไฟล์:** `src/registry.py`

Project registry เก็บข้อมูลโปรเจกต์ที่ลงทะเบียนในตาราง `registered_projects` เพื่อให้ scheduler สแกนไฟล์ใหม่ได้

### ฟังก์ชัน

#### `detect_scope(project_path: str) -> str`

Auto-detect scope จาก path:

```python
detect_scope("/Users/user/code/myproject")
# → "myproject"

detect_scope("/Users/user/code/github.com/doctorboyz/synapse")
# → "synapse"  (ตัดส่วน github.com ออก)
```

กฎการตั้งชื่อ scope:
- ใช้ `Path.name` ของ path สุดท้าย
- แปลงเป็น lowercase
- แทนที่อักขระที่ไม่ใช่ alphanumeric ด้วยขีดกลาง
- ลบขีดกลางซ้ำ

#### `validate_scope(scope: str) -> bool`

ตรวจสอบว่า scope name ถูกต้อง:

```python
validate_scope("myproject")       # True
validate_scope("my-project-2")    # True
validate_scope("My Project")      # False (มี space)
validate_scope("")                 # False (ว่าง)
```

กฎ: lowercase, alphanumeric, ขีดกลางเท่านั้น, 1-64 ตัวอักษร, ต้องขึ้นต้นด้วย alphanumeric

#### `async register_project(pg: PgStore, project_path: str, scope: str | None = None) -> dict`

ลงทะเบียนโปรเจกต์:

```python
result = await register_project(pg, "/Users/user/code/myproject", scope="myproject")
# → {"scope": "myproject", "project_path": "/Users/user/code/myproject", "status": "registered"}
```

- หากไม่ระบุ scope → auto-detect จาก path
- ใช้ `UPSERT` (ON CONFLICT DO UPDATE) หาก scope มีอยู่แล้วจะอัปเดต path

#### `async unregister_project(pg: PgStore, scope: str) -> dict`

ยกเลิกลงทะเบียน:

```python
result = await unregister_project(pg, "myproject")
# → {"scope": "myproject", "status": "unregistered"}
# หรือ {"scope": "myproject", "status": "not_found"}
```

#### `async list_projects(pg: PgStore) -> list[dict]`

แสดงโปรเจกต์ที่ลงทะเบียนทั้งหมด:

```python
projects = await list_projects(pg)
# → [
#     {"scope": "myproject", "project_path": "/Users/user/code/myproject", "registered_at": "..."},
#     {"scope": "shared", "project_path": "/Users/user/code/shared", "registered_at": "..."}
#   ]
```

#### `async get_all_scopes(pg: PgStore) -> list[str]`

ดึงเฉพาะรายชื่อ scope:

```python
scopes = await get_all_scopes(pg)
# → ["myproject", "shared"]
```

---

## Daemon Lifecycle

**ไฟล์:** `src/daemon.py`

### PID File Management

```python
DEFAULT_PID_DIR = Path.home() / ".synapse"
# PID file: ~/.synapse/synapse.pid
```

| ฟังก์ชัน | คำอธิบาย |
|----------|----------|
| `write_pid(pid_path=None)` | เขียน PID ปัจจุบันลงไฟล์ สร้าง directory อัตโนมัติ |
| `read_pid(pid_path=None)` | อ่าน PID จากไฟล์ คืน None หากไม่พบหรือ invalid |
| `remove_pid(pid_path=None)` | ลบ PID file |
| `is_running(pid_path=None)` | ตรวจว่า process ยังทำงานอยู่ (ส่ง signal 0) |

### Stop Daemon

```python
def stop_daemon(pid_path=None) -> dict:
```

ขั้นตอน:
1. อ่าน PID จากไฟล์
2. ส่ง `SIGTERM` ให้ process
3. รอสูงสุด 15 วินาที (ตรวจทุก 0.5 วินาที)
4. หากยังไม่หยุด → ส่ง `SIGKILL`
5. ลบ PID file

**ผลลัพธ์:**

```json
{"status": "stopped", "pid": 12345}     // หยุดสำเร็จด้วย SIGTERM
{"status": "killed", "pid": 12345}       // หยุดด้วย SIGKILL
{"status": "not_running", "pid": 12345}  // process หยุดไปแล้ว
{"status": "not_running", "message": "No PID file found"}  // ไม่มี PID file
```

### Get Status

```python
def get_status(pid_path=None) -> dict:
```

คืนสถานะของ daemon:

```json
{
  "running": true,
  "pid": 12345,
  "pid_file": "/home/user/.synapse/synapse.pid"
}
```

### Signal Handlers

```python
def setup_signals(on_reload=None, on_shutdown=None):
```

ลงทะเบียน signal handlers:

| Signal | พฤติกรรม |
|--------|----------|
| `SIGTERM` | เรียก `on_shutdown()` |
| `SIGINT` | เรียก `on_shutdown()` (Ctrl+C) |
| `SIGHUP` | เรียก `on_reload()` (ไม่รองรับบน Windows) |

---

## การใช้งาน CLI

### ลงทะเบียนโปรเจกต์

```bash
# ลงทะเบียน path ปัจจุบัน
synapse register

# ลงทะเบียน path ที่ระบุ
synapse register --path /path/to/project

# ระบุ scope เอง
synapse register --path /path/to/project --scope myproject
```

### ยกเลิกลงทะเบียน

```bash
synapse unregister myproject
```

### แสดงโปรเจกต์ที่ลงทะเบียน

```bash
synapse projects
```

### สแกนหาไฟล์ใหม่ (ครั้งเดียว)

```bash
synapse scan
```

### ดูสถานะ daemon

```bash
synapse status
```

ผลลัพธ์รวม: daemon status, local-only violations, สถิติฐานข้อมูล

### หยุด daemon

```bash
synapse stop
```

---

## ข้อควรระวัง

1. **Scan interval = 0 หมายถึงปิด** — scheduler จะไม่เริ่มทำงานหาก `SYNAPSE_SCAN_INTERVAL=0`
2. **Path ต้องมีอยู่จริง** — หาก `project_path` ไม่มี scheduler จะ log warning และข้าม
3. **Scan ทำตามลำดับ** — แต่ละโปรเจกต์ถูกสแกนทีละอัน (sequential) หากมีหลายโปรเจกต์อาจใช้เวลานาน
4. **Init scan ใช้ resource มาก** — การสแกนโปรเจกต์ใหญ่ต้อง embed ไฟล์ทุกไฟล์ผ่าน Ollama
5. **Scope name validation** — ต้องเป็น lowercase, alphanumeric, ขีดกลาง, 1-64 ตัวอักษร