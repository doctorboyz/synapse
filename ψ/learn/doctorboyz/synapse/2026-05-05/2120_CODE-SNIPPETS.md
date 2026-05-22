# Synapse v3 — Code Snippets

## 1. Main Entry Point — Boot Sequence

**File:** `src/main.py`

CLI dispatches two subcommands. `serve` launches uvicorn with FastAPI; `mcp` runs the MCP stdio server.

```python
def cli_main():
    parser = argparse.ArgumentParser(prog="synapse")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Start HTTP API server")
    sub.add_parser("mcp", help="Start MCP stdio server")
    args = parser.parse_args()

    if args.command == "serve":
        settings = Settings()
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)
    elif args.command == "mcp":
        from src.mcp.server import run_server
        asyncio.run(run_server())
    else:
        parser.print_help()
```

**FastAPI startup lifecycle:**

```python
@app.on_event("startup")
async def startup():
    global _pg, _qdrant
    settings = Settings()
    _pg = PgStore(settings)
    await _pg.connect()
    await _pg.init_schema()          # idempotent schema migration

    _qdrant = None
    try:
        _qdrant = QdrantStore(settings)
        await _qdrant.connect()
    except Exception:
        log.warning("Qdrant not available, running in FTS-only mode")

    embedder = OllamaEmbedder(settings)
    init_routes(_pg, _qdrant, embedder)   # wires globals into API router
```

**MCP server boot** (`src/mcp/server.py`):

```python
async def run_server():
    app = await create_app()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
```

Key pattern: Both boot paths share the same graceful-degradation approach for Qdrant — wrap the connect in try/except and fall back to `None`, which downstream code checks with `if self.qdrant:` guards.

---

## 2. Push Pipeline (Dual-Store Write)

**File:** `src/ingest/push.py`

The `Push` class orchestrates a dual-store write: first PostgreSQL (for dedup + FTS), then Qdrant (for vector indexing). The vector step is optional and non-fatal.

```python
async def push_text(self, title, content, scope="shared", doc_type="learning",
                    source_file=None, source_type="manual", ...,
                    concepts=None, tags=None, embed=True) -> dict:
    validate_doc_type(doc_type)

    result = await self.pg.add(
        title=title, content=content, scope=scope, doc_type=doc_type,
        source_file=source_file, source_type=source_type,
        source_project=source_project, oracle_name=oracle_name,
        brain_path=brain_path, brain_tier=brain_tier,
        concepts=concepts, tags=tags,
    )

    if result["status"] == "duplicate":       # early exit on content hash collision
        return result

    if embed and self.qdrant and self.embedder:
        try:
            vector = await self.embedder.embed(content)
            await self.qdrant.upsert(
                doc_id=result["id"], vector=vector, title=title,
                scope=scope, doc_type=doc_type,
                oracle_name=oracle_name, brain_tier=brain_tier,
                concepts=concepts,
            )
        except Exception as e:
            log.warning("Vector indexing failed: %s", e)
            result["status"] = "indexed_pg_only"  # partial success marker

    return result
```

**File-based push** auto-extracts oracle metadata from path conventions:

```python
async def push_file(self, file_path, scope=None, doc_type=None, embed=True) -> dict:
    path = Path(file_path)
    title = path.stem
    content = path.read_text(encoding="utf-8")

    meta = {}
    if scope is None:
        meta = extract_metadata(str(path), str(path.parent))
        scope = meta.get("scope", "shared")
    if doc_type is None and "doc_type" in meta:
        doc_type = meta["doc_type"]

    return await self.push_text(
        title=title, content=content, scope=scope,
        doc_type=doc_type or "learning",
        source_file=str(path), source_type="manual",
        oracle_name=meta.get("oracle_name"),
        brain_path=meta.get("brain_path"),
        brain_tier=meta.get("brain_tier"),
        embed=embed,
    )
```

---

## 3. Dedup Logic (content_hash)

**File:** `src/db/pg_store.py`

SHA-256 of content truncated to 16 hex chars, with a unique constraint on `(content_hash, scope)`.

```python
async def add(self, title, content, scope="shared", ...) -> dict:
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    # ...
    async with self.pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM knowledge_documents WHERE content_hash = $1 AND scope = $2",
            content_hash, scope,
        )
        if existing:
            return {"id": str(existing["id"]), "scope": scope, "status": "duplicate"}
        # ... INSERT
```

The SQL schema enforces:

```sql
UNIQUE(content_hash, scope)
```

---

## 4. Supersession (Versioned Knowledge Replacement)

**File:** `src/db/pg_store.py`

Never deletes old documents. Creates a new row, points the old row's `superseded_by` to it, and logs the transition.

```python
async def supersede(self, old_id, new_content, reason="updated", new_title=None) -> dict:
    async with self.pool.acquire() as conn:
        old_row = await conn.fetchrow(
            "SELECT * FROM knowledge_documents WHERE id = $1 AND superseded_by IS NULL",
            uuid.UUID(old_id),
        )
        # ... create new row, link old → new, log transition
```

Qdrant side uses soft-delete via `mark_superseded` (sets payload flag):

```python
# qdrant_store.py
async def mark_superseded(self, doc_id: str) -> None:
    try:
        await self.client.set_payload(
            collection_name=self._settings.qdrant_collection,
            payload={"superseded": True},
            points=[uuid.UUID(doc_id).hex],
        )
    except Exception:
        pass  # intentional: Qdrant is not the source of truth
```

---

## 5. Hybrid Search (Dense + FTS → RRF Fusion)

**File:** `src/retrieve/hybrid_search.py`

The core RRF algorithm:

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
            score = weight / (k + rank)            # RRF formula: w / (k + rank_position)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + score
            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    "id": doc_id, "title": doc.get("title", ""),
                    "scope": doc.get("scope", "shared"), ...
                }

    return [
        {**doc_info[doc_id], "score": score}
        for doc_id, score in sorted(rrf_scores.items(), key=lambda x: -x[1])
    ]
```

Search dispatch with graceful degradation:

```python
async def search(self, query, scope=None, doc_type=None, oracle=None,
                 source_project=None, concepts=None, limit=10, mode="hybrid") -> list[dict]:
    if mode == "dense":
        if not self.qdrant or not self.embedder:
            raise SearchError("Dense search requires Qdrant and OllamaEmbedder")
        vector = await self.embedder.embed(query)
        return await self.qdrant.search(vector, ...)

    if mode == "fts":
        return await self.pg.search_fts(query, ...)

    # Hybrid: both + RRF
    if not self.qdrant or not self.embedder:
        return await self.pg.search_fts(query, ...)   # fallback to FTS-only

    try:
        vector = await self.embedder.embed(query)
        dense_results = await self.qdrant.search(vector, ..., limit=limit * 2)
    except EmbeddingError as e:
        log.warning("Dense search failed, falling back to FTS: %s", e)
        return await self.pg.search_fts(query, ...)

    fts_results = await self.pg.search_fts(query, ..., limit=limit * 2)
    # ... merge and return
```

Default weights: `[0.6, 0.4]` (60% dense, 40% FTS).

---

## 6. Exponential Backoff Retry in Embedder

**File:** `src/embed/ollama.py`

```python
async def embed(self, text: str) -> list[float]:
    text = text[:MAX_CHUNK_CHARS]              # truncate to 4000 chars
    for attempt in range(self._max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self._model, "input": text},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["embeddings"][0]
        except (httpx.HTTPError, KeyError, IndexError) as e:
            if attempt == self._max_retries:
                raise EmbeddingError(f"Embedding failed after {attempt+1} attempts: {e}") from e
            wait = 0.5 * (2 ** attempt)          # 0.5s, 1s, 2s...
            log.warning("Embed retry %d/%d: %s", attempt + 1, self._max_retries, e)
            await asyncio.sleep(wait)
    raise EmbeddingError("Unreachable")
```

---

## 7. Oracle Path Convention (Auto-Metadata Extraction)

**File:** `src/ingest/oracle_paths.py`

```python
ORACLE_PATH_RULES: list[tuple[str, str, str]] = [
    # (path_pattern, doc_type, brain_tier)
    (r"ψ/memory/learnings/",       "learning",  "extrinsic"),
    (r"ψ/memory/retrospectives/",  "retro",     "extrinsic"),
    (r"ψ/outbox/",                 "handoff",   "extrinsic"),
    (r"κ/extrinsic/wisdom/knowledge/", "wisdom", "extrinsic"),
    (r"κ/extrinsic/wisdom/reference/", "reference", "extrinsic"),
    (r"κ/extrinsic/experience/learn/", "learning", "extrinsic"),
    (r"κ/extrinsic/experience/work/logs/", "log", "extrinsic"),
    (r"κ/intrinsic/instinct/",     "instinct",  "intrinsic"),
    (r"κ/intrinsic/identity/",     "instinct",  "intrinsic"),
    (r"κ/intrinsic/inherit/",      "instinct",  "intrinsic"),
]
```

---

## 8. Weighted tsvector with PostgreSQL Trigger

**File:** `src/db/schema.sql`

```sql
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

Title gets weight A (highest), content weight B, concepts weight C.

---

## 9. Dynamic Query Building with Parameterized SQL

**File:** `src/db/pg_store.py`

```python
async def search_fts(self, query, scope=None, doc_type=None, oracle=None,
                     source_project=None, limit=10) -> list[dict]:
    ts_query = " | ".join(query.split())     # OR all tokens
    conditions = ["superseded_by IS NULL", "search_vector @@ to_tsquery('english', $1)"]
    params: list = [ts_query]
    idx = 2

    if scope:
        conditions.append(f"scope = ${idx}")
        params.append(scope); idx += 1
    # ... dynamic WHERE building

    sql = f"""SELECT id, title, scope, doc_type, oracle_name, source_project,
                     ts_rank(search_vector, to_tsquery('english', $1)) AS rank
              FROM knowledge_documents
              WHERE {where}
              ORDER BY rank DESC LIMIT ${idx}"""
```

---

## 10. Trace Walking (BFS-style Knowledge Graph Traversal)

**File:** `src/db/pg_store.py`

```python
async def _trace_walk(self, conn, start_id, match_col, follow_col, relation, max_depth):
    results = []
    visited = {start_id}
    current_ids = [start_id]

    for _ in range(max_depth):
        if not current_ids:
            break
        # ... BFS with visited-set to prevent cycles
        # Supports direction parameterization (upstream vs downstream)
```

---

## 11. Error Handling Patterns

### Custom Exceptions

```python
# src/retrieve/hybrid_search.py
class SearchError(Exception):
    pass

# src/embed/ollama.py
class EmbeddingError(Exception):
    pass
```

### Qdrant Soft-Failure (Silent Pass)

PostgreSQL is the source of truth; Qdrant is a derived index. Failures are silently swallowed:

```python
async def mark_superseded(self, doc_id: str) -> None:
    try:
        await self.client.set_payload(...)
    except Exception:
        pass   # intentional: Qdrant is not the source of truth
```

### Hook Handler Degradation

```python
qdrant = None
embedder = None
try:
    qdrant = QdrantStore(settings)
    await qdrant.connect()
    embedder = OllamaEmbedder(settings)
    if not await embedder.check():
        embedder = None
except Exception:
    pass  # Qdrant/Ollama optional for hook ingestion
```

The hook handler health-checks the embedder (`embedder.check()`) and sets it to `None` if unavailable, then passes `embed=embedder is not None` to `push_text` so PG-only ingestion still succeeds.