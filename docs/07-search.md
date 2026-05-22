# 07 — Hybrid Search Architecture

> ระบบค้นหาแบบผสมของ Synapse: Qdrant dense vectors + PostgreSQL tsvector รวมด้วย Reciprocal Rank Fusion

---

## ภาพรวม

Synapse ใช้ระบบค้นหาแบบ hybrid ที่ผสานผลลัพธ์จากสอง engine เข้าด้วยกัน:

1. **Dense search** — ค้นหาด้วยเวกเตอร์ผ่าน Qdrant (semantic similarity)
2. **FTS search** — ค้นหาด้วย full-text search ผ่าน PostgreSQL tsvector (keyword matching)
3. **RRF fusion** — รวมคะแนนจากทั้งสอง engine ด้วยสูตร Reciprocal Rank Fusion

```
Query "docker networking"
        │
        ▼
  ┌─────────────┐
  │  OllamaEmbed │  ← embed query → 768d vector
  └──────┬──────┘
         │
    ┌────▼────┐          ┌──────────┐
    │ Qdrant  │          │PostgreSQL│
    │  dense  │          │   FTS    │
    └────┬────┘          └─────┬────┘
         │                     │
    dense_results         fts_results
         │                     │
         └──────┬──────────────┘
                ▼
      ┌─────────────────┐
      │  RRF Fusion     │  weights=[0.6, 0.4], k=60
      └────────┬────────┘
               ▼
         merged results
```

---

## โหมดการค้นหา

รองรับ 3 โหมด กำหนดด้วยพารามิเตอร์ `mode`:

| โหมด | พฤติกรรม | ข้อกำหนด |
|---|---|---|
| `"hybrid"` (default) | embed query → ค้น Qdrant + FTS → รวมด้วย RRF | หาก Qdrant/Embedder ไม่พร้อม → fallback เป็น FTS-only |
| `"dense"` | embed query → ค้น Qdrant เท่านั้น | ต้องมี Qdrant + Embedder โยน `SearchError` หากขาด |
| `"fts"` | ค้นหาด้วย PostgreSQL tsvector เท่านั้น | ไม่ต้องการ Qdrant หรือ Embedder |

### ตัวอย่างการใช้งาน

```python
from src.retrieve.hybrid_search import HybridSearch
from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.config import Settings

settings = Settings()
pg = PgStore(settings)
await pg.connect()

qdrant = QdrantStore(settings)
await qdrant.connect()

embedder = OllamaEmbedder(settings)

search = HybridSearch(pg, qdrant, embedder)

# Hybrid search (default)
results = await search.search("docker networking patterns", limit=10)

# Dense-only search (semantic)
results = await search.search("docker networking patterns", mode="dense")

# FTS-only search (keyword)
results = await search.search("docker networking patterns", mode="fts")
```

### CLI

```bash
# Hybrid (default)
synapse search "docker networking" --limit 10

# Dense-only
synapse search "docker networking" --mode dense

# FTS-only
synapse search "docker networking" --mode fts

# กรองตาม scope, doc_type, oracle
synapse search "error handling" --scope myproject --doc-type pattern --limit 5
```

---

## Reciprocal Rank Fusion (RRF)

### สูตร

```
score(doc) = sum  weight_i / (k + rank_i)
```

- `weight_i` — น้ำหนักของ result list ที่ i (default: `[0.6, 0.4]` สำหรับ dense และ FTS ตามลำดับ)
- `k` — ค่าคงที่ป้องกัน rank สูงมีน้ำหนักเยอะเกินไป (default: `60`)
- `rank_i` — ลำดับของ doc ใน result list ที่ i (เริ่มจาก 1)

### การตั้งค่า

```python
# ค่า default
search = HybridSearch(pg, qdrant, embedder,
                      weights=[0.6, 0.4],  # 60% dense, 40% FTS
                      rrf_k=60)

# เปลี่ยนน้ำหนัก (เช่น เน้น FTS มากขึ้น)
search = HybridSearch(pg, qdrant, embedder,
                      weights=[0.4, 0.6],  # 40% dense, 60% FTS
                      rrf_k=60)
```

หรือผ่าน environment variable:

```bash
export SEARCH_WEIGHTS="0.6,0.4"   # น้ำหนัก: dense, FTS
# search_rrf_k ไม่มี env var — ใช้ค่า default 60
```

### การคำนวณตัวอย่าง

สมมติ query = "docker" ได้ผลลัพธ์:

**Dense results (Qdrant):**
| Rank | Doc ID | น้ำหนัก 0.6 |
|---|---|---|
| 1 | doc-A | 0.6 / (60 + 1) = 0.00984 |
| 2 | doc-B | 0.6 / (60 + 2) = 0.00968 |
| 3 | doc-C | 0.6 / (60 + 3) = 0.00952 |

**FTS results (PostgreSQL):**
| Rank | Doc ID | น้ำหนัก 0.4 |
|---|---|---|
| 1 | doc-B | 0.4 / (60 + 1) = 0.00656 |
| 2 | doc-D | 0.4 / (60 + 2) = 0.00645 |
| 3 | doc-A | 0.4 / (60 + 3) = 0.00635 |

**ผลลัพธ์รวม:**
| Doc ID | Dense | FTS | คะแนนรวม |
|---|---|---|---|
| doc-A | 0.00984 | 0.00635 | **0.01619** |
| doc-B | 0.00968 | 0.00656 | **0.01624** |
| doc-D | — | 0.00645 | **0.00645** |
| doc-C | 0.00952 | — | **0.00952** |

เรียงตามคะแนน: doc-B > doc-A > doc-C > doc-D

### โค้ด RRF

```python
def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    weights: list[float] | None = None,
    k: int = 60,
) -> list[dict]:
    if weights is None:
        weights = [1.0 / len(result_lists)] * len(result_lists)

    rrf_scores: dict[str, float] = {}
    doc_info: dict[str, dict] = {}

    for weight, results in zip(weights, result_lists):
        for rank, doc in enumerate(results, start=1):
            doc_id = doc["id"]
            score = weight / (k + rank)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + score

            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    "id": doc_id,
                    "title": doc.get("title", ""),
                    "scope": doc.get("scope", "shared"),
                    "doc_type": doc.get("doc_type", ""),
                    "oracle_name": doc.get("oracle_name"),
                    "source_project": doc.get("source_project"),
                }

    return [
        {**doc_info[doc_id], "score": score}
        for doc_id, score in sorted(rrf_scores.items(), key=lambda x: -x[1])
    ]
```

---

## FTS Fallback

ระบบ hybrid search ออกแบบให้ทำงานได้แม้ Qdrant หรือ Ollama ไม่พร้อมใช้งาน:

### ลำดับ fallback

```
1. Qdrant + Ollama พร้อม → hybrid (dense + FTS + RRF)
2. Qdrant หรือ Ollama ไม่พร้อม → FTS-only
3. EmbeddingError ระหว่าง embed query → FTS-only
4. mode="dense" แต่ Qdrant/Ollama ไม่พร้อม → โยน SearchError
```

### โค้ด fallback

```python
async def search(self, query, scope=None, doc_type=None, oracle=None,
                 source_project=None, concepts=None, limit=10, mode="hybrid"):

    # mode="fts" → ค้น PostgreSQL เท่านั้น
    if mode == "fts":
        return await self.pg.search_fts(query, scope=scope, ...)

    # mode="dense" → ต้องมี Qdrant + Embedder
    if mode == "dense":
        if not self.qdrant or not self.embedder:
            raise SearchError("Dense search requires Qdrant and OllamaEmbedder")
        vector = await self.embedder.embed(query)
        return await self.qdrant.search(vector, ...)

    # mode="hybrid" → ลองทั้งสอง engine
    if not self.qdrant or not self.embedder:
        # Fallback: Qdrant ไม่พร้อม → FTS-only
        return await self.pg.search_fts(query, scope=scope, ...)

    try:
        vector = await self.embedder.embed(query)
        dense_results = await self.qdrant.search(vector, ...)
    except EmbeddingError as e:
        # Fallback: embed ล้มเหลว → FTS-only
        log.warning("Dense search failed, falling back to FTS: %s", e)
        return await self.pg.search_fts(query, scope=scope, ...)

    fts_results = await self.pg.search_fts(query, scope=scope, ...)

    # รวมด้วย RRF
    merged = reciprocal_rank_fusion(
        [dense_results, fts_results],
        weights=self._weights,
        k=self._rrf_k,
    )
    return merged[:limit]
```

### การสร้าง HybridSearch ที่รองรับ fallback

```python
# Qdrant ไม่พร้อม → ทำงานในโหมด FTS-only อัตโนมัติ
pg = PgStore(settings)
await pg.connect()

qdrant = None  # Qdrant ไม่พร้อมใช้งาน
embedder = None  # Ollama ไม่พร้อมใช้งาน

# สร้าง HybridSearch — จะ fallback เป็น FTS-only อัตโนมัติ
search = HybridSearch(pg, qdrant=None, embedder=None)

# ค้นหา — จะใช้ FTS-only โดยไม่โยน error
results = await search.search("test query")  # → FTS-only
```

---

## Cache Layer (LRU + TTL)

**ไฟล์:** `src/cache.py`

### ภาพรวม

`SearchCache` เป็น cache สำหรับผลลัพธ์การค้นหา ใช้โครงสร้าง LRU (Least Recently Used) + TTL (Time To Live)

```
Search request
      │
      ▼
  Cache hit? ──Yes──→ Return cached results
      │
      No
      │
      ▼
  Execute search (hybrid/dense/fts)
      │
      ▼
  Store results in cache
      │
      ▼
  Return results
```

### โครงสร้าง Cache Key

```python
key = f"{query}||{scope}||{mode}||{limit}"
# ตัวอย่าง: "docker||myproject||hybrid||10"
# scope=None → "*"
```

### Configuration

| Parameter | Default | Environment Variable | คำอธิบาย |
|---|---|---|---|
| `max_size` | `1000` | `CACHE_MAX_SIZE` | จำนวนรายการสูงสุดใน cache |
| `ttl` | `300` | `CACHE_TTL` | TTL ในวินาที (5 นาที) |

```python
from src.cache import SearchCache

cache = SearchCache(max_size=1000, ttl=300)
search = HybridSearch(pg, qdrant, embedder, cache=cache)
```

### เมธอด

| เมธอด | ลายเซ็น | คำอธิบาย |
|---|---|---|
| `get()` | `get(query, scope=None, mode="hybrid", limit=10) -> list or None` | ดึงผลลัพธ์จาก cache คืน `None` หากไม่พบหรือหมดอายุ |
| `put()` | `put(query, results, scope=None, mode="hybrid", limit=10)` | เก็บผลลัพธ์ใน cache ถ้าเต็ม → ลบรายการเก่าที่สุด (LRU) |
| `invalidate()` | `invalidate(query=None, scope=None) -> int` | ลบ cache ตามเงื่อนไข คืนจำนวนรายการที่ลบ |
| `clear()` | `clear()` | ลบ cache ทั้งหมด |
| `stats()` | `stats() -> dict` | คืน `{size, max_size, ttl}` |

### Thread Safety

`SearchCache` ใช้ `threading.Lock` เพื่อให้ปลอดภัยในสภาพแวดล้อม multi-threaded ทุกการเข้าถึง cache ถูกคุ้มครองด้วย lock

### LRU Eviction

เมื่อ cache เต็ม (`len(cache) > max_size`) จะลบรายการที่เก่าที่สุดก่อน:

```python
while len(self._cache) > self._max_size:
    self._cache.popitem(last=False)  # ลบตัวแรก (เก่าสุด)
```

### Cache Invalidation

```python
# ลบ cache ทั้งหมด
count = cache.invalidate()

# ลบ cache เฉพาะ scope
count = cache.invalidate(scope="myproject")

# ลบ cache เฉพาะ query + scope
count = cache.invalidate(query="docker networking", scope="myproject")
```

---

## Cross-Project Search (search_cross_scope)

### ภาพรวม

`search_cross_scope` ค้นหาข้อมูลข้ามหลาย scope โดยรวมผลลัพธ์จากแต่ละ scope เข้าด้วยกัน โดยเลือกผลลัพธ์ที่มีคะแนนสูงสุดสำหรับแต่ละ doc_id

### โค้ด

```python
async def search_cross_scope(
    self,
    query: str,
    scopes: list[str],
    limit: int = 10,
    mode: str = "hybrid",
) -> list[dict]:
    all_results: dict[str, dict] = {}
    for scope in scopes:
        results = await self.search(
            query=query, scope=scope, limit=limit * 2, mode=mode,
        )
        for r in results:
            doc_id = r["id"]
            if doc_id not in all_results or r["score"] > all_results[doc_id]["score"]:
                all_results[doc_id] = r

    sorted_results = sorted(all_results.values(), key=lambda x: -x["score"])
    return sorted_results[:limit]
```

### ตัวอย่างการใช้งาน

```python
results = await search.search_cross_scope(
    query="error handling patterns",
    scopes=["project-a", "project-b", "shared"],
    limit=10,
    mode="hybrid"
)
```

### CLI

```bash
synapse search-cross "error handling" --scopes "project-a,project-b,shared" --limit 10
```

### กลไกการรวมผลลัพธ์

1. ค้นหาในแต่ละ scope ด้วย `limit * 2` (ดึงมากกว่าปกติเพื่อให้มีตัวเลือกมากขึ้น)
2. สำหรับแต่ละ doc_id ที่ปรากฏในหลาย scope → เก็บผลลัพธ์ที่มีคะแนนสูงสุด
3. เรียงลำดับตามคะแนนจากมากไปน้อย
4. ตัดผลลัพธ์ให้เหลือ `limit` รายการ

---

## Dense Search (Qdrant)

### กลไกการค้นหา

1. แปลง query เป็นเวกเตอร์ 768 มิติด้วย `OllamaEmbedder.embed()`
2. ส่งเวกเตอร์ไป Qdrant พร้อม payload filter
3. Qdrant คืนผลลัพธ์เรียงตาม cosine similarity

### Payload Filtering

Qdrant รองรับการกรองด้วย payload fields:

```python
conditions = [
    FieldCondition(key="superseded", match=MatchValue(value=False)),
    FieldCondition(key="scope", match=MatchValue(value="myproject")),
    FieldCondition(key="doc_type", match=MatchValue(value="pattern")),
]
```

### ข้อจำกัด

- ต้องมี Qdrant server ทำงานอยู่ (`http://localhost:6333`)
- ต้องมี Ollama พร้อมใช้งานสำหรับ embed
- หากขาดอย่างใดอย่างหนึ่ง → fallback เป็น FTS อัตโนมัติ

---

## FTS Search (PostgreSQL tsvector)

### การสร้าง tsvector

PostgreSQL trigger `trg_search_vector` สร้าง `search_vector` อัตโนมัติจาก:

| ฟิลด์ | Weight | คำอธิบาย |
|---|---|---|
| `title` | `A` (สูงสุด) | ชื่อเอกสาร — มีน้ำหนักสูงสุด |
| `content` | `B` | เนื้อหาเอกสาร |
| `concepts` | `C` | concepts (JSONB text) |

```sql
-- Trigger function
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

### การค้นหา

```python
async def search_fts(self, query, scope=None, doc_type=None, oracle=None,
                     source_project=None, limit=10):
    # แปลง query: "docker networking" → "docker | networking"
    ts_query = " | ".join(query.split())

    # กรองเฉพาะเอกสารที่ยังไม่ถูก supersede
    conditions = ["superseded_by IS NULL", "search_vector @@ to_tsquery('english', $1)"]

    # เรียงตาม ts_rank DESC
    sql = """SELECT id, title, scope, doc_type, oracle_name, source_project,
                     ts_rank(search_vector, to_tsquery('english', $1)) AS rank
              FROM knowledge_documents
              WHERE {where}
              ORDER BY rank DESC
              LIMIT ${idx}"""
```

### GIN Index

```sql
CREATE INDEX IF NOT EXISTS idx_doc_search
ON knowledge_documents USING GIN(search_vector);
```

GIN index ช่วยให้การค้นหา tsvector มีประสิทธิภาพสูง โดยเฉพาะกับข้อมูลจำนวนมาก

---

## ข้อควรระวัง

1. **ผลลัพธ์ FTS มีคะแนนไม่เท่ากันกับ dense** — RRF แก้ปัญหานี้โดยใช้ rank แทน raw score
2. **Cache ไม่ได้ตามการเปลี่ยนแปลงข้อมูลอัตโนมัติ** — ต้องเรียก `cache.invalidate()` เมื่อมีการ push/supersede
3. **search_cross_scope ค้นหาแบบ sequential** — แต่ละ scope ค้นหาทีละอัน หากมี scope จำนวนมากอาจช้า
4. **Dense search ดึง `limit * 2` รายการ** — เพื่อให้มีตัวเลือกเพียงพอสำหรับ RRF fusion