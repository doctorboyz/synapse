# 05 — การตั้งค่า (Configuration)

> ตัวแปรสภาพแวดล้อม, YAML config, hot-reload, daemon settings, local-only enforcement

Synapse ใช้ environment variables เป็นหลัก รองรับ YAML config file สำหรับการตั้งค่าที่ซับซ้อน และรองรับ hot-reload ผ่าน SIGHUP

---

## Settings Dataclass

**ไฟล์:** `src/config.py`

คลาส `Settings` เป็น dataclass ที่อ่านค่าจาก environment variables ก่อน แล้วจึง override ด้วย YAML config

```python
from src.config import Settings

# สร้างจาก env vars
settings = Settings()

# สร้างจาก YAML file
settings = Settings.from_yaml("~/.synapse/config.yaml")
```

---

## Environment Variables

### การเชื่อมต่อฐานข้อมูล

| Environment Variable | Type | Default | คำอธิบาย |
|---|---|---|---|
| `DATABASE_URL` | `str` | `postgresql://admin:88888888@localhost:5432/synapse` | PostgreSQL connection string |
| `SYNAPSE_DB_URL` | `str` | - | สำรอง: ใช้แทน DATABASE_URL |
| `QDRANT_URL` | `str` | `http://localhost:6333` | URL ของ Qdrant server |
| `SYNAPSE_QDRANT_COLLECTION` | `str` | `synapse_vectors` | ชื่อ collection ใน Qdrant |
| `OLLAMA_URL` | `str` | `http://localhost:11434` | URL ของ Ollama API |

**ลำดับความสำคัญ:** `DATABASE_URL` มีความสำคัญเหนือกว่า `SYNAPSE_DB_URL`

### Embedding

| Environment Variable | Type | Default | คำอธิบาย |
|---|---|---|---|
| `EMBEDDING_MODEL` | `str` | `nomic-embed-text` | ชื่อโมเดล embedding |
| `EMBEDDING_DIM` | `int` | `768` | ขนาดเวกเตอร์ embedding |
| `EMBEDDING_TIMEOUT` | `int` | `30` | timeout การ embed (วินาที) |

### HTTP Server

| Environment Variable | Type | Default | คำอธิบาย |
|---|---|---|---|
| `SYNAPSE_HOST` | `str` | `0.0.0.0` | bind address ของ HTTP server |
| `SYNAPSE_PORT` | `int` | `8420` | port ของ HTTP server |

### Search & Cache

| Environment Variable | Type | Default | คำอธิบาย |
|---|---|---|---|
| `SEARCH_WEIGHTS` | `str` | `0.6,0.4` | น้ำหนัก RRF fusion (dense,FTS) คั่นด้วย comma |
| `CACHE_TTL` | `int` | `300` | cache TTL ในวินาที (5 นาที) |
| `CACHE_MAX_SIZE` | `int` | `1000` | จำนวนรายการ cache สูงสุด |

`search_rrf_k` ตั้งค่าในโค้ดเป็น `60` ไม่มี environment variable แยก

### Logging

| Environment Variable | Type | Default | คำอธิบาย |
|---|---|---|---|
| `SYNAPSE_LOG_LEVEL` | `str` | `INFO` | logging level: DEBUG, INFO, WARNING, ERROR |

### Daemon

| Environment Variable | Type | Default | คำอธิบาย |
|---|---|---|---|
| `SYNAPSE_PID_FILE` | `str` | `~/.synapse/synapse.pid` | path ของ PID file |
| `SYNAPSE_SCAN_INTERVAL` | `int` | `0` | ช่วงเวลาสแกนเป็นวินาที (0 = ปิด) |
| `SYNAPSE_CONFIG` | `str` | `""` | path ของ YAML config file |

---

## YAML Config

### ตำแหน่ง Default

```
~/.synapse/config.yaml
```

### รูปแบบไฟล์

```yaml
# ~/.synapse/config.yaml
database_url: "postgresql://admin:password@localhost:5432/synapse"
qdrant_url: "http://localhost:6333"
qdrant_collection: "synapse_vectors"
ollama_url: "http://localhost:11434"
embedding_model: "nomic-embed-text"
embedding_dim: 768
embedding_timeout: 30
api_host: "0.0.0.0"
api_port: 8420
log_level: "INFO"
search_weights:
  - 0.6
  - 0.4
search_rrf_k: 60
cache_ttl: 300
cache_max_size: 1000
scan_interval: 600
```

### การโหลด

```python
# โหลดจาก default path (~/.synapse/config.yaml)
settings = Settings.from_yaml()

# โหลดจาก path ที่ระบุ
settings = Settings.from_yaml("/path/to/config.yaml")

# โหลดจาก SYNAPSE_CONFIG env var
settings = Settings.from_yaml(os.getenv("SYNAPSE_CONFIG") or None)
```

### ลำดับความสำคัญ

```
Environment Variables > YAML Config > Default Values
```

1. สร้าง `Settings()` จาก env vars + defaults
2. หากมี YAML file → override เฉพาะ keys ที่อยู่ในไฟล์
3. env vars จะ override ค่าจาก YAML (เพราะ env vars ถูกอ่านก่อนใน dataclass default_factory)

### การติดตั้ง PyYAML

```bash
pip install pyyaml
```

หากไม่มี PyYAML ระบบจะข้ามการโหลด YAML config และ log warning

---

## Hot-Reload (SIGHUP)

ส่งสัญญาณ `SIGHUP` ให้ daemon process เพื่อโหลด config ใหม่โดยไม่ต้อง restart

```bash
# หา PID ของ daemon
cat ~/.synapse/synapse.pid

# ส่ง SIGHUP
kill -HUP $(cat ~/.synapse/synapse.pid)
```

### กลไกการ Hot-Reload

```python
def reload(self) -> None:
    """Re-read settings from env vars + config file (for SIGHUP)."""
    new_settings = Settings.from_yaml(self.config_path or None)
    for key in vars(new_settings):
        if key != "config_path":
            setattr(self, key, getattr(new_settings, key))
    log.info("Configuration reloaded")
```

**ข้อสังเกต:**
- `config_path` ไม่ถูกเปลี่ยนระหว่าง reload (ต้อง restart เพื่อเปลี่ยน config path)
- Settings object ถูกเปลี่ยนในหน่วยความจำ แต่ components ที่สร้างจาก settings เก่า (เช่น PgStore, QdrantStore) ไม่ถูกสร้างใหม่อัตโนมัติ
- การเปลี่ยน `database_url` หรือ `qdrant_url` จะไม่มีผลจนกว่าจะ restart daemon

### การตั้งค่า Signal Handlers

```python
from src.daemon import setup_signals

def on_reload():
    settings.reload()
    log.info("Config reloaded via SIGHUP")

def on_shutdown():
    log.info("Shutting down...")

setup_signals(on_reload=on_reload, on_shutdown=on_shutdown)
```

Signal handlers ที่ลงทะเบียน:

| Signal | พฤติกรรม |
|--------|----------|
| `SIGTERM` | Shutdown daemon |
| `SIGINT` | Shutdown daemon (Ctrl+C) |
| `SIGHUP` | Reload configuration (ไม่รองรับบน Windows) |

---

## การตั้งค่าสำหรับ Docker

```yaml
# docker-compose.yaml
services:
  synapse:
    image: synapse:latest
    environment:
      DATABASE_URL: "postgresql://admin:pass@db:5432/synapse"
      QDRANT_URL: "http://qdrant:6333"
      OLLAMA_URL: "http://ollama:11434"
      SYNAPSE_HOST: "0.0.0.0"
      SYNAPSE_PORT: "8420"
      SYNAPSE_SCAN_INTERVAL: "600"
    ports:
      - "8420:8420"
```

**หมายเหตุ:** `0.0.0.0` เป็นค่าที่ยอมรับได้ใน Docker environment แต่ระบบ local-only enforcement จะตรวจสอบ URL อื่นๆ

---

## การตั้งค่าสำหรับ Development

```bash
# .env.local
DATABASE_URL=postgresql://admin:88888888@localhost:5432/synapse
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
SYNAPSE_LOG_LEVEL=DEBUG
SEARCH_WEIGHTS=0.6,0.4
CACHE_TTL=60
CACHE_MAX_SIZE=100
```

```bash
# รันด้วย env file
set -a && source .env.local && set +a
synapse serve
```