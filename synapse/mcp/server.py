"""Synapse MCP server — tools for Claude Code

Uses MCP SDK for proper stdio transport.
Exposes: synapse_search, synapse_push, synapse_scope, synapse_status
"""

from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from synapse.store.sqlite_store import SQLiteStore
from synapse.store.lancedb_store import LanceDBStore
from synapse.retrieve.hybrid_search import HybridSearch
from synapse.scope.manager import ScopeManager
from synapse.ingest.push import Push
from synapse.ingest.init import init_vault


def find_vault_path() -> Path:
    """Find or create synapse vault in current project."""
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        vault = p / ".synapse"
        if vault.exists():
            return vault
    vault = cwd / ".synapse"
    vault.mkdir(parents=True, exist_ok=True)
    return vault


app = Server("synapse")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="synapse_search",
            description="Hybrid search (dense vectors + FTS5 keyword) across knowledge vault",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "scope": {"type": "string", "description": "Filter to scope (optional)"},
                    "limit": {"type": "integer", "description": "Max results", "default": 10},
                    "mode": {"type": "string", "enum": ["hybrid", "dense", "fts"], "default": "hybrid"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="synapse_push",
            description="Add knowledge to the vault",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "scope": {"type": "string", "default": "shared"},
                    "doc_type": {"type": "string", "default": "learning"},
                    "source_file": {"type": "string"},
                },
                "required": ["title", "content"],
            },
        ),
        Tool(
            name="synapse_scope",
            description="List all knowledge scopes",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="synapse_status",
            description="Get vault statistics",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="synapse_init",
            description="Initialize .synapse/ vault in current project. Creates vault.db, vectors/, config.yaml, and adds .synapse/ to .gitignore.",
            inputSchema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "description": "Default scope for this project (e.g. 'emily-oracle')"},
                },
            },
        ),
    ]


def _get_stores():
    vault = find_vault_path()
    sqlite = SQLiteStore(vault)
    try:
        lancedb = LanceDBStore(vault)
    except ImportError:
        lancedb = None
    return sqlite, lancedb, vault


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    import json

    if name == "synapse_search":
        sqlite, lancedb, _ = _get_stores()
        search = HybridSearch(sqlite, lancedb) if lancedb else None
        scope = arguments.get("scope")
        limit = arguments.get("limit", 10)
        mode = arguments.get("mode", "hybrid")
        query = arguments["query"]

        if search:
            results = search.search(query, scope=scope, limit=limit, mode=mode)
        else:
            results = sqlite.search_fts5(query, scope=scope, limit=limit)
            for r in results:
                r["score"] = abs(r["score"])

        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]

    if name == "synapse_push":
        sqlite, lancedb, _ = _get_stores()
        scope_mgr = ScopeManager(sqlite)
        push = Push(sqlite, lancedb, scope_mgr) if lancedb else None
        title = arguments["title"]
        content = arguments["content"]
        scope = arguments.get("scope")
        doc_type = arguments.get("doc_type", "learning")
        source_file = arguments.get("source_file")

        if push:
            result = push.push_text(title, content, scope=scope, doc_type=doc_type, source_file=source_file)
        else:
            doc_id = sqlite.add(title, content, scope=scope or "shared", doc_type=doc_type, source_file=source_file)
            result = {"doc_id": doc_id, "status": "sqlite_only"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    if name == "synapse_scope":
        sqlite, _, _ = _get_stores()
        scopes = ScopeManager(sqlite).list_scopes()
        return [TextContent(type="text", text=json.dumps(scopes, ensure_ascii=False, indent=2))]

    if name == "synapse_status":
        sqlite, lancedb, _ = _get_stores()
        stats = sqlite.stats()
        if lancedb:
            stats["vectors"] = lancedb.stats()
        return [TextContent(type="text", text=json.dumps(stats, ensure_ascii=False, indent=2))]

    if name == "synapse_init":
        scope = arguments.get("scope")
        result = init_vault(Path.cwd(), scope=scope)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())