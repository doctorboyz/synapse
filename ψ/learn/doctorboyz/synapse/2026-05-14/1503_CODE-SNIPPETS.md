# Synapse v3 — Code Snippets Reference

> Practical reference for developers working on the Synapse hybrid-knowledge codebase.
> Generated from source exploration on 2026-05-14.

---

## Table of Contents

1. [Entry Points](#1-entry-points)
2. [Configuration & Settings](#2-configuration--settings)
3. [Data Stores](#3-data-stores)
4. [Embedding & LLM](#4-embedding--llm)
5. [Ingestion Pipeline](#5-ingestion-pipeline)
6. [Retrieval & Search](#6-retrieval--search)
7. [Reconciliation](#7-reconciliation)
8. [Project Registry & Scheduling](#8-project-registry--scheduling)
9. [Daemon & Local-Only Enforcement](#9-daemon--local-only-enforcement)
10. [MCP Server](#10-mcp-server)
11. [HTTP API](#11-http-api)
12. [Hooks Installer](#12-hooks-installer)
13. [Schema](#13-schema)
14. [Patterns & Idioms](#14-patterns--idioms)

---

## 1. Entry Points

### 1.1 FastAPI App + CLI (`src/main.py`)

**Startup / shutdown lifecycle** (lines 29-75):

```python
@app.on_event("startup")
async def startup():
    global _pg, _qdrant, _scheduler

    settings = Settings()
    _pg = PgStore(settings)
    await _pg.connect()
    await _pg.init_schema()

    from src.registry import restore_registry_backup
    await restore_registry_backup(_pg)

    _qdrant = None
    try:
        _qdrant = QdrantStore(settings)
        await _qdrant.connect()
    except Exception:
        log.warning("Qdrant not available, running in FTS-only mode")
        _qdrant = None

    embedder = OllamaEmbedder(settings)
    init_routes(_pg, _qdrant, embedder)

    if settings.scan_interval > 0 or settings.reconcile_hour >= 0:
        from src.scheduler import TaskScheduler
        _scheduler = TaskScheduler(...)
        await _scheduler.start()
```

**CLI dispatch table** (lines 561-584):

```python
COMMAND_DISPATCH = {
    "serve": None,   # handled separately
    "mcp": None,     # handled separately
    "push": _cmd_push,
    "search": _cmd_search,
    "get": _cmd_get,
    "list": _cmd_list,
    "scope": _cmd_scope,
    "stats": _cmd_stats,
    "supersede": _cmd_supersede,
    "trace": _cmd_trace,
    "trace-chain": _cmd_trace_chain,
    "concepts": _cmd_concepts,
    "init": _cmd_init,
    "reconcile": _cmd_reconcile,
    "register": _cmd_register,
    "unregister": _cmd_unregister,
    "projects": _cmd_projects,
    "search-cross": _cmd_search_cross,
    "stop": _cmd_stop,
    "status": _cmd_status,
    "scan": _cmd_scan,
    "install-hooks": _cmd_install_hooks,
}
```

**CLI main** (lines 587-605):

```python
def cli_main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "serve":
        settings = Settings()
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)
    elif args.command == "mcp":
        from src.mcp.server import run_server
        asyncio.run(run_server())
    elif args.command in COMMAND_DISPATCH and COMMAND_DISPATCH[args.command]:
        handler = COMMAND_DISPATCH[args.command]
        asyncio.run(handler(args))
    else:
        parser.print_help()
```

### 1.2 CLI Components Setup (`src/cli.py`)

**Components dataclass + async lifecycle** (lines 19-100):

```python
class Components:
    def __init__(self, settings, pg, qdrant, embedder, push, search):
        self.settings = settings
        self.pg = pg
        self.qdrant = qdrant
        self.embedder = embedder
        self.push = push
        self.search = search

async def get_components() -> Components:
    settings = Settings()
    pg = PgStore(settings)
    await pg.connect()

    qdrant = None
    try:
        qdrant = QdrantStore(settings)
        await qdrant.connect()
    except Exception:
        log.warning("Qdrant not available, running in FTS-only mode")
        qdrant = None

    embedder = None
    try:
        embedder = OllamaEmbedder(settings)
    except Exception:
        log.warning("Ollama not available, running without embeddings")
        embedder = None

    push = Push(pg, qdrant, embedder)
    search = HybridSearch(pg, qdrant, embedder, settings.search_weights, settings.search_rrf_k)
    return Components(settings, pg, qdrant, embedder, push, search)


def cli_command(func):
    """Decorator for async CLI commands: handles setup/teardown and errors."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        async def run():
            components = await get_components()
            try:
                result = await func(components, *args, **kwargs)
                output(result)
            except Exception as e:
                output({"error": str(e), "command": func.__name__})
                sys.exit(1)
            finally:
                await cleanup(components)
        asyncio.run(run())
    return wrapper
```

---

## 2. Configuration & Settings

### 2.1 Settings Dataclass (`src/config.py`)

**Env-var driven dataclass with YAML reload** (lines 14-106):

```python
@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        os.getenv("SYNAPSE_DB_URL", "postgresql://admin:88888888@localhost:5432/synapse")
    ))
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333"))
    qdrant_collection: str = field(default_factory=lambda: os.getenv("SYNAPSE_QDRANT_COLLECTION", "synapse_vectors"))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "nomic-embed-text"))
    embedding_dim: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_DIM", "768")))
    embedding_timeout: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_TIMEOUT", "30")))
    api_host: str = field(default_factory=lambda: os.getenv("SYNAPSE_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("SYNAPSE_PORT", "8420")))
    log_level: str = field(default_factory=lambda: os.getenv("SYNAPSE_LOG_LEVEL", "INFO"))
    search_weights: list[float] = field(default_factory=lambda: [
        float(x) for x in os.getenv("SEARCH_WEIGHTS", "0.6,0.4").split(",")
    ])
    search_rrf_k: int = 60
    cache_ttl: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL", "300")))
    cache_max_size: int = field(default_factory=lambda: int(os.getenv("CACHE_MAX_SIZE", "1000")))
    daemon_pid_file: str = field(default_factory=lambda: os.getenv(
        "SYNAPSE_PID_FILE", str(Path.home() / ".synapse" / "synapse.pid")
    ))
    scan_interval: int = field(default_factory=lambda: int(os.getenv("SYNAPSE_SCAN_INTERVAL", "0")))
    reconcile_hour: int = field(default_factory=lambda: int(os.getenv("SYNAPSE_RECONCILE_HOUR", "2")))
    config_path: str = field(default_factory=lambda: os.getenv("SYNAPSE_CONFIG", ""))

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> "Settings":
        if path is None:
            path = DEFAULT_CONFIG_PATH
        path = Path(path)
        settings = cls()
        if not path.exists():
            return settings
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            for key, value in config.items():
                if hasattr(settings, key) and value is not None:
                    setattr(settings, key, value)
        except ImportError:
            log.warning("PyYAML not installed, skipping config file")
        except Exception as e:
            log.warning("Failed to load config from %s: %s", path, e)
        return settings

    def reload(self) -> None:
        """Re-read settings from env vars + config file (for SIGHUP)."""
        new_settings = Settings.from_yaml(self.config_path or None)
        for key in vars(new_settings):
            if key != "config_path":
                setattr(self, key, getattr(new_settings, key))
        log.info("Configuration reloaded")
```

---

## 3. Data Stores

### 3.1 PostgreSQL Store (`src/db/pg_store.py`)

**Connection pool + schema init** (lines 13-36):

```python
class PgStore:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._settings.database_url, min_size=2, max_size=10
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def init_schema(self) -> None:
        schema_path = __file__.replace("pg_store.py", "schema.sql")
        with open(schema_path) as f:
            sql = f.read()
        async with self._pool.acquire() as conn:
            await conn.execute(sql)
```

**Add with dedup by (content_hash, scope)** (lines 46-109):

```python
async def add(self, title: str, content: str, scope: str = "shared", ...) -> dict:
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    concepts_json = json.dumps(concepts or [])
    tags_json = json.dumps(tags or [])

    async with self.pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM knowledge_documents WHERE content_hash = $1 AND scope = $2",
            content_hash, scope,
        )
        if existing:
            return {"id": str(existing["id"]), "scope": scope, "status": "duplicate"}

        row = await conn.fetchrow(
            """INSERT INTO knowledge_documents ... RETURNING id""",
            title, content, content_hash, scope, ...,
        )
        doc_id = str(row["id"])

        # Increment scope_registry doc_count
        await conn.execute(
            """INSERT INTO scope_registry (name, doc_count)
               VALUES ($1, 1)
               ON CONFLICT (name) DO UPDATE SET doc_count = scope_registry.doc_count + 1""",
            scope,
        )
        # ... concept linking omitted for brevity
    return {"id": doc_id, "scope": scope, "status": "indexed"}
```

**Supersede (never delete)** (lines 139-177):

```python
async def supersede(self, old_id: str, new_content: str, reason: str = "updated",
                    new_title: str | None = None) -> dict:
    async with self.pool.acquire() as conn:
        old_row = await conn.fetchrow(
            "SELECT * FROM knowledge_documents WHERE id = $1 AND superseded_by IS NULL",
            uuid.UUID(old_id),
        )
        if not old_row:
            raise ValueError(f"Document {old_id} not found or already superseded")

        title = new_title or old_row["title"]
        content_hash = hashlib.sha256(new_content.encode()).hexdigest()[:16]

        new_row = await conn.fetchrow(
            """INSERT INTO knowledge_documents ... RETURNING id""",
            title, new_content, content_hash, old_row["scope"], ...,
        )

        await conn.execute(
            "UPDATE knowledge_documents SET superseded_by = $1, updated_at = NOW() WHERE id = $2",
            new_row["id"], uuid.UUID(old_id),
        )

        await conn.execute(
            """INSERT INTO supersede_log (old_id, new_id, reason) VALUES ($1, $2, $3)""",
            uuid.UUID(old_id), new_row["id"], reason,
        )

    return {"id": str(new_row["id"]), "superseded": old_id, "status": "superseded"}
```

**FTS search with dynamic WHERE** (lines 181-236):

```python
async def search_fts(self, query: str, ..., limit: int = 10) -> list[dict]:
    ts_query = " | ".join(query.split())
    conditions = ["superseded_by IS NULL", "search_vector @@ to_tsquery('english', $1)"]
    params: list = [ts_query]
    idx = 2

    if scope:
        conditions.append(f"scope = ${idx}")
        params.append(scope)
        idx += 1
    # ... more filters

    params.append(limit)
    where = " AND ".join(conditions)

    sql = f"""SELECT id, title, scope, doc_type, oracle_name, source_project,
                     ts_rank(search_vector, to_tsquery('english', $1)) AS rank
              FROM knowledge_documents
              WHERE {where}
              ORDER BY rank DESC
              LIMIT ${idx}"""

    async with self.pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return [...]
```

**Trace chain BFS walk** (lines 280-333):

```python
async def get_trace_chain(self, doc_id: str, direction: str = "both", max_depth: int = 5, ...) -> list[dict]:
    results = []
    async with self.pool.acquire() as conn:
        if direction in ("upstream", "both"):
            rows = await self._trace_walk(conn, doc_id, "target_id", "source_id", relation, max_depth)
            results.extend(rows)
        if direction in ("downstream", "both"):
            rows = await self._trace_walk(conn, doc_id, "source_id", "target_id", relation, max_depth)
            results.extend(rows)
    return results

async def _trace_walk(self, conn, start_id: str, match_col: str, follow_col: str,
                      relation: str | None, max_depth: int) -> list[dict]:
    results = []
    visited = {start_id}
    current_ids = [start_id]

    for depth in range(max_depth):
        if not current_ids:
            break
        rel_filter = f" AND t.relation = '{relation}'" if relation else ""
        placeholders = ", ".join(f"${i+1}" for i in range(len(current_ids)))
        sql = f"""SELECT t.source_id, t.target_id, t.relation, t.confidence, kd.id, kd.title, kd.doc_type
                  FROM trace t
                  JOIN knowledge_documents kd ON kd.id = t.{follow_col}
                  WHERE t.{match_col} IN ({placeholders}){rel_filter}
                    AND kd.superseded_by IS NULL"""
        rows = await conn.fetch(sql, *[uuid.UUID(cid) for cid in current_ids])
        # ... build next_ids, append results
    return results
```

### 3.2 Qdrant Store (`src/db/qdrant_store.py`)

**Auto-create collection on connect** (lines 16-34):

```python
class QdrantStore:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._client: AsyncQdrantClient | None = None

    async def connect(self) -> None:
        self._client = AsyncQdrantClient(url=self._settings.qdrant_url)
        try:
            await self._client.get_collection(self._settings.qdrant_collection)
        except Exception:
            await self._client.create_collection(
                collection_name=self._settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=self._settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
```

**Payload-filtered vector search** (lines 82-126):

```python
async def search(self, vector: list[float], ..., limit: int = 10) -> list[dict]:
    conditions = [FieldCondition(key="superseded", match=MatchValue(value=False))]
    if scope:
        conditions.append(FieldCondition(key="scope", match=MatchValue(value=scope)))
    if doc_type:
        conditions.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    # ... oracle, source_project, concepts filters

    search_filter = Filter(must=conditions) if conditions else None

    results = await self.client.query_points(
        collection_name=self._settings.qdrant_collection,
        query=vector,
        query_filter=search_filter,
        limit=limit,
        with_payload=True,
    )
    return [
        {"id": str(r.id), "title": r.payload.get("title", ""), ...}
        for r in results.points
    ]
```

---

## 4. Embedding & LLM

### 4.1 Ollama Embedder (`src/embed/ollama.py`)

**Retry with exponential backoff** (lines 16-47):

```python
class OllamaEmbedder:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self.settings = self._settings
        self._base_url = self._settings.ollama_url
        self._model = self._settings.embedding_model
        self._dim = self._settings.embedding_dim
        self._timeout = self._settings.embedding_timeout
        self._max_retries = 2
        self._batch_semaphore = asyncio.Semaphore(4)

    async def embed(self, text: str) -> list[float]:
        text = text[:MAX_CHUNK_CHARS]   # 4000 char cap
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
                wait = 0.5 * (2 ** attempt)
                log.warning("Embed retry %d/%d: %s", attempt + 1, self._max_retries, e)
                await asyncio.sleep(wait)
        raise EmbeddingError("Unreachable")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with self._batch_semaphore:
            results = []
            for text in texts:
                vec = await self.embed(text)
                results.append(vec)
            return results

    async def check(self) -> bool:
        try:
            await self.embed("health check")
            return True
        except Exception:
            return False
```

---

## 5. Ingestion Pipeline

### 5.1 Push — Dual-Store Write (`src/ingest/push.py`)

**Push text with summarization + dedup + vector index** (lines 56-116):

```python
class Push:
    def __init__(self, pg: PgStore, qdrant: QdrantStore | None = None,
                 embedder: OllamaEmbedder | None = None):
        self.pg = pg
        self.qdrant = qdrant
        self.embedder = embedder

    async def push_text(self, title: str, content: str, scope: str = "shared",
                        doc_type: str = "learning", ..., embed: bool = True,
                        trace_content: str | None = None) -> dict:
        validate_doc_type(doc_type)

        if concepts is None:
            concepts = extract_concepts(content)

        summary = None
        if len(content) > 3000 and self.embedder:
            summary = await self._summarize(content)

        result = await self.pg.add(...)

        # Create traces from Obsidian-style [[links]] in content
        if result["status"] != "duplicate":
            try:
                trace_result = await create_traces_from_links(
                    self.pg, result["id"], trace_content or content, scope=scope
                )
                if trace_result["traces_created"] > 0:
                    log.info("Created %d traces from obsidian links in '%s'",
                             trace_result["traces_created"], title)
            except Exception as e:
                log.warning("Obsidian link trace creation failed: %s", e)

        if embed and self.qdrant and self.embedder:
            try:
                text_for_embedding = summary or content
                vector = await self.embedder.embed(text_for_embedding)
                await self.qdrant.upsert(
                    doc_id=result["id"], vector=vector, title=title, scope=scope, ...
                )
            except Exception as e:
                log.warning("Vector indexing failed: %s", e)
                result["status"] = "indexed_pg_only"

        return result
```

### 5.2 Oracle Path Metadata (`src/ingest/oracle_paths.py`)

**Path rules for κ/ψ brain structure** (lines 6-52):

```python
ORACLE_PATH_RULES: list[tuple[str, str, str]] = [
    (r"ψ/memory/learnings/", "learning", "extrinsic"),
    (r"ψ/memory/retrospectives/", "retro", "extrinsic"),
    (r"ψ/outbox/", "handoff", "extrinsic"),
    (r"κ/extrinsic/wisdom/knowledge/", "wisdom", "extrinsic"),
    (r"κ/extrinsic/wisdom/reference/", "reference", "extrinsic"),
    (r"κ/extrinsic/experience/learn/", "learning", "extrinsic"),
    (r"κ/extrinsic/experience/work/logs/", "log", "extrinsic"),
    (r"κ/intrinsic/instinct/", "instinct", "intrinsic"),
    (r"κ/intrinsic/identity/", "instinct", "intrinsic"),
    (r"κ/intrinsic/inherit/", "instinct", "intrinsic"),
]

VALID_DOC_TYPES = {
    "learning", "pattern", "retro", "reference", "handoff",
    "protocol", "wisdom", "instinct", "log", "note",
}

VALID_TRACE_RELATIONS = {"derived_from", "refines", "contradicts", "extends", "references"}


def extract_metadata(file_path: str, repo_root: str) -> dict:
    rel_path = str(file_path).replace(str(repo_root) + "/", "")
    oracle_name = extract_oracle_name(repo_root)

    for pattern, doc_type, brain_tier in ORACLE_PATH_RULES:
        if pattern in rel_path:
            return {
                "oracle_name": oracle_name,
                "brain_path": rel_path,
                "brain_tier": brain_tier,
                "doc_type": doc_type,
                "scope": oracle_name,
            }

    return {
        "oracle_name": oracle_name,
        "brain_path": rel_path,
        "brain_tier": "extrinsic",
        "doc_type": "note",
        "scope": oracle_name,
    }
```

### 5.3 Hook Handler (`src/ingest/hook_handler.py`)

**PostToolUse auto-ingest entry point** (lines 21-115):

```python
def is_oracle_brain_path(file_path: str) -> bool:
    p = Path(file_path)
    parts = p.parts
    return "κ" in parts or "ψ" in parts


def find_oracle_root(file_path: str) -> str | None:
    p = Path(file_path).resolve()
    for parent in [p.parent, *p.parents]:
        if (parent / "CLAUDE.md").exists():
            return str(parent)
    return None


async def ingest_file(file_path: str):
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return
    if not is_oracle_brain_path(file_path):
        return

    oracle_root = find_oracle_root(file_path)
    if not oracle_root:
        return

    meta = extract_metadata(file_path, oracle_root)
    content = path.read_text(encoding="utf-8")

    settings = Settings()
    pg = PgStore(settings)
    await pg.connect()

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

    push = Push(pg, qdrant, embedder)
    try:
        result = await push.push_text(
            title=meta.get("doc_type", "note"),
            content=content,
            scope=meta.get("oracle_name", "shared"),
            doc_type=meta.get("doc_type", "note"),
            oracle_name=meta.get("oracle_name"),
            brain_path=meta.get("brain_path"),
            brain_tier=meta.get("brain_tier"),
            source_file=file_path,
            source_type="hook",
            source_project=Path(oracle_root).name,
            embed=embedder is not None,
        )
        print(json.dumps(result))
    finally:
        await pg.close()
        if qdrant:
            await qdrant.close()


def main():
    """CLI entry point. Reads file path from argv, env var, or stdin JSON."""
    file_path = ""
    if len(sys.argv) > 1 and sys.argv[1]:
        file_path = sys.argv[1]
    elif os.environ.get("CLAUDE_CODE_FILEPATH"):
        file_path = os.environ["CLAUDE_CODE_FILEPATH"]
    else:
        try:
            data = json.load(sys.stdin)
            file_path = data.get("tool_input", {}).get("file_path", "")
            if not file_path:
                file_path = data.get("file_path", "")
        except (json.JSONDecodeError, EOFError):
            pass

    if not file_path:
        sys.exit(0)
    asyncio.run(ingest_file(file_path))
```

### 5.4 Init Scan (`src/ingest/init_scan.py`)

**Directory walk + LLM summarization** (lines 126-256):

```python
SCAN_EXTENSIONS = {".md", ".txt", ".rst", ".pdf", ".docx"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache"}


def should_skip(path: Path) -> bool:
    parts = path.parts
    for part in parts:
        if part in SKIP_DIRS or part.startswith("."):
            return True
    return False


def scan_files(root: Path) -> list[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip(Path(dirpath) / d)]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() in SCAN_EXTENSIONS and not should_skip(fpath):
                files.append(fpath)
    return sorted(files)


async def init_scan(path: str, scope: str | None = None, dry_run: bool = False) -> dict:
    root = Path(path).resolve()
    files = scan_files(root)

    settings = Settings()
    pg = PgStore(settings)
    await pg.connect()

    qdrant = None
    try:
        qdrant = QdrantStore(settings)
        await qdrant.connect()
    except Exception:
        log.warning("Qdrant not available, FTS-only mode")

    embedder = None
    try:
        embedder = OllamaEmbedder(settings)
    except Exception:
        log.warning("Ollama not available, no LLM summarization")

    push = Push(pg, qdrant, embedder)

    for fpath in files:
        rel_path = str(fpath.relative_to(root))
        content = read_file_content(fpath)
        if not content or not content.strip():
            continue

        metadata = extract_metadata(str(fpath), str(root))
        file_scope = scope or metadata.get("scope", "shared")
        title = fpath.stem.replace("-", " ").replace("_", " ").title()

        # LLM summarization for long content
        final_content = content
        if embedder and len(content) > 2000:
            summary = await summarize_with_llm(content, title, embedder)
            if summary:
                final_content = summary

        if dry_run:
            # ...
            continue

        concepts = extract_concepts(content)
        result = await push.push_text(
            title=title, content=final_content, scope=file_scope,
            doc_type=metadata.get("doc_type", "note"),
            source_file=rel_path, source_type="init_scan",
            source_project=file_scope,
            oracle_name=metadata.get("oracle_name"),
            brain_path=metadata.get("brain_path"),
            brain_tier=metadata.get("brain_tier"),
            trace_content=content,
            concepts=concepts,
        )
        # ...
    # Cleanup
    await pg.close()
    if qdrant:
        await qdrant.close()
    return results
```

---

## 6. Retrieval & Search

### 6.1 Hybrid Search — RRF Fusion (`src/retrieve/hybrid_search.py`)

**Reciprocal Rank Fusion** (lines 13-43):

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

**Hybrid search with cache + fallback** (lines 60-153):

```python
class HybridSearch:
    def __init__(self, pg: PgStore, qdrant: QdrantStore | None = None,
                 embedder: OllamaEmbedder | None = None,
                 weights: list[float] | None = None, rrf_k: int = 60, cache=None):
        self.pg = pg
        self.qdrant = qdrant
        self.embedder = embedder
        self._weights = weights or [0.6, 0.4]
        self._rrf_k = rrf_k
        self._cache = cache

    async def search(self, query: str, ..., mode: str = "hybrid") -> list[dict]:
        # Check cache first
        if self._cache:
            cached = self._cache.get(query, scope=scope, mode=mode, limit=limit)
            if cached is not None:
                return cached

        if mode == "dense":
            if not self.qdrant or not self.embedder:
                raise SearchError("Dense search requires Qdrant and OllamaEmbedder")
            vector = await self.embedder.embed(query)
            return await self.qdrant.search(vector, ...)

        if mode == "fts":
            return await self.pg.search_fts(query, ...)

        # Hybrid: both + RRF
        if not self.qdrant or not self.embedder:
            return await self.pg.search_fts(query, ...)

        try:
            vector = await self.embedder.embed(query)
            dense_results = await self.qdrant.search(vector, ..., limit=limit * 2)
        except EmbeddingError as e:
            log.warning("Dense search failed, falling back to FTS: %s", e)
            return await self.pg.search_fts(query, ..., limit=limit)

        fts_results = await self.pg.search_fts(query, ..., limit=limit * 2)

        if not dense_results and not fts_results:
            return []
        if not dense_results:
            return fts_results[:limit]
        if not fts_results:
            return dense_results[:limit]

        merged = reciprocal_rank_fusion(
            [dense_results, fts_results],
            weights=self._weights,
            k=self._rrf_k,
        )
        results = merged[:limit]

        if self._cache:
            self._cache.put(query, results, scope=scope, mode=mode, limit=limit)
        return results

    async def search_cross_scope(self, query: str, scopes: list[str], limit: int = 10, mode: str = "hybrid") -> list[dict]:
        per_scope: list[list[dict]] = []
        for scope in scopes:
            results = await self.search(query=query, scope=scope, limit=limit * 2, mode=mode)
            per_scope.append(results)
        merged = reciprocal_rank_fusion(per_scope, weights=None, k=self._rrf_k)
        return merged[:limit]
```

### 6.2 Search Cache (`src/cache.py`)

**Thread-safe LRU + TTL** (lines 8-74):

```python
class SearchCache:
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self._max_size = max_size
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple] = OrderedDict()
        self._lock = Lock()

    def _make_key(self, query: str, scope: str | None, mode: str, limit: int) -> str:
        scope_str = scope or "*"
        return f"{query}||{scope_str}||{mode}||{limit}"

    def get(self, query: str, scope: str | None = None, mode: str = "hybrid",
            limit: int = 10) -> list | None:
        key = self._make_key(query, scope, mode, limit)
        with self._lock:
            if key not in self._cache:
                return None
            results, timestamp = self._cache[key]
            if time.time() - timestamp > self._ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return results

    def put(self, query: str, results: list, scope: str | None = None,
            mode: str = "hybrid", limit: int = 10) -> None:
        key = self._make_key(query, scope, mode, limit)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            self._cache[key] = (results, time.time())
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
```

---

## 7. Reconciliation

### 7.1 Defrag — Duplicate Compaction (`src/reconcile/defrag.py`)

```python
async def defrag(pg: PgStore, scope: str | None = None, dry_run: bool = False) -> dict:
    all_docs = await pg.list_docs(scope=scope, limit=10000, order="newest")
    if not all_docs:
        return {"duplicates_found": 0, "compacted": 0, "errors": 0, "groups": []}

    seen = {}
    groups = []
    for doc in all_docs:
        doc_id = doc["id"]
        full_doc = await pg.get(doc_id, include_chain=False)
        if not full_doc:
            continue
        key = (full_doc.get("title", ""), full_doc.get("scope", ""))
        if key not in seen:
            seen[key] = []
        seen[key].append(full_doc)

    for (title, doc_scope), docs in seen.items():
        if len(docs) <= 1:
            continue
        group_info = {
            "title": title, "scope": doc_scope, "count": len(docs),
            "keep": docs[0]["id"], "supersede": [d["id"] for d in docs[1:]],
        }
        if dry_run:
            group_info["action"] = "would_supersede"
            groups.append(group_info)
            continue
        for old_doc in docs[1:]:
            try:
                await pg.supersede(old_id=old_doc["id"], new_content=old_doc.get("content", ""),
                                  reason="defrag_duplicate")
                group_info["action"] = "superseded"
            except Exception as e:
                log.error("Failed to supersede %s: %s", old_doc["id"], e)
    return {"duplicates_found": sum(g["count"] - 1 for g in groups), "compacted": ..., "groups": groups}
```

### 7.2 Detox — Conflict Detection (`src/reconcile/detox.py`)

```python
async def detox(pg: PgStore, qdrant=None, embedder=None, settings=None,
                scope: str | None = None, dry_run: bool = False) -> dict:
    all_docs = await pg.list_docs(scope=scope, limit=100, order="newest")
    if not all_docs or len(all_docs) < 2:
        return {"conflicts_found": 0, "conflicts": [], "resolutions": [], "errors": 0}

    potential_pairs = []
    seen = set()
    for i, doc_a in enumerate(all_docs):
        for doc_b in all_docs[i + 1:]:
            if doc_a.get("scope") == doc_b.get("scope") and doc_a.get("doc_type") == doc_b.get("doc_type"):
                pair_key = tuple(sorted([doc_a["id"], doc_b["id"]]))
                if pair_key not in seen:
                    seen.add(pair_key)
                    potential_pairs.append((doc_a, doc_b))

    conflicts = []
    resolutions = []
    for doc_a, doc_b in potential_pairs:
        if embedder and settings:
            full_a = await pg.get(doc_a["id"], include_chain=False)
            full_b = await pg.get(doc_b["id"], include_chain=False)
            analysis = await analyze_conflict(
                doc_a={"title": full_a.get("title", ""), "content": (full_a.get("content", "") or "")[:2000]},
                doc_b={"title": full_b.get("title", ""), "content": (full_b.get("content", "") or "")[:2000]},
                settings=settings,
            )
            if analysis and analysis.get("is_conflict"):
                conflicts.append(conflict_info)
                if not dry_run and analysis.get("merged_content"):
                    supersede_id = analysis.get("supersede_id", "a")
                    old_id = doc_a["id"] if supersede_id == "a" else doc_b["id"]
                    merged_content = analysis["merged_content"]
                    result = await pg.supersede(
                        old_id=str(old_id), new_content=merged_content,
                        reason=f"detox_conflict: {analysis.get('reason', 'conflict detected')}"
                    )
                    resolutions.append({"old_id": str(old_id), "new_id": result.get("id"), "reason": analysis.get("reason")})
    return {"conflicts_found": len(conflicts), "conflicts": conflicts, "resolutions": resolutions, "errors": errors}
```

---

## 8. Project Registry & Scheduling

### 8.1 Project Registry (`src/registry.py`)

**Auto-detect scope from path** (lines 21-32):

```python
def detect_scope(project_path: str) -> str:
    path = Path(project_path).resolve()
    scope = path.name.lower()
    scope = re.sub(r"[^a-z0-9-]", "-", scope)
    scope = re.sub(r"-+", "-").strip("-")
    return scope or "shared"


def validate_scope(scope: str) -> bool:
    return bool(re.match(r"^[a-z0-9][a-z0-9-]{0,63}$", scope))
```

**Upsert registration + JSON backup** (lines 35-104):

```python
async def register_project(pg: PgStore, project_path: str, scope: str | None = None) -> dict:
    if scope is None:
        scope = detect_scope(project_path)
    if not validate_scope(scope):
        raise ValueError(f"Invalid scope name: {scope}")

    async with pg.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO registered_projects (scope, project_path, registered_at)
               VALUES ($1, $2, NOW())
               ON CONFLICT (scope) DO UPDATE SET project_path = $2, registered_at = NOW()""",
            scope, str(Path(project_path).resolve()),
        )
    result = {"scope": scope, "project_path": project_path, "status": "registered"}
    await _save_registry_backup(pg)
    return result
```

### 8.2 Scheduler (`src/scheduler.py`)

**Periodic scan + daily reconcile** (lines 15-177):

```python
class TaskScheduler:
    def __init__(self, pg, settings, qdrant=None, embedder=None,
                 scan_interval: int = 600, reconcile_hour: int = 2):
        self._pg = pg
        self._settings = settings
        self._qdrant = qdrant
        self._embedder = embedder
        self._scan_interval = scan_interval
        self._reconcile_hour = reconcile_hour
        self._scan_task: asyncio.Task | None = None
        self._reconcile_task: asyncio.Task | None = None
        self._running = False
        self._last_reconcile_date: str | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self._scan_interval > 0:
            self._scan_task = asyncio.create_task(self._scan_loop())
        self._reconcile_task = asyncio.create_task(self._reconcile_loop())

    async def stop(self) -> None:
        self._running = False
        for task in (self._scan_task, self._reconcile_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _reconcile_loop(self) -> None:
        while self._running:
            try:
                now = datetime.now()
                target = now.replace(hour=self._reconcile_hour, minute=0, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                sleep_seconds = (target - now).total_seconds()
                await asyncio.sleep(sleep_seconds)
                if not self._running:
                    break
                today_str = datetime.now().strftime("%Y-%m-%d")
                if self._last_reconcile_date == today_str:
                    continue
                await self._run_reconcile()
                self._last_reconcile_date = today_str
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Reconcile loop error: %s", e)
                await asyncio.sleep(3600)
```

---

## 9. Daemon & Local-Only Enforcement

### 9.1 Daemon Lifecycle (`src/daemon.py`)

**PID file + signal handling** (lines 14-117):

```python
def write_pid(pid_path: str | None = None) -> str:
    if pid_path is None:
        pid_path = str(DEFAULT_PID_DIR / "synapse.pid")
    Path(pid_path).parent.mkdir(parents=True, exist_ok=True)
    Path(pid_path).write_text(str(os.getpid()), encoding="utf-8")
    return pid_path


def read_pid(pid_path: str | None = None) -> int | None:
    try:
        return int(Path(pid_path).read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def is_running(pid_path: str | None = None) -> bool:
    pid = read_pid(pid_path)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        remove_pid(pid_path)
        return False
    except PermissionError:
        return True


def stop_daemon(pid_path: str | None = None) -> dict:
    pid = read_pid(pid_path)
    if pid is None:
        return {"status": "not_running", "message": "No PID file found"}
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except ProcessLookupError:
                remove_pid(pid_path)
                return {"status": "stopped", "pid": pid}
        os.kill(pid, signal.SIGKILL)
        remove_pid(pid_path)
        return {"status": "killed", "pid": pid}
    except ProcessLookupError:
        remove_pid(pid_path)
        return {"status": "not_running", "pid": pid}
    except PermissionError:
        return {"status": "error", "pid": pid, "message": "Permission denied"}


def setup_signals(on_reload=None, on_shutdown=None):
    def _handle_shutdown(signum, frame):
        log.info("Received signal %d, shutting down", signum)
        if on_shutdown:
            on_shutdown()
    def _handle_reload(signum, frame):
        log.info("Received SIGHUP, reloading configuration")
        if on_reload:
            on_reload()
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    try:
        signal.signal(signal.SIGHUP, _handle_reload)
    except (OSError, ValueError):
        pass  # SIGHUP not available on Windows
```

### 9.2 Local-Only Enforcement (`src/local_only.py`)

```python
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}


def validate_local_url(url: str, allow_docker: bool = False) -> list[str]:
    violations = []
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if not hostname:
            return violations
        if hostname in LOCAL_HOSTS:
            return violations
        if allow_docker and (hostname.endswith(".internal") or hostname == "host.docker.internal"):
            return violations
        violations.append(f"Non-localhost URL: {url} (hostname={hostname})")
    except Exception as e:
        violations.append(f"Invalid URL: {url} ({e})")
    return violations
```

---

## 10. MCP Server

### 10.1 MCP Tool Definitions (`src/mcp/server.py`)

**Tool schema array** (lines 21-193):

```python
TOOL_DEFINITIONS = [
    Tool(
        name="synapse_search",
        description="Search knowledge vault with hybrid dense+keyword search.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "scope": {"type": "string"},
                "doc_type": {"type": "string"},
                "oracle": {"type": "string"},
                "source_project": {"type": "string"},
                "concepts": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 10},
                "mode": {"type": "string", "enum": ["hybrid", "dense", "fts"], "default": "hybrid"},
            },
            "required": ["query"],
        },
    ),
    # ... synapse_push, synapse_supersede, synapse_trace, synapse_trace_chain,
    # synapse_concepts, synapse_get, synapse_scope, synapse_stats, synapse_list,
    # synapse_register, synapse_unregister, synapse_projects, synapse_search_cross
]
```

**MCP app factory + stdio runner** (lines 197-356):

```python
async def create_app(settings: Settings | None = None) -> Server:
    settings = settings or Settings()
    pg = PgStore(settings)
    qdrant = QdrantStore(settings)
    embedder = OllamaEmbedder(settings)

    await pg.connect()
    await pg.init_schema()
    try:
        await qdrant.connect()
    except Exception:
        log.warning("Qdrant not available, falling back to FTS-only mode")
        qdrant = None

    push = Push(pg, qdrant, embedder)
    search = HybridSearch(pg, qdrant, embedder)

    server = Server("synapse")

    @server.list_tools()
    async def list_tools():
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        try:
            if name == "synapse_search":
                results = await search.search(...)
                return [TextContent(type="text", text=json.dumps(results, indent=2))]
            elif name == "synapse_push":
                result = await push.push_text(...)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            # ... other tools
        except Exception as e:
            log.error("Tool %s error: %s", name, e)
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    return server


async def run_server():
    app = await create_app()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
```

---

## 11. HTTP API

### 11.1 Routes Setup (`src/api/routes.py`)

**Global state injection + SafeJSONResponse** (lines 16-38):

```python
router = APIRouter(prefix="/api", tags=["synapse"])

pg: PgStore | None = None
qdrant: QdrantStore | None = None
embedder: OllamaEmbedder | None = None
push: Push | None = None
search: HybridSearch | None = None


class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=True, default=str).encode("utf-8")


def init_routes(pg_store, qdrant_store, embedder_client):
    global pg, qdrant, embedder, push, search
    pg = pg_store
    qdrant = qdrant_store
    embedder = embedder_client
    push = Push(pg, qdrant, embedder)
    search = HybridSearch(pg, qdrant, embedder)
```

**Health expansion (liveness + readiness)** (lines 180-217):

```python
@router.get("/health")
async def api_health():
    embedding_ok = False
    if embedder:
        embedding_ok = await embedder.check()
    qdrant_ok = qdrant is not None
    return {"status": "ok", "qdrant": qdrant_ok, "embedding": embedding_ok}


@router.get("/health/live")
async def api_liveness():
    return {"alive": True}


@router.get("/health/ready")
async def api_readiness():
    checks = {"pg": False, "qdrant": False, "embedding": False}
    try:
        await pg.pool.acquire()
        checks["pg"] = True
    except Exception:
        pass
    if qdrant:
        try:
            await qdrant.connect()
            checks["qdrant"] = True
        except Exception:
            pass
    if embedder:
        checks["embedding"] = await embedder.check()
    ready = checks["pg"]
    return {"ready": ready, **checks}
```

**Chat endpoint with streaming** (lines 504-593):

```python
@router.post("/chat")
async def api_chat(request: Request):
    from fastapi.responses import StreamingResponse
    body = await request.json()
    query = body.get("query", "")
    model = body.get("model", "kimi-k2.6:cloud")
    scope = body.get("scope")
    scopes = body.get("scopes")

    if scopes and isinstance(scopes, list) and len(scopes) > 0:
        search_results = await search.search_cross_scope(query=query, scopes=scopes, limit=5, mode="hybrid")
    else:
        search_results = await search.search(query=query, scope=scope, limit=5, mode="hybrid")

    context_parts = []
    for r in search_results:
        full_doc = await pg.get(r['id'])
        content = full_doc['content'][:800] if full_doc and full_doc.get('content') else '[no content]'
        ctx = f"[{r['title']} | scope: {r.get('scope', 'shared')}]\n{content}"
        context_parts.append(ctx)
    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

    system_prompt = (
        "You are a helpful assistant that answers questions based on the provided knowledge vault context. "
        "Use only the information in the context to answer. If the context doesn't contain the answer, say so. "
        "Cite sources by referencing document titles in brackets."
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    sources_meta = [...]

    async def stream_response():
        yield f"__SOURCES__{json.dumps(sources_meta)}__SOURCES__"
        try:
            import httpx
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": True,
                "options": {"temperature": 0.7},
            }
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST", f"{embedder.settings.ollama_url}/api/chat", json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            yield f"\n[Error: {e}]"

    return StreamingResponse(stream_response(), media_type="text/plain")
```

---

## 12. Hooks Installer

### 12.1 Hook Registration (`src/hooks/installer.py`)

**Idempotent settings.json modification** (lines 82-131):

```python
SYNAPSE_INGEST_MARKER = "src.ingest.hook_handler"
SYNAPSE_CONTEXT_MARKER = "synapse-context-inject"


def find_hook_entry(hooks_list: list, marker: str) -> dict | None:
    for entry in hooks_list:
        if "hooks" not in entry:
            continue
        for hook in entry["hooks"]:
            cmd = hook.get("command", "")
            if marker in cmd:
                return entry
    return None


def install_hooks(settings_path=None, python_path=None, script_path=None, dry_run=False) -> dict:
    path = settings_path or SETTINGS_PATH
    settings = load_settings(path)
    if "hooks" not in settings:
        settings["hooks"] = {}

    results = {
        "settings_path": str(path),
        "ingest_hook": "unchanged",
        "context_hook": "unchanged",
        "changes": [],
    }

    post_hooks = settings["hooks"].setdefault("PostToolUse", [])
    existing_ingest = find_hook_entry(post_hooks, SYNAPSE_INGEST_MARKER)
    if existing_ingest is None:
        ingest_entry = build_ingest_hook_entry(python_path)
        post_hooks.append(ingest_entry)
        results["ingest_hook"] = "installed"
        results["changes"].append("Added PostToolUse auto-ingest hook")

    pre_hooks = settings["hooks"].setdefault("PreToolUse", [])
    existing_context = find_hook_entry(pre_hooks, SYNAPSE_CONTEXT_MARKER)
    if existing_context is None:
        context_entry = build_context_inject_hook_entry(script_path)
        pre_hooks.append(context_entry)
        results["context_hook"] = "installed"
        results["changes"].append("Added PreToolUse context injection hook")

    if not dry_run and results["changes"]:
        save_settings(settings, path)
    return results
```

---

## 13. Schema

### 13.1 PostgreSQL Schema (`src/db/schema.sql`)

**Core tables + tsvector trigger** (lines 1-105):

```sql
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    doc_type        TEXT NOT NULL DEFAULT 'learning',
    scope           TEXT NOT NULL DEFAULT 'shared',
    source_file     TEXT,
    source_type     TEXT NOT NULL DEFAULT 'manual',
    source_project  TEXT,
    oracle_name     TEXT,
    brain_path      TEXT,
    brain_tier      TEXT,
    concepts        JSONB DEFAULT '[]',
    tags            JSONB DEFAULT '[]',
    superseded_by   UUID REFERENCES knowledge_documents(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    search_vector   tsvector,
    UNIQUE(content_hash, scope)
);

CREATE OR REPLACE FUNCTION update_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.content, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(
            (SELECT string_agg(value::text, ' ') FROM jsonb_array_elements_text(NEW.concepts) AS value), ''
        )), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE TRIGGER trg_search_vector
    BEFORE INSERT OR UPDATE ON knowledge_documents
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

CREATE INDEX idx_doc_search ON knowledge_documents USING GIN(search_vector);
CREATE INDEX idx_doc_scope ON knowledge_documents(scope) WHERE superseded_by IS NULL;
CREATE INDEX idx_doc_type ON knowledge_documents(doc_type) WHERE superseded_by IS NULL;
CREATE INDEX idx_doc_oracle ON knowledge_documents(oracle_name) WHERE superseded_by IS NULL;
CREATE INDEX idx_doc_hash ON knowledge_documents(content_hash);
CREATE INDEX idx_doc_brain_tier ON knowledge_documents(brain_tier) WHERE superseded_by IS NULL;
CREATE INDEX idx_doc_source_project ON knowledge_documents(source_project) WHERE superseded_by IS NULL;

CREATE TABLE IF NOT EXISTS supersede_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    old_id      UUID NOT NULL REFERENCES knowledge_documents(id),
    new_id      UUID NOT NULL REFERENCES knowledge_documents(id),
    reason      TEXT DEFAULT 'updated',
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scope_registry (
    name        TEXT PRIMARY KEY,
    description TEXT,
    doc_count   INTEGER DEFAULT 0,
    oracle_name TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concepts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_concepts (
    doc_id      UUID REFERENCES knowledge_documents(id),
    concept_id  UUID REFERENCES concepts(id),
    PRIMARY KEY (doc_id, concept_id)
);

CREATE TABLE IF NOT EXISTS trace (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID REFERENCES knowledge_documents(id),
    target_id   UUID REFERENCES knowledge_documents(id),
    relation    TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS registered_projects (
    scope           TEXT PRIMARY KEY,
    project_path    TEXT NOT NULL,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 14. Patterns & Idioms

### 14.1 Graceful Degradation

Throughout the codebase, external services (Qdrant, Ollama) are treated as optional:

```python
qdrant = None
try:
    qdrant = QdrantStore(settings)
    await qdrant.connect()
except Exception:
    log.warning("Qdrant not available, running in FTS-only mode")
    qdrant = None
```

### 14.2 Dual-Store Consistency

Every `push` writes to PostgreSQL first, then Qdrant. On Qdrant failure, the doc is still indexed in PG with status `"indexed_pg_only"`.

### 14.3 Supersession Instead of Deletion

Nothing is ever deleted. Supersession creates a new doc and updates `superseded_by` on the old one. All queries filter `WHERE superseded_by IS NULL`.

### 14.4 Dynamic SQL with Parameterized Queries

```python
conditions = ["superseded_by IS NULL", "search_vector @@ to_tsquery('english', $1)"]
params: list = [ts_query]
idx = 2
if scope:
    conditions.append(f"scope = ${idx}")
    params.append(scope)
    idx += 1
# ...
where = " AND ".join(conditions)
sql = f"SELECT ... WHERE {where} ORDER BY rank DESC LIMIT ${idx}"
rows = await conn.fetch(sql, *params)
```

### 14.5 Decorator for Async CLI Commands

```python
def cli_command(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        async def run():
            components = await get_components()
            try:
                result = await func(components, *args, **kwargs)
                output(result)
            except Exception as e:
                output({"error": str(e), "command": func.__name__})
                sys.exit(1)
            finally:
                await cleanup(components)
        asyncio.run(run())
    return wrapper
```

### 14.6 Config Hot-Reload

`Settings.reload()` creates a new instance and copies all fields except `config_path`. Triggered by `SIGHUP` in the daemon.

### 14.7 Idempotent Settings Patching

The hooks installer uses marker strings to detect whether a hook entry already exists, preventing duplicate entries on repeated installs.

---

*End of reference document.*
