from __future__ import annotations

"""HTTP API routes — mirrors MCP tool interface for Docker service access."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.ingest.push import Push
from src.ingest.oracle_paths import validate_doc_type, validate_trace_relation
from src.retrieve.hybrid_search import HybridSearch

router = APIRouter(prefix="/api", tags=["synapse"])

pg: PgStore | None = None
qdrant: QdrantStore | None = None
embedder: OllamaEmbedder | None = None
push: Push | None = None
search: HybridSearch | None = None
_settings: "Settings" | None = None


class SafeJSONResponse(JSONResponse):
    """JSON response that escapes non-ASCII chars to avoid parser issues."""
    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=True, default=str).encode("utf-8")


def init_routes(pg_store: PgStore, qdrant_store: QdrantStore | None,
                embedder_client: OllamaEmbedder | None,
                settings: "Settings" | None = None):
    global pg, qdrant, embedder, push, search, _settings
    pg = pg_store
    qdrant = qdrant_store
    embedder = embedder_client
    _settings = settings
    push = Push(pg, qdrant, embedder)
    search = HybridSearch(pg, qdrant, embedder)


# --- Search ---

class SearchRequest:
    def __init__(self, query: str, scope: str | None = None, doc_type: str | None = None,
                 oracle: str | None = None, source_project: str | None = None,
                 concepts: list[str] | None = None, limit: int = 10, mode: str = "hybrid"):
        self.query = query
        self.scope = scope
        self.doc_type = doc_type
        self.oracle = oracle
        self.source_project = source_project
        self.concepts = concepts
        self.limit = limit
        self.mode = mode


@router.post("/search")
async def api_search(body: dict):
    results = await search.search(
        query=body["query"],
        scope=body.get("scope"),
        doc_type=body.get("doc_type"),
        oracle=body.get("oracle"),
        source_project=body.get("source_project"),
        concepts=body.get("concepts"),
        limit=body.get("limit", 10),
        mode=body.get("mode", "hybrid"),
    )
    return results


# --- Push ---

@router.post("/push")
async def api_push(body: dict):
    result = await push.push_text(
        title=body["title"],
        content=body["content"],
        scope=body.get("scope", "shared"),
        doc_type=body.get("doc_type", "learning"),
        source_file=body.get("source_file"),
        source_type=body.get("source_type", "api"),
        source_project=body.get("source_project"),
        concepts=body.get("concepts"),
        tags=body.get("tags"),
        oracle_name=body.get("oracle_name"),
        brain_path=body.get("brain_path"),
        brain_tier=body.get("brain_tier"),
    )
    return result


# --- Webhook (for external projects) ---

@router.post("/webhook")
async def api_webhook(request: Request):
    from src.api.webhook_verify import verify_webhook_signature

    secret = _settings.webhook_secret if _settings else ""
    body_bytes = await verify_webhook_signature(request, secret=secret)
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    body.setdefault("source_type", "webhook")
    return await api_push(body)


# --- LINE Webhook ---

@router.post("/line-webhook")
async def api_line_webhook(request: Request):
    from src.api.line_handler import verify_line_signature, process_line_events

    channel_secret = _settings.line_channel_secret if _settings else ""
    access_token = _settings.line_channel_access_token if _settings else ""

    body = await request.body()
    signature = request.headers.get("x-line-signature", "")

    if not channel_secret:
        raise HTTPException(status_code=500, detail="LINE_CHANNEL_SECRET not configured")

    if not verify_line_signature(body, signature, channel_secret):
        raise HTTPException(status_code=401, detail="Invalid LINE signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    events = payload.get("events", [])
    stats = await process_line_events(
        events, pg,
        access_token=access_token,
        settings=_settings,
    )
    return stats


# --- Supersede ---

@router.post("/supersede")
async def api_supersede(body: dict):
    result = await pg.supersede(
        old_id=body["old_id"],
        new_content=body["new_content"],
        reason=body.get("reason", "updated"),
        new_title=body.get("new_title"),
    )
    if qdrant:
        await qdrant.mark_superseded(body["old_id"])
    return result


# --- Trace ---

@router.post("/trace")
async def api_trace(body: dict):
    validate_trace_relation(body["relation"])
    result = await pg.add_trace(
        source_id=body["source_id"],
        target_id=body["target_id"],
        relation=body["relation"],
        confidence=body.get("confidence", 1.0),
    )
    return result


@router.get("/trace/{doc_id}")
async def api_trace_chain(doc_id: str, direction: str = "both",
                          max_depth: int = 5, relation: str | None = None):
    results = await pg.get_trace_chain(doc_id, direction, max_depth, relation)
    return results


# --- Concepts ---

@router.get("/concepts")
async def api_concepts(search: str | None = None, limit: int = 50):
    results = await pg.list_concepts(search, limit)
    return results


# --- Get ---

@router.get("/documents/{doc_id}")
async def api_get(doc_id: str, include_chain: bool = True):
    doc = await pg.get(doc_id, include_chain=include_chain)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# --- Scope ---

@router.get("/scopes", response_class=SafeJSONResponse)
async def api_scopes():
    return await pg.list_scopes()


# --- Stats ---

@router.get("/stats", response_class=SafeJSONResponse)
async def api_stats():
    return await pg.stats()


# --- List ---

@router.get("/documents")
async def api_list(scope: str | None = None, doc_type: str | None = None,
                   oracle: str | None = None, limit: int = 20, offset: int = 0,
                   order: str = "newest"):
    return await pg.list_docs(scope, doc_type, oracle, limit, offset, order)


# --- Health ---

@router.get("/health")
async def api_health():
    embedding_ok = False
    if embedder:
        embedding_ok = await embedder.check()
    qdrant_ok = qdrant is not None
    pg_ok = False
    try:
        async with pg.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        pg_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if pg_ok else "degraded",
        "pg": pg_ok,
        "qdrant": qdrant_ok,
        "embedding": embedding_ok,
    }


@router.get("/health/live")
async def api_liveness():
    return {"alive": True}


@router.get("/health/ready")
async def api_readiness():
    checks = {"pg": False, "qdrant": False, "embedding": False}
    try:
        async with pg.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["pg"] = True
    except Exception:
        pass
    if qdrant:
        try:
            await qdrant.connect()
            checks["qdrant"] = True
        except Exception:
            pass
    else:
        checks["qdrant"] = False
    if embedder:
        checks["embedding"] = await embedder.check()
    ready = checks["pg"]
    return {"ready": ready, **checks}


@router.post("/register")
async def api_register(body: dict):
    from src.registry import register_project
    return await register_project(pg, body["project_path"], scope=body.get("scope"))


@router.post("/unregister")
async def api_unregister(body: dict):
    from src.registry import unregister_project
    return await unregister_project(pg, body["scope"])


@router.get("/projects")
async def api_projects():
    from src.registry import list_projects
    return await list_projects(pg)


@router.post("/search-cross")
async def api_search_cross(body: dict):
    results = await search.search_cross_scope(
        query=body["query"],
        scopes=body["scopes"],
        limit=body.get("limit", 10),
        mode=body.get("mode", "hybrid"),
    )
    return results


# --- Obsidian link resolution ---

@router.post("/resolve-links")
async def api_resolve_links(body: dict):
    """Resolve Obsidian-style [[link]] targets to document IDs."""
    from src.ingest.obsidian_links import resolve_links, extract_links

    content = body.get("content", "")
    scope = body.get("scope")

    links = extract_links(content)
    if not links:
        return {"resolved": {}, "unresolved": []}

    resolved = await resolve_links(pg, links, scope=scope)
    targets = {link["target"] for link in links}
    unresolved = [t for t in targets if t not in resolved]

    return {"resolved": resolved, "unresolved": unresolved}


# --- Ingest extensions ---

@router.post("/ingest/youtube")
async def api_ingest_youtube(body: dict):
    """Extract transcript from YouTube URL and push to vault."""
    url = body.get("url", "")
    scope = body.get("scope", "shared")
    if not url:
        raise HTTPException(status_code=400, detail="url required")

    # Try youtube-transcript-api first, fallback to yt-dlp
    content = ""
    title = url
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        video_id = _extract_youtube_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        content = "\n".join(seg["text"] for seg in transcript)
        title = f"YouTube Transcript: {video_id}"
    except Exception:
        # Fallback to basic extraction
        content = f"[YouTube URL: {url}]"
        title = f"YouTube: {url}"

    result = await push.push_text(
        title=title,
        content=content,
        scope=scope,
        doc_type="note",
        source_type="youtube",
        source_file=url,
    )
    return {"id": result.get("id"), "status": "indexed", "title": title}


def _extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    import re
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


@router.post("/ingest/website")
async def api_ingest_website(body: dict):
    """Scrape website content and push to vault."""
    url = body.get("url", "")
    scope = body.get("scope", "shared")
    if not url:
        raise HTTPException(status_code=400, detail="url required")

    try:
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove script/style
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            title = soup.title.string.strip() if soup.title else url
            content = soup.get_text(separator="\n", strip=True)
            # Truncate if too long
            if len(content) > 50000:
                content = content[:50000] + "\n\n[...truncated]"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape failed: {e}")

    result = await push.push_text(
        title=title,
        content=content,
        scope=scope,
        doc_type="note",
        source_type="website",
        source_file=url,
    )
    return {"id": result.get("id"), "status": "indexed", "title": title}


@router.post("/ingest/file")
async def api_ingest_file(request: Request):
    """Upload file, parse content, and push to vault."""
    from fastapi import UploadFile, File as FastAPIFile
    from multipart.multipart import parse_options_header
    import io

    scope = "shared"
    content = ""
    title = "Uploaded file"
    filename = ""

    # FastAPI doesn't have native multipart in plain router without deps
    # Use raw body parsing for now
    body = await request.body()
    content_type = request.headers.get("content-type", "")

    if "multipart" in content_type:
        # Simple multipart parsing
        boundary = parse_options_header(content_type)[1].get("boundary", b"").decode()
        if boundary:
            parts = body.split(f"--{boundary}".encode())
            for part in parts:
                if b'Content-Disposition: form-data; name="file"' in part:
                    # Extract filename and content
                    header_end = part.find(b"\r\n\r\n")
                    if header_end > 0:
                        headers = part[:header_end].decode()
                        fn_match = __import__("re").search(r'filename="([^"]*)"', headers)
                        if fn_match:
                            filename = fn_match.group(1)
                            title = filename
                        file_content = part[header_end + 4 :]
                        if file_content.endswith(b"\r\n"):
                            file_content = file_content[:-2]
                        content = _parse_file_content(filename, file_content)
                elif b'Content-Disposition: form-data; name="scope"' in part:
                    header_end = part.find(b"\r\n\r\n")
                    if header_end > 0:
                        scope = part[header_end + 4 :].decode().strip()
                        if scope.endswith("\r\n"):
                            scope = scope[:-2]

    if not content:
        raise HTTPException(status_code=400, detail="No file content parsed")

    result = await push.push_text(
        title=title,
        content=content,
        scope=scope,
        doc_type="note",
        source_type="file",
        source_file=filename,
    )
    return {"id": result.get("id"), "status": "indexed", "title": title}


def _parse_file_content(filename: str, data: bytes) -> str:
    """Parse uploaded file bytes to text."""
    import re
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    if ext in ("txt", "md", "rst"):
        return data.decode("utf-8", errors="replace")

    if ext == "pdf":
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
        except Exception:
            return "[PDF parsing failed - raw bytes]"

    if ext == "docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(data))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception:
            return "[DOCX parsing failed - raw bytes]"

    return data.decode("utf-8", errors="replace")


# --- Suggest Scope ---

@router.post("/suggest-scope")
async def api_suggest_scope(body: dict):
    """Use LLM to suggest the best scope for given content."""
    content = body.get("content", "")
    available_scopes = body.get("scopes")
    model = body.get("model", "kimi-k2.6:cloud")

    if not content:
        raise HTTPException(status_code=400, detail="content required")

    if not available_scopes:
        scopes_data = await pg.list_scopes()
        available_scopes = [s["name"] for s in scopes_data]

    try:
        import httpx
        scopes_list = ", ".join(available_scopes)
        system_prompt = (
            f"You are a knowledge organizer. Given content, suggest the most appropriate scope from: {scopes_list}. "
            "Respond with ONLY the scope name."
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Content:\n{content[:4000]}"},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        settings = embedder.settings if embedder else __import__("src.config").Settings()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            suggested = data.get("message", {}).get("content", "").strip().lower()

            # Exact match
            for s in available_scopes:
                if s.lower() == suggested:
                    return {"scope": s, "confidence": 1.0}

            # Substring match
            for s in available_scopes:
                if s.lower() in suggested or suggested in s.lower():
                    return {"scope": s, "confidence": 0.8}

            return {"scope": available_scopes[0] if available_scopes else "shared", "confidence": 0.5}
    except Exception as e:
        return {"scope": "shared", "confidence": 0, "error": str(e)}


# --- Chat ---

@router.post("/chat")
async def api_chat(request: Request):
    """Stream chat response using search context + Ollama LLM."""
    from fastapi.responses import StreamingResponse
    import json as json_mod

    body = await request.json()
    query = body.get("query", "")
    model = body.get("model", "kimi-k2.6:cloud")
    scope = body.get("scope")
    scopes = body.get("scopes")

    if not query:
        raise HTTPException(status_code=400, detail="query required")

    # 1. Search for relevant documents
    if scopes and isinstance(scopes, list) and len(scopes) > 0:
        search_results = await search.search_cross_scope(
            query=query,
            scopes=scopes,
            limit=5,
            mode="hybrid",
        )
    else:
        search_results = await search.search(
            query=query,
            scope=scope,
            limit=5,
            mode="hybrid",
        )

    # 2. Build context prompt
    context_parts = []
    for r in search_results:
        # Fetch full doc to get content (search results only have title/scope/score)
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
    scope_hint = ""
    if scopes and len(scopes) > 0:
        scope_hint = f"The user is asking across these scopes: {', '.join(scopes)}. "
    user_prompt = f"{scope_hint}Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    sources_meta = [
        {"id": r["id"], "title": r["title"], "scope": r.get("scope", ""), "doc_type": r.get("doc_type", "")}
        for r in search_results
    ]

    # 4. Stream from Ollama
    async def stream_response():
        # Prefix with sources so frontend can show citations
        yield f"__SOURCES__{json_mod.dumps(sources_meta)}__SOURCES__"
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
                async with client.stream(
                    "POST",
                    f"{embedder.settings.ollama_url}/api/chat",
                    json=payload,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json_mod.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except json_mod.JSONDecodeError:
                            pass
        except Exception as e:
            yield f"\n[Error: {e}]"

    return StreamingResponse(stream_response(), media_type="text/plain")


# --- Search Topics ---

@router.get("/search-topics")
async def api_search_topics(scope: str | None = None):
    """List configured search topics for web/social monitoring."""
    return await pg.list_search_topics(scope=scope)


@router.post("/search-topics")
async def api_add_search_topic(body: dict):
    """Add a new search topic for monitoring."""
    return await pg.add_search_topic(
        scope=body["scope"],
        topic=body["topic"],
        source=body.get("source", "web"),
        frequency=body.get("frequency", "daily"),
    )


@router.delete("/search-topics/{topic_id}")
async def api_remove_search_topic(topic_id: str):
    """Remove a search topic."""
    return await pg.remove_search_topic(topic_id)


@router.post("/search-topics/{topic_id}/toggle")
async def api_toggle_search_topic(topic_id: str, body: dict):
    """Enable/disable a search topic."""
    return await pg.toggle_search_topic(topic_id, body.get("enabled", True))


@router.post("/search-topics/run")
async def api_run_topic_monitor(body: dict):
    """Manually trigger topic monitor run."""
    from src.connectors.topic_monitor import run_topic_monitor
    from src.connectors.web_search import WebSearchConnector
    from src.connectors.social_search import SocialSearchConnector

    stats = await run_topic_monitor(
        pg, push,
        web_search=WebSearchConnector(),
        social_search=SocialSearchConnector(),
        limit_per_topic=body.get("limit", 5),
    )
    return stats


# --- Reconcile Log ---

@router.get("/reconcile-log")
async def api_reconcile_log(limit: int = 20):
    """List recent reconcile runs with timestamps and results."""
    return await pg.list_reconcile_log(limit=limit)


# --- Models ---

@router.get("/models")
async def api_models():
    """List available Ollama models."""
    try:
        import httpx
        settings = embedder.settings if embedder else __import__("src.config").Settings()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "name": m.get("name"),
                    "size": m.get("size"),
                    "modified_at": m.get("modified_at"),
                }
                for m in data.get("models", [])
            ]
    except Exception:
        return []