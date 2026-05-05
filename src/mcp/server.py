"""MCP server — 10 tools for agent-first knowledge access via stdio."""

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.config import Settings
from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.ingest.push import Push
from src.ingest.oracle_paths import validate_doc_type, validate_trace_relation
from src.retrieve.hybrid_search import HybridSearch

log = logging.getLogger("synapse.mcp")

TOOL_DEFINITIONS = [
    Tool(
        name="synapse_search",
        description="Search knowledge vault with hybrid dense+keyword search. Returns ranked results with metadata.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "scope": {"type": "string", "description": "Filter to scope"},
                "doc_type": {"type": "string", "description": "Filter by doc_type"},
                "oracle": {"type": "string", "description": "Filter by oracle name"},
                "source_project": {"type": "string", "description": "Filter by source project"},
                "concepts": {"type": "array", "items": {"type": "string"}, "description": "Filter by concepts"},
                "limit": {"type": "integer", "description": "Max results", "default": 10},
                "mode": {"type": "string", "enum": ["hybrid", "dense", "fts"], "default": "hybrid"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="synapse_push",
        description="Add knowledge to the vault. Auto-detects oracle metadata from source_file path.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Document title"},
                "content": {"type": "string", "description": "Document content (markdown)"},
                "scope": {"type": "string", "default": "shared"},
                "doc_type": {"type": "string", "default": "learning",
                             "description": "One of: learning, pattern, retro, reference, handoff, protocol, wisdom, instinct, log, note"},
                "source_file": {"type": "string", "description": "Original file path"},
                "source_project": {"type": "string", "description": "Project that sent this knowledge"},
                "concepts": {"type": "array", "items": {"type": "string"}},
                "tags": {"type": "array", "items": {"type": "string"}},
                "oracle_name": {"type": "string"},
                "brain_path": {"type": "string"},
                "brain_tier": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    ),
    Tool(
        name="synapse_supersede",
        description="Supersede a document with updated knowledge. Old doc never deleted — marked superseded_by.",
        inputSchema={
            "type": "object",
            "properties": {
                "old_id": {"type": "string", "description": "UUID of document to supersede"},
                "new_content": {"type": "string", "description": "Updated content"},
                "new_title": {"type": "string", "description": "Optional new title"},
                "reason": {"type": "string", "default": "updated"},
            },
            "required": ["old_id", "new_content"],
        },
    ),
    Tool(
        name="synapse_trace",
        description="Create a trace link between two knowledge documents.",
        inputSchema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "target_id": {"type": "string"},
                "relation": {"type": "string", "enum": ["derived_from", "refines", "contradicts", "extends"]},
                "confidence": {"type": "number", "default": 1.0},
            },
            "required": ["source_id", "target_id", "relation"],
        },
    ),
    Tool(
        name="synapse_trace_chain",
        description="Follow trace chain from a document. Returns all linked documents.",
        inputSchema={
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "direction": {"type": "string", "enum": ["both", "upstream", "downstream"], "default": "both"},
                "max_depth": {"type": "integer", "default": 5},
                "relation": {"type": "string", "description": "Filter to specific relation type"},
            },
            "required": ["doc_id"],
        },
    ),
    Tool(
        name="synapse_concepts",
        description="List or search concepts across the knowledge vault.",
        inputSchema={
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Search concepts by name"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    ),
    Tool(
        name="synapse_get",
        description="Retrieve a full knowledge document by ID, including supersession history.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Document UUID"},
                "include_chain": {"type": "boolean", "default": True},
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="synapse_scope",
        description="List all knowledge scopes with document counts.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="synapse_stats",
        description="Get knowledge vault statistics: total docs, by type, by scope, by oracle.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="synapse_list",
        description="List documents with filters. Returns summaries.",
        inputSchema={
            "type": "object",
            "properties": {
                "scope": {"type": "string"},
                "doc_type": {"type": "string"},
                "oracle": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0},
                "order": {"type": "string", "enum": ["newest", "oldest"], "default": "newest"},
            },
        },
    ),
]


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
                results = await search.search(
                    query=arguments["query"],
                    scope=arguments.get("scope"),
                    doc_type=arguments.get("doc_type"),
                    oracle=arguments.get("oracle"),
                    source_project=arguments.get("source_project"),
                    concepts=arguments.get("concepts"),
                    limit=arguments.get("limit", 10),
                    mode=arguments.get("mode", "hybrid"),
                )
                return [TextContent(type="text", text=json.dumps(results, indent=2))]

            elif name == "synapse_push":
                result = await push.push_text(
                    title=arguments["title"],
                    content=arguments["content"],
                    scope=arguments.get("scope", "shared"),
                    doc_type=arguments.get("doc_type", "learning"),
                    source_file=arguments.get("source_file"),
                    source_project=arguments.get("source_project"),
                    concepts=arguments.get("concepts"),
                    tags=arguments.get("tags"),
                    oracle_name=arguments.get("oracle_name"),
                    brain_path=arguments.get("brain_path"),
                    brain_tier=arguments.get("brain_tier"),
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "synapse_supersede":
                result = await pg.supersede(
                    old_id=arguments["old_id"],
                    new_content=arguments["new_content"],
                    reason=arguments.get("reason", "updated"),
                    new_title=arguments.get("new_title"),
                )
                if qdrant:
                    await qdrant.mark_superseded(arguments["old_id"])
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "synapse_trace":
                validate_trace_relation(arguments["relation"])
                result = await pg.add_trace(
                    source_id=arguments["source_id"],
                    target_id=arguments["target_id"],
                    relation=arguments["relation"],
                    confidence=arguments.get("confidence", 1.0),
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "synapse_trace_chain":
                results = await pg.get_trace_chain(
                    doc_id=arguments["doc_id"],
                    direction=arguments.get("direction", "both"),
                    max_depth=arguments.get("max_depth", 5),
                    relation=arguments.get("relation"),
                )
                return [TextContent(type="text", text=json.dumps(results, indent=2))]

            elif name == "synapse_concepts":
                results = await pg.list_concepts(
                    search=arguments.get("search"),
                    limit=arguments.get("limit", 50),
                )
                return [TextContent(type="text", text=json.dumps(results, indent=2))]

            elif name == "synapse_get":
                doc = await pg.get(
                    doc_id=arguments["id"],
                    include_chain=arguments.get("include_chain", True),
                )
                if doc is None:
                    return [TextContent(type="text", text=json.dumps({"error": "not found"}))]
                return [TextContent(type="text", text=json.dumps(doc, indent=2, default=str))]

            elif name == "synapse_scope":
                scopes = await pg.list_scopes()
                return [TextContent(type="text", text=json.dumps(scopes, indent=2))]

            elif name == "synapse_stats":
                stats = await pg.stats()
                return [TextContent(type="text", text=json.dumps(stats, indent=2, default=str))]

            elif name == "synapse_list":
                docs = await pg.list_docs(
                    scope=arguments.get("scope"),
                    doc_type=arguments.get("doc_type"),
                    oracle=arguments.get("oracle"),
                    limit=arguments.get("limit", 20),
                    offset=arguments.get("offset", 0),
                    order=arguments.get("order", "newest"),
                )
                return [TextContent(type="text", text=json.dumps(docs, indent=2, default=str))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        except Exception as e:
            log.error("Tool %s error: %s", name, e)
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    return server


async def run_server():
    app = await create_app()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run_server())