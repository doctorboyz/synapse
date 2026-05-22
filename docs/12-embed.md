# 12 — Embedding & LLM Integration

> Ollama embedding pipeline: async embed, retry logic, batching, LLM integration สำหรับ conflict detection และ summarization

---

## ภาพรวม

Synapse ใช้ Ollama สำหรับ 2 ฟังก์ชันหลัก:

1. **Embedding** — แปลงข้อความเป็นเวกเตอร์ 768 มิติสำหรับ vector search
2. **LLM Generation** — สรุปเนื้อหาและวิเคราะห์ความขัดแย้งด้วย qwen2.5:7b

```
ข้อความ ("error handling patterns")
        │
        ▼
  ┌─────────────┐
  │ OllamaEmbed │  POST /api/embed
  │             │  model: nomic-embed-text
  │             │  768-dimensional vector
  └──────┬──────┘
         │
    [0.12, -0.34, 0.56, ...]   ← ใช้กับ Qdrant search
```

---

## OllamaEmbedder

**ไฟล์:** `src/embed/ollama.py`

### Constructor

```python
OllamaEmbedder(settings: Settings | None = None)
```

ภายในตั้งค่าจาก Settings:

| Attribute | Source | Default |
|-----------|--------|---------|
| `_base_url` | `settings.ollama_url` | `http://localhost:11434` |
| `_model` | `settings.embedding_model` | `nomic-embed-text` |
| `_dim` | `settings.embedding_dim` | `768` |
| `_timeout` | `settings.embedding_timeout` | `30` (วินาที) |
| `_max_retries` | hardcoded | `2` |
| `_batch_semaphore` | hardcoded | `asyncio.Semaphore(4)` |

### embed()

```python
async def embed(text: str) -> list[float]
```

แปลงข้อความเป็นเวกเตอร์ embedding

**ขั้นตอน:**

1. ตัดทอนข้อความเกิน `MAX_CHUNK_CHARS` (4000 ตัวอักษร)
2. POST `/api/embed` ไปยัง Ollama
3. หากล้มเหลว → retry ด้วย exponential backoff (0.5s, 1s)
4. หากล้มเหลวทั้งหมด → โยน `EmbeddingError`

**ตัวอย่าง request:**

```json
{
  "model": "nomic-embed-text",
  "input": "error handling patterns"
}
```

**ตัวอย่าง response:**

```json
{
  "embeddings": [[0.12, -0.34, 0.56, ...]]
}
```

### Retry Logic

```
Attempt 1: POST /api/embed → ล้มเหลว
  → รอ 0.5s (0.5 * 2^0)
Attempt 2: POST /api/embed → ล้มเหลว
  → รอ 1.0s (0.5 * 2^1)
Attempt 3: POST /api/embed → ล้มเหลว
  → โยน EmbeddingError
```

- ลองใหม่สูงสุด 2 ครั้ง (`_max_retries = 2`)
- Exponential backoff: `0.5 * 2^attempt` วินาที
- จับเฉพาะ `httpx.HTTPError`, `KeyError`, `IndexError`

### embed_batch()

```python
async def embed_batch(texts: list[str]) -> list[list[float]]
```

Embed หลายข้อความพร้อมกัน จำกัด concurrency ด้วย semaphore=4:

```python
async with self._batch_semaphore:
    results = []
    for text in texts:
        vec = await self.embed(text)
        results.append(vec)
    return results
```

**หมายเหตุ:** ปัจจุบัน embed ทีละรายการตามลำดับ (sequential) ภายใน semaphore เพื่อจำกัด concurrency

### check()

```python
async def check() -> bool
```

ตรวจสอบว่า Ollama embedding พร้อมใช้งานหรือไม่:

```python
try:
    await embed("health check")
    return True
except Exception:
    return False
```

ใช้ใน:
- HTTP API `/api/health` เพื่อตรวจสอบสุขภาพ
- Hook handler เพื่อตัดสินใจว่าจะ embed หรือไม่

---

## EmbeddingError

```python
class EmbeddingError(Exception):
    pass
```

Exception สำหรับ embed ล้มเหลว สืบทอดจาก `Exception`

**การจัดการใน HybridSearch:**

```python
try:
    vector = await self.embedder.embed(query)
    dense_results = await self.qdrant.search(vector, ...)
except EmbeddingError as e:
    log.warning("Dense search failed, falling back to FTS: %s", e)
    return await self.pg.search_fts(query, ...)  # Fallback to FTS
```

---

## Configuration

### Environment Variables

| Variable | Default | คำอธิบาย |
|----------|---------|----------|
| `OLLAMA_URL` | `http://localhost:11434` | URL ของ Ollama API |
| `EMBEDDING_MODEL` | `nomic-embed-text` | ชื่อโมเดล embedding |
| `EMBEDDING_DIM` | `768` | ขนาดเวกเตอร์ embedding |
| `EMBEDDING_TIMEOUT` | `30` | timeout การ embed (วินาที) |

### YAML Config

```yaml
# ~/.synapse/config.yaml
ollama_url: "http://localhost:11434"
embedding_model: "nomic-embed-text"
embedding_dim: 768
embedding_timeout: 30
```

### การติดตั้ง Ollama

```bash
# ติดตั้ง Ollama
curl -fsSL https://ollama.com/install.sh | sh

# ดาวน์โหลดโมเดล embedding
ollama pull nomic-embed-text

# ดาวน์โหลดโมเดล LLM สำหรับ summarization
ollama pull qwen2.5:7b
```

---

## LLM Integration

### โมเดลที่ใช้

| ฟังก์ชัน | โมเดล | วัตถุประสงค์ |
|----------|--------|----------|
| Embedding | `nomic-embed-text` | แปลงข้อความเป็นเวกเตอร์ 768 มิติ |
| Conflict Analysis | `qwen2.5:7b` | วิเคราะห์ความขัดแย้งระหว่างเอกสาร |
| Summarization | `qwen2.5:7b` | สรุปเอกสารยาวก่อน ingest |

### Conflict Analysis

**ไฟล์:** `src/reconcile/llm.py`

```python
async def analyze_conflict(
    doc_a: dict,    # {"title": ..., "content": ...}
    doc_b: dict,    # {"title": ..., "content": ...}
    settings,       # Settings object (has ollama_url)
    model: str = "qwen2.5:7b",
) -> dict | None
```

ส่งคำขอไปยัง Ollama `/api/generate` endpoint:

```python
async with httpx.AsyncClient(timeout=120.0) as client:
    response = await client.post(
        f"{settings.ollama_url}/api/generate",
        json={
            "model": "qwen2.5:7b",
            "prompt": CONFLICT_PROMPT.format(title_a=..., content_a=..., ...),
            "stream": False,
            "format": "json",
        },
    )
```

**Prompt Template (CONFLICT_PROMPT):**

```
Analyze these two knowledge documents and determine if they conflict.

Document A:
Title: {title_a}
Content: {content_a}

Document B:
Title: {title_b}
Content: {content_b}

Respond in this exact JSON format:
{
  "is_conflict": true/false,
  "conflict_type": "contradiction|overlap|outdated|none",
  "reason": "brief explanation of the conflict or why no conflict exists",
  "supersede_id": "a_or_b_or_none",
  "merged_content": "if conflict, provide merged/resolved content. if no conflict, empty string"
}

Be conservative: only mark as conflict if the documents genuinely contradict each other.
Overlapping information is not a conflict unless one document contradicts the other.
```

**ผลลัพธ์ที่คาดหวัง:**

```json
{
  "is_conflict": true,
  "conflict_type": "contradiction",
  "reason": "Document A says to use early returns, Document B says to use try/catch blocks",
  "supersede_id": "a",
  "merged_content": "Combined guidance: use early returns for simple cases..."
}
```

**การแก้ไข JSON Response:**

LLM อาจครอบ JSON ด้วย markdown code blocks:

```python
if "```json" in text:
    text = text.split("```json")[1].split("```")[0].strip()
elif "```" in text:
    text = text.split("```")[1].split("```")[0].strip()
```

**Normalization:**

```python
if isinstance(result.get("is_conflict"), str):
    result["is_conflict"] = result["is_conflict"].lower() in ("true", "yes")
```

### Summarization

**ไฟล์:** `src/reconcile/llm.py`

```python
async def summarize_content(
    content: str,
    title: str,
    settings,
    model: str = "qwen2.5:7b",
) -> str | None
```

สรุปเนื้อหาเอกสารโดยจำกัดไม่เกิน 500 คำ:

```python
prompt = (
    f"Summarize the following document concisely, preserving key information. "
    f"Keep the summary under 500 words.\n\n"
    f"Title: {title}\n\n"
    f"Content:\n{content[:8000]}"
)
```

**การเรียกใช้ใน init_scan:**

```python
# สรุปเฉพาะเอกสารที่ยาวกว่า 2000 ตัวอักษร
if embedder and len(content) > 2000:
    summary = await summarize_with_llm(content, title, embedder)
    if summary:
        final_content = summary
        results["llm_summarized"] += 1
```

---

## Fallback Behavior

### Embedding Failure

```
Ollama พร้อมใช้
    │
    ▼
embed(query) → เวกเตอร์ 768 มิติ
    │
    ▼
Qdrant search → dense_results
    │
    ▼
PostgreSQL FTS → fts_results
    │
    ▼
RRF Fusion → merged results

Ollama ไม่พร้อมใช้
    │
    ▼
EmbeddingError
    │
    ▼
Fallback: PostgreSQL FTS only → fts_results
```

### LLM Failure

```
Ollama พร้อมใช้ (มี qwen2.5:7b)
    │
    ▼
analyze_conflict() → {"is_conflict": true, "merged_content": "..."}
    │
    ▼
supersede เอกสารเก่าด้วยเนื้อหาที่ merge แล้ว

Ollama ไม่พร้อมใช้ (หรือ LLM request ล้มเหลว)
    │
    ▼
analyze_conflict() → None
    │
    ▼
detox ระบุ {"is_conflict": "potential", "reason": "LLM unavailable"}
    │
    ▼
ไม่แก้ไขข้อมูล (soft enforcement)
```

---

## ข้อควรระวัง

1. **MAX_CHUNK_CHARS = 4000** — ข้อความที่ยาวกว่า 4000 ตัวอักษรจะถูกตัดทอนก่อน embed
2. **Timeout 120 วินาทีสำหรับ LLM** — request ที่ใช้เวลานานกว่านี้จะ timeout
3. **Batch embed ทำตามลำดับ** — แม้จะมี semaphore=4 แต่ embed ทีละรายการ ไม่ได้ parallel อย่างแท้จริง
4. **content ตัดทอนเหลือ 2000 ตัวอักษร** สำหรับ conflict analysis และ 8000 ตัวอักษรสำหรับ summarization
5. **format="json"** — ส่งให้ Ollama เพื่อบังคับ JSON output แต่ยังต้อง parse เองเพราะ LLM อาจครอบด้วย markdown