"""synapse — FastAPI app + CLI entry point."""

import argparse
import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from src.api.routes import init_routes, router
from src.config import Settings
from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder

log = logging.getLogger("synapse")

_pg: PgStore | None = None
_qdrant: QdrantStore | None = None

app = FastAPI(title="synapse", version="3.0.0",
              description="Agent-first knowledge service for the Oracle ecosystem")
app.include_router(router)


@app.on_event("startup")
async def startup():
    global _pg, _qdrant

    settings = Settings()
    _pg = PgStore(settings)
    await _pg.connect()
    await _pg.init_schema()

    _qdrant = None
    try:
        _qdrant = QdrantStore(settings)
        await _qdrant.connect()
    except Exception:
        log.warning("Qdrant not available, running in FTS-only mode")

    embedder = OllamaEmbedder(settings)
    init_routes(_pg, _qdrant, embedder)


@app.on_event("shutdown")
async def shutdown():
    if _pg:
        await _pg.close()
    if _qdrant:
        await _qdrant.close()


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


if __name__ == "__main__":
    cli_main()