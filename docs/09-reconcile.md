# 09 — Reconcile (Defrag + Detox)

> ระบบกู้คืนความสอดคล้องของข้อมูล: รวมเอกสารซ้ำ (Defrag) และตรวจจับ/แก้ไขข้อขัดแย้ง (Detox)

---

## ภาพรวม

Reconcile เป็นกระบวนการบำรุงรักษาคลังความรู้ ประกอบด้วย 2 ขั้นตอนหลัก:

```
synapse reconcile
        │
        ├── Defrag (กระทัดข้อมูลซ้ำ)
        │   └── ค้นหาเอกสารที่ title+scope เดียวกัน
        │   └── supersede เอกสารเก่า เก็บเอกสารใหม่สุด
        │
        └── Detox (ตรวจจับความขัดแย้ง)
            └── จับคู่เอกสารใน scope+doc_type เดียวกัน
            └── วิเคราะห์ด้วย LLM (qwen2.5:7b)
            └── หากขัดแย้ง → supersede ด้วยเนื้อหาที่ merge แล้ว
```

---

## การเรียกใช้

```bash
# รัน reconcile ทั้งหมด
synapse reconcile

# จำกัดเฉพาะ scope
synapse reconcile --scope myproject

# ทดลองดูผลโดยไม่แก้ไขจริง
synapse reconcile --dry-run
```

---

## Defrag — กระทัดข้อมูลซ้ำ

**ไฟล์:** `src/reconcile/defrag.py`

### หลักการ

ค้นหาเอกสารที่มี `title` และ `scope` เดียวกัน แล้ว supersede เอกสารที่เก่ากว่า เก็บเอกสารใหม่สุดไว้

### ขั้นตอนการทำงาน

1. ดึงเอกสารทั้งหมดใน scope (หรือทั้งหมดถ้าไม่ระบุ scope)
2. จัดกลุ่มตาม `(title, scope)`
3. สำหรับกลุ่มที่มีมากกว่า 1 เอกสาร:
   - เก็บเอกสารใหม่สุด (index 0 เพราะเรียงจาก newest)
   - supersede เอกสารที่เก่ากว่า
4. หาก `dry_run=True`: แสดงผลโดยไม่แก้ไขจริง

### ฟังก์ชัน

```python
async def defrag(
    pg: PgStore,
    scope: str | None = None,
    dry_run: bool = False,
) -> dict
```

### ผลลัพธ์

```json
{
  "duplicates_found": 3,
  "compacted": 3,
  "errors": 0,
  "groups": [
    {
      "title": "Error Handling",
      "scope": "shared",
      "count": 2,
      "keep": "uuid-newest",
      "supersede": ["uuid-older-1"],
      "action": "superseded"
    }
  ]
}
```

### กลไก Supersede

เมื่อ supersede เอกสารเก่า ระบบจะ:
1. สร้างเอกสารใหม่ด้วยเนื้อหาเดียวกัน (สำเนาของเอกสารเก่า)
2. ตั้ง `superseded_by` บนเอกสารเก่าให้ชี้ไปเอกสารใหม่
3. บันทึกใน `supersede_log` ด้วย reason: `"defrag_duplicate"`

**หมายเหตุ:** เนื้อหาของเอกสารใหม่คือสำเนาของเอกสารเก่า (ไม่มีการ merge เนื้อหา) เพราะจุดประสงค์คือรวมชื่อเดียวกัน ไม่ใช่ merge เนื้อหา

---

## Detox — ตรวจจับและแก้ไขความขัดแย้ง

**ไฟล์:** `src/reconcile/detox.py`

### หลักการ

จับคู่เอกสารที่อยู่ใน `scope` และ `doc_type` เดียวกัน ส่งให้ LLM วิเคราะห์ว่ามีความขัดแย้งหรือไม่ หากมี → สร้างเนื้อหาที่ merge แล้วและ supersede เอกสารเก่า

### ขั้นตอนการทำงาน

1. ดึงเอกสารทั้งหมดใน scope (หรือทั้งหมดถ้าไม่ระบุ) — จำกัด 100 รายการ
2. จับคู่เอกสารที่อยู่ใน `scope` + `doc_type` เดียวกัน
3. สำหรับแต่ละคู่:
   - ดึงเนื้อหาฉบับเต็มของทั้งสองเอกสาร (ตัดทอนเหลือ 2000 ตัวอักษร)
   - ส่งให้ LLM (qwen2.5:7b) วิเคราะห์ผ่าน `analyze_conflict()`
   - หาก LLM ระบุว่ามีความขัดแย้งและมี `merged_content`:
     - supersede เอกสารที่ระบุใน `supersede_id` ด้วยเนื้อหาที่ merge แล้ว
     - บันทึกใน `supersede_log` ด้วย reason: `"detox_conflict: <reason>"`
4. หาก LLM ไม่พร้อมใช้ → ระบุ `is_conflict: "potential"` แต่ไม่แก้ไข

### ฟังก์ชัน

```python
async def detox(
    pg: PgStore,
    qdrant: QdrantStore | None = None,
    embedder: OllamaEmbedder | None = None,
    settings=None,
    scope: str | None = None,
    dry_run: bool = False,
) -> dict
```

### ผลลัพธ์

```json
{
  "conflicts_found": 1,
  "conflicts": [
    {
      "doc_a": {"id": "uuid-a", "title": "Error Handling", "scope": "shared"},
      "doc_b": {"id": "uuid-b", "title": "Error Patterns", "scope": "shared"},
      "analysis": {
        "is_conflict": true,
        "conflict_type": "contradiction",
        "reason": "Document A says to use early returns, Document B says to use try/catch blocks",
        "supersede_id": "a",
        "merged_content": "Combined guidance: use early returns for simple cases..."
      },
      "action": "superseded",
      "new_id": "uuid-merged"
    }
  ],
  "resolutions": [
    {
      "old_id": "uuid-a",
      "new_id": "uuid-merged",
      "reason": "contradiction: different error handling advice"
    }
  ],
  "errors": 0
}
```

### กรณี LLM ไม่พร้อมใช้

```json
{
  "conflicts_found": 2,
  "conflicts": [
    {
      "doc_a": {"id": "uuid-a", "title": "...", "scope": "shared"},
      "doc_b": {"id": "uuid-b", "title": "...", "scope": "shared"},
      "analysis": {"is_conflict": "potential", "reason": "LLM unavailable for analysis"}
    }
  ],
  "resolutions": [],
  "errors": 0
}
```

---

## LLM Conflict Analysis

**ไฟล์:** `src/reconcile/llm.py`

### Prompt Template

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
  "reason": "brief explanation",
  "supersede_id": "a_or_b_or_none",
  "merged_content": "if conflict, provide merged/resolved content. if no conflict, empty string"
}

Be conservative: only mark as conflict if the documents genuinely contradict each other.
Overlapping information is not a conflict unless one document contradicts the other.
```

### ฟังก์ชัน

```python
async def analyze_conflict(
    doc_a: dict,    # {"title": ..., "content": ...}
    doc_b: dict,    # {"title": ..., "content": ...}
    settings,       # Settings object (has ollama_url)
    model: str = "qwen2.5:7b",
) -> dict | None
```

**ผลลัพธ์ที่คาดหวัง:**

| Key | Type | คำอธิบาย |
|-----|------|----------|
| `is_conflict` | bool | มีความขัดแย้งหรือไม่ |
| `conflict_type` | str | contradiction / overlap / outdated / none |
| `reason` | str | คำอธิบายสั้น |
| `supersede_id` | str | "a" / "b" / "none" — เอกสารไหนควรถูก supersede |
| `merged_content` | str | เนื้อหาที่ merge แล้ว (ว่างถ้าไม่มี conflict) |

### การแก้ไข JSON Response

LLM อาจครอบ JSON ด้วย markdown code blocks:

```python
if "```json" in text:
    text = text.split("```json")[1].split("```")[0].strip()
elif "```" in text:
    text = text.split("```")[1].split("```")[0].strip()
```

### summarize_content()

ฟังก์ชันสำหรับสรุปเนื้อหาเดี่ยว:

```python
async def summarize_content(
    content: str,
    title: str,
    settings,
    model: str = "qwen2.5:7b",
) -> str | None
```

ใช้ใน `init_scan.py` สำหรับสรุปเอกสารที่ยาวกว่า 2000 ตัวอักษร

---

## การเรียกใช้รวม (reconcile)

**ไฟล์:** `src/reconcile/__init__.py`

```python
async def reconcile(
    pg,
    qdrant=None,
    embedder=None,
    settings=None,
    scope: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run full reconcile: defrag + detox."""
    defrag_result = await defrag(pg, scope=scope, dry_run=dry_run)
    detox_result = await detox(
        pg, qdrant=qdrant, embedder=embedder, settings=settings,
        scope=scope, dry_run=dry_run,
    )

    return {
        "defrag": defrag_result,
        "detox": detox_result,
        "scope": scope or "all",
        "dry_run": dry_run,
    }
```

รัน defrag ก่อน แล้วจึงรัน detox ตามลำดับ เพื่อให้ detox ทำงานกับข้อมูลที่ผ่านการกระทัดแล้ว

---

## ข้อควรระวัง

1. **Defrag ใช้ title+scope เป็น proxy** — ไม่ได้ใช้ content_hash โดยตรงเพราะ `list_docs()` ไม่คืน content_hash อาจรวมเอกสารที่มีเนื้อหาต่างกันแต่ชื่อเดียวกัน
2. **Detox จำกัด 100 เอกสาร** — ป้องกันการวิเคราะห์คู่เอกสารจำนวนมากเกินไป ทำให้ O(n^2) pairs
3. **เนื้อหาถูกตัดทอนเหลือ 2000 ตัวอักษร** — เมื่อส่งให้ LLM เพื่อวิเคราะห์
4. **LLM ต้องพร้อมใช้** — หาก Ollama ไม่พร้อม detox จะระบุว่ามี conflict เป็น "potential" แต่ไม่แก้ไข
5. **dry_run ไม่แก้ไขข้อมูลจริง** — แสดงผลว่าจะทำอะไรโดยไม่ supersede จริง