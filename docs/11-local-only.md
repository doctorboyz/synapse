# 11 — Local-Only Philosophy

> ปรัชญา local-only ของ Synapse: ไม่มีข้อมูลออก network เด็ดขาด, URL validation, Docker allowance

---

## ปรัชญาหลัก

Synapse ออกแบบมาเพื่อทำงานบนเครื่องเดียว (local-first) ทุกการเชื่อมต่อต้องเป็น localhost, Unix socket, หรือ `0.0.0.0` (Docker เท่านั้น) ระบบจะตรวจสอบและแจ้งเตือนหากพบ URL ที่ไม่ใช่ local

```
Local-Only Principle:
  "ข้อมูลความรู้ของคุณ อยู่บนเครื่องของคุณ"
  - ไม่มีการส่งข้อมูลออก network ภายนอก
  - ทุก service URL ต้องเป็น localhost
  - ละเว้นเฉพาะกรณี Docker (0.0.0.0)
```

### หลักการ 4 ข้อ

1. **ไม่มี network egress** — ทุก URL ต้องชี้ไปที่ localhost/Unix socket
2. **ไม่มีการส่งข้อมูลออกนอกเครื่อง** — ข้อมูลทั้งหมดอยู่ใน PostgreSQL และ Qdrant บนเครื่องเดียวกัน
3. **ไม่มี remote API calls** — LLM, embedding, และ search ทั้งหมดทำงานผ่าน Ollama บน localhost
4. **ไม่ต้องการ authentication** — เพราะทำงานเฉพาะบนเครื่อง local จึงไม่จำเป็นต้องมี auth

---

## Local Hosts ที่อนุญาต

```python
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}
```

| Hostname | ประเภท | อนุญาต |
|---------|--------|--------|
| `localhost` | Local loopback | ผ่านเสมอ |
| `127.0.0.1` | IPv4 loopback | ผ่านเสมอ |
| `::1` | IPv6 loopback | ผ่านเสมอ |
| `0.0.0.0` | Bind all interfaces | ผ่านเสมอ (ดู Docker exceptions) |
| `host.docker.internal` | Docker host gateway | ผ่านเสมอ |
| Unix socket (ไม่มี hostname) | Unix domain socket | ผ่านเสมอ |
| `*.internal` | Docker internal DNS | ผ่านเมื่อ `allow_docker=True` |

---

## URL Validation

**ไฟล์:** `src/local_only.py`

### validate_local_url()

```python
def validate_local_url(url: str, allow_docker: bool = False) -> list[str]
```

ตรวจสอบว่า URL ชี้ไป localhost เท่านั้น คืน list ของ violations

**กลไกการตรวจสอบ:**

1. แปลง URL ด้วย `urlparse()`
2. ดึง `hostname` จาก parsed URL
3. หากไม่มี hostname (Unix socket) -> ผ่าน
4. หาก hostname อยู่ใน `LOCAL_HOSTS` -> ผ่าน
5. หาก `allow_docker=True` และ hostname ลงท้ายด้วย `.internal` -> ผ่าน
6. กรณีอื่น -> เพิ่ม violation

**ตัวอย่าง:**

```python
# URL ที่ผ่าน
validate_local_url("postgresql://admin:pass@localhost:5432/synapse")
# → []

validate_local_url("http://127.0.0.1:6333")
# → []

# URL ที่ไม่ผ่าน
validate_local_url("postgresql://db.example.com:5432/synapse")
# → ["Non-localhost URL: postgresql://... (hostname=db.example.com)"]

validate_local_url("http://192.168.1.100:6333")
# → ["Non-localhost URL: http://192.168.1.100:6333 (hostname=192.168.1.100)"]

# Docker exceptions
validate_local_url("http://qdrant.internal:6333", allow_docker=True)
# → []  (ผ่านเพราะ .internal TLD)

validate_local_url("http://qdrant.internal:6333", allow_docker=False)
# → ["Non-localhost URL: ... (hostname=qdrant.internal)"]

# Unix socket
validate_local_url("postgresql:///synapse?host=/var/run/postgresql")
# → []  (ไม่มี hostname = Unix socket)
```

---

## Settings Validation

### validate_all_settings()

```python
def validate_all_settings(settings, allow_docker: bool = False) -> list[str]
```

ตรวจสอบ URL ทั้งหมดใน Settings:

| Setting | Default | วิธีตรวจสอบ |
|---------|---------|-------------|
| `database_url` | `postgresql://admin:88888888@localhost:5432/synapse` | URL validation |
| `qdrant_url` | `http://localhost:6333` | URL validation |
| `ollama_url` | `http://localhost:11434` | URL validation |
| `api_host` | `0.0.0.0` | Hostname validation (พิเศษ) |

**กลไกพิเศษสำหรับ api_host:**

```python
api_host = settings.api_host
if api_host not in LOCAL_HOSTS and not (allow_docker and api_host == "0.0.0.0"):
    violations.append(f"Non-localhost api_host: {api_host}")
```

`0.0.0.0` ได้รับอนุญาตเฉพาะเมื่อ `allow_docker=True`

---

## check_and_warn()

```python
def check_and_warn(settings, allow_docker: bool = False) -> list[str]
```

ตรวจสอบ settings และ log warning สำหรับ violations:

```python
violations = check_and_warn(settings, allow_docker=True)
# หากมี violations → log.warning("LOCAL-ONLY VIOLATION: %s", v) สำหรับแต่ละรายการ
# คืน list ของ violations (อาจว่าง)
```

ถูกเรียกใช้ใน `synapse status` โดยอัตโนมัติ:

```python
# ใน _cmd_status()
violations = check_and_warn(settings, allow_docker=(settings.api_host == "0.0.0.0"))
result["local_only_violations"] = violations
```

**Log Output ตัวอย่าง:**

```
WARNING:synapse.local_only:LOCAL-ONLY VIOLATION: Non-localhost URL: postgresql://db.aws.com:5432/synapse (hostname=db.aws.com)
WARNING:synapse.local_only:LOCAL-ONLY VIOLATION: Non-localhost api_host: 192.168.1.100
```

---

## Docker Configuration

### เงื่อนไข allow_docker

```python
# allow_docker=True เมื่อ api_host เป็น 0.0.0.0 (Docker mode)
allow_docker = (settings.api_host == "0.0.0.0")
```

เมื่อ `api_host = "0.0.0.0"`:
- `0.0.0.0` จะผ่านการตรวจสอบ `api_host` (อยู่ใน `LOCAL_HOSTS`)
- `*.internal` URLs จะผ่านการตรวจสอบ (เพราะ `allow_docker=True`)
- `host.docker.internal` จะผ่านเสมอ (อยู่ใน `LOCAL_HOSTS`)

### การตั้งค่าสำหรับ Docker

```yaml
# ~/.synapse/config.yaml สำหรับ Docker
database_url: "postgresql://admin:88888888@host.docker.internal:5432/synapse"
qdrant_url: "http://qdrant.internal:6333"
ollama_url: "http://host.docker.internal:11434"
api_host: "0.0.0.0"
```

---

## การตั้งค่าที่ปลอดภัย

### Default Configuration (local-only)

```bash
DATABASE_URL="postgresql://admin:88888888@localhost:5432/synapse"
QDRANT_URL="http://localhost:6333"
OLLAMA_URL="http://localhost:11434"
SYNAPSE_HOST="0.0.0.0"
SYNAPSE_PORT="8420"
```

### การตั้งค่าที่ไม่ปลอดภัย (ไม่ควรใช้)

```bash
# ไม่ปลอดภัย — ส่งข้อมูลออกนอกเครื่อง!
DATABASE_URL="postgresql://admin:pass@db.aws.com:5432/synapse"
QDRANT_URL="https://qdrant.cloud.example.com:6333"
OLLAMA_URL="https://api.openai.com/v1"
```

### ความเสี่ยงถ้าละเมิด local-only

| การตั้งค่า | ความเสี่ยง |
|-----------|-----------|
| `database_url` ชี้ไป remote | ข้อมูลถูกส่งออกนอกเครื่อง, network eavesdropping |
| `qdrant_url` ชี้ไป remote | เวกเตอร์ embedding รั่วไหล, data eavesdropping |
| `ollama_url` ชี้ไป remote | Prompt และ content ถูกส่งไป server ภายนอก |
| `api_host` เป็น public IP | API endpoint เปิดสู่ภายนอก, ใครก็เข้าถึงได้ |

---

## Unix Socket Support

หาก PostgreSQL ทำงานผ่าน Unix socket (ไม่มี hostname ใน URL) การตรวจสอบจะผ่านโดยอัตโนมัติ:

```python
validate_local_url("postgresql:///synapse?host=/var/run/postgresql")
# → []  (ไม่มี hostname = Unix socket)

validate_local_url("postgresql://admin@/synapse?host=/tmp/.s.PGSQL.5432")
# → []  (hostname ว่าง)
```

---

## ข้อสังเกต

1. **`0.0.0.0` เป็น localhost แต่เปิดรับทุก interface** — เหมาะสำหรับ Docker แต่ต้องระวังใน production
2. **`check_and_warn()` เป็น soft enforcement** — แจ้งเตือนเท่านั้น ไม่ได้บังคับให้ใช้ localhost
3. **การตรวจสอบทำตอน `synapse status` เท่านั้น** — ไม่มีการ re-check ระหว่างการทำงาน
4. **Password ใน connection string ไม่ถูกตรวจสอบ** — `validate_local_url` ตรวจเฉพาะ hostname ไม่ได้ตรวจ credential
5. **Unix socket paths ผ่านการตรวจสอบเสมอ** — เพราะไม่มี hostname ใน URL