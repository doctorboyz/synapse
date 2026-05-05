"""PostToolUse hook handler — auto-ingest oracle brain files into mysynapse.

Called by Claude Code hooks after Write/Edit on files under κ/ or ψ/ paths.
Detects oracle metadata from the file path and pushes to mysynapse.
"""

import asyncio
import json
import sys
from pathlib import Path

from src.config import Settings
from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.ingest.oracle_paths import extract_metadata
from src.ingest.push import Push


def is_oracle_brain_path(file_path: str) -> bool:
    """Check if a file path is within an oracle brain structure (κ/ or ψ/)."""
    p = Path(file_path)
    parts = p.parts
    return "κ" in parts or "ψ" in parts


def find_oracle_root(file_path: str) -> str | None:
    """Walk up from file_path to find the oracle project root (has CLAUDE.md)."""
    p = Path(file_path).resolve()
    for parent in [p.parent, *p.parents]:
        if (parent / "CLAUDE.md").exists():
            return str(parent)
    return None


async def ingest_file(file_path: str):
    """Ingest a single file into mysynapse via push pipeline."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        print(f"hook_handler: file not found: {file_path}", file=sys.stderr)
        return

    if not is_oracle_brain_path(file_path):
        return

    oracle_root = find_oracle_root(file_path)
    if not oracle_root:
        print(f"hook_handler: no oracle root found for: {file_path}", file=sys.stderr)
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
    """CLI entry point for hook handler. Reads file path from stdin or argv."""
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        data = json.load(sys.stdin)
        file_path = data.get("file_path", data.get("tool_input", {}).get("file_path", ""))

    if not file_path:
        print("hook_handler: no file_path provided", file=sys.stderr)
        sys.exit(1)

    asyncio.run(ingest_file(file_path))


if __name__ == "__main__":
    main()