"""Push — add knowledge to synapse vault

Inspired by: MemPalace (zero-LLM write), OpenKB (hash dedup)
"""

import json
from pathlib import Path
from typing import Optional

from synapse.store.sqlite_store import SQLiteStore
from synapse.store.lancedb_store import LanceDBStore
from synapse.scope.manager import ScopeManager, detect_scope


class Push:
    """Push knowledge into the vault."""

    def __init__(self, sqlite: SQLiteStore, lancedb: LanceDBStore, scope_mgr: ScopeManager):
        self.sqlite = sqlite
        self.lancedb = lancedb
        self.scope_mgr = scope_mgr

    def push_text(
        self,
        title: str,
        content: str,
        scope: Optional[str] = None,
        doc_type: str = "learning",
        source_file: Optional[str] = None,
        concepts: Optional[list[str]] = None,
        embed: bool = True,
    ) -> dict:
        """Push text content to vault.

        Args:
            title: Document title
            content: Text content
            scope: Scope (auto-detect if None)
            doc_type: learning, pattern, architecture, retro
            source_file: Original file path
            concepts: Concept tags
            embed: Whether to generate vector embedding

        Returns:
            {doc_id, scope, status}
        """
        resolved_scope = self.scope_mgr.resolve_scope(source_file, scope)

        # SQLite first (fast, dedup)
        doc_id = self.sqlite.add(
            title=title,
            content=content,
            scope=resolved_scope,
            doc_type=doc_type,
            source_file=source_file,
            concepts=concepts,
        )

        # LanceDB (slower, embed)
        if embed:
            try:
                self.lancedb.add(
                    doc_id=doc_id,
                    title=title,
                    content=content,
                    scope=resolved_scope,
                    doc_type=doc_type,
                    source_file=source_file,
                )
            except Exception as e:
                return {"doc_id": doc_id, "scope": resolved_scope, "status": f"indexed_sqlite_only: {e}"}

        return {"doc_id": doc_id, "scope": resolved_scope, "status": "indexed"}

    def push_file(self, file_path: str, scope: Optional[str] = None, doc_type: str = "learning") -> dict:
        """Push a file's content to vault."""
        path = Path(file_path)
        if not path.exists():
            return {"doc_id": None, "scope": None, "status": "file_not_found"}

        content = path.read_text(encoding="utf-8", errors="replace")
        title = path.stem

        return self.push_text(
            title=title,
            content=content,
            scope=scope,
            doc_type=doc_type,
            source_file=str(path),
        )

    def push_learnings_dir(self, dir_path: str, scope: Optional[str] = None) -> list[dict]:
        """Push all learning files from a directory."""
        path = Path(dir_path)
        if not path.exists():
            return []

        results = []
        for md_file in sorted(path.rglob("*.md")):
            result = self.push_file(str(md_file), scope=scope, doc_type="learning")
            results.append(result)

        return results