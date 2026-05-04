"""SQLite store — FTS5 + metadata + scope + supersession

Inspired by: arra-oracle (supersession), MemPalace (wing/room scope)
"""

import json
import logging
import re
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from synapse.exceptions import SQLiteStoreError

log = logging.getLogger("synapse.store.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'shared',
    doc_type TEXT NOT NULL DEFAULT 'learning',
    source_file TEXT,
    concepts TEXT,
    superseded_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    title, content, scope, doc_type,
    content='knowledge_documents',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE INDEX IF NOT EXISTS idx_scope ON knowledge_documents(scope);
CREATE INDEX IF NOT EXISTS idx_hash ON knowledge_documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_type ON knowledge_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_superseded ON knowledge_documents(superseded_by);

CREATE TABLE IF NOT EXISTS supersede_log (
    id TEXT PRIMARY KEY,
    old_id TEXT NOT NULL,
    new_id TEXT NOT NULL,
    reason TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scope_registry (
    name TEXT PRIMARY KEY,
    description TEXT,
    doc_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, vault_path: Path):
        self.db_path = vault_path / "vault.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(SCHEMA)
        except sqlite3.Error as e:
            raise SQLiteStoreError(f"Failed to initialize vault database: {e}") from e

    def _content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add(
        self,
        title: str,
        content: str,
        scope: str = "shared",
        doc_type: str = "learning",
        source_file: Optional[str] = None,
        concepts: Optional[list[str]] = None,
    ) -> str:
        """Add a document. Returns doc ID. Skips if hash exists (dedup)."""
        content_hash = self._content_hash(content)

        existing = self._conn.execute(
            "SELECT id FROM knowledge_documents WHERE content_hash = ?",
            (content_hash,),
        ).fetchone()
        if existing:
            log.debug("Dedup: content hash %s already exists as %s", content_hash, existing["id"])
            return existing["id"]

        doc_id = str(uuid4())
        now = self._now()
        concepts_json = json.dumps(concepts or [])

        try:
            self._conn.execute(
                """INSERT INTO knowledge_documents
                (id, title, content, content_hash, scope, doc_type, source_file, concepts, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, title, content, content_hash, scope, doc_type, source_file, concepts_json, now),
            )

            self._conn.execute(
                """INSERT INTO knowledge_fts (rowid, title, content, scope, doc_type)
                VALUES (?, ?, ?, ?, ?)""",
                (self._conn.execute("SELECT last_insert_rowid()").fetchone()[0], title, content, scope, doc_type),
            )

            self._update_scope_count(scope, delta=1)
            self._conn.commit()
            log.info("Added document %s (%s/%s)", doc_id[:8], scope, doc_type)
        except sqlite3.Error as e:
            self._conn.rollback()
            raise SQLiteStoreError(f"Failed to add document: {e}") from e

        return doc_id

    def supersede(self, old_id: str, new_content: str, reason: str = "updated", lancedb=None) -> str:
        """Supersede a document (never delete). Returns new doc ID."""
        from synapse.exceptions import LanceDBStoreError

        old = self._conn.execute(
            "SELECT * FROM knowledge_documents WHERE id = ?", (old_id,)
        ).fetchone()
        if not old:
            raise SQLiteStoreError(f"Document {old_id} not found")

        # Skip if content unchanged (prevents self-referencing)
        new_hash = self._content_hash(new_content)
        if new_hash == old["content_hash"]:
            log.debug("Supersede skipped: content unchanged for %s", old_id)
            return old_id

        new_id = self.add(
            title=old["title"],
            content=new_content,
            scope=old["scope"],
            doc_type=old["doc_type"],
            source_file=old["source_file"],
            concepts=json.loads(old["concepts"]) if old["concepts"] else None,
        )

        try:
            now = self._now()
            self._conn.execute(
                "UPDATE knowledge_documents SET superseded_by = ?, updated_at = ? WHERE id = ?",
                (new_id, now, old_id),
            )
            self._conn.execute(
                "INSERT INTO supersede_log (id, old_id, new_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), old_id, new_id, reason, now),
            )

            # Remove stale FTS entry for superseded doc
            old_rowid = self._conn.execute(
                "SELECT rowid FROM knowledge_documents WHERE id = ?", (old_id,)
            ).fetchone()
            if old_rowid:
                self._conn.execute("DELETE FROM knowledge_fts WHERE rowid = ?", (old_rowid[0],))

            # Decrement old scope count
            self._update_scope_count(old["scope"], delta=-1)

            self._conn.commit()
        except sqlite3.Error as e:
            self._conn.rollback()
            raise SQLiteStoreError(f"Failed to supersede document {old_id}: {e}") from e

        # Sync LanceDB vectors if available
        if lancedb:
            try:
                lancedb.add(
                    doc_id=new_id,
                    title=old["title"],
                    content=new_content,
                    scope=old["scope"],
                    doc_type=old["doc_type"],
                    source_file=old["source_file"],
                )
            except LanceDBStoreError as e:
                log.warning("Failed to sync LanceDB vectors for superseded doc %s: %s", old_id, e)

        log.info("Superseded %s → %s", old_id[:8], new_id[:8])
        return new_id

    def search_fts5(self, query: str, scope: Optional[str] = None, limit: int = 20) -> list[dict]:
        """FTS5 keyword search. Returns list of {id, title, scope, doc_type, rank}."""
        clean_query = self._sanitize_fts(query)
        if not clean_query:
            return []

        try:
            if scope:
                sql = """
                    SELECT d.id, d.title, d.scope, d.doc_type, f.rank
                    FROM knowledge_fts f
                    JOIN knowledge_documents d ON d.rowid = f.rowid
                    WHERE knowledge_fts MATCH ? AND d.scope = ? AND d.superseded_by IS NULL
                    ORDER BY f.rank LIMIT ?
                """
                rows = self._conn.execute(sql, (clean_query, scope, limit)).fetchall()
            else:
                sql = """
                    SELECT d.id, d.title, d.scope, d.doc_type, f.rank
                    FROM knowledge_fts f
                    JOIN knowledge_documents d ON d.rowid = f.rowid
                    WHERE knowledge_fts MATCH ? AND d.superseded_by IS NULL
                    ORDER BY f.rank LIMIT ?
                """
                rows = self._conn.execute(sql, (clean_query, limit)).fetchall()
        except sqlite3.Error as e:
            raise SQLiteStoreError(f"FTS5 search failed: {e}") from e

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "scope": r["scope"],
                "doc_type": r["doc_type"],
                "score": float(r["rank"]),
            }
            for r in rows
        ]

    def get(self, doc_id: str) -> Optional[dict]:
        """Get document by ID."""
        row = self._conn.execute(
            "SELECT * FROM knowledge_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["concepts"] = json.loads(d["concepts"]) if d["concepts"] else []
        return d

    def list_scopes(self) -> list[dict]:
        """List all scopes with doc counts."""
        rows = self._conn.execute(
            "SELECT name, description, doc_count, created_at FROM scope_registry ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        """Vault statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as c FROM knowledge_documents WHERE superseded_by IS NULL"
        ).fetchone()["c"]
        scopes = self._conn.execute(
            "SELECT scope, COUNT(*) as c FROM knowledge_documents WHERE superseded_by IS NULL GROUP BY scope"
        ).fetchall()
        types = self._conn.execute(
            "SELECT doc_type, COUNT(*) as c FROM knowledge_documents WHERE superseded_by IS NULL GROUP BY doc_type"
        ).fetchall()
        superseded = self._conn.execute(
            "SELECT COUNT(*) as c FROM knowledge_documents WHERE superseded_by IS NOT NULL"
        ).fetchone()["c"]

        return {
            "total_documents": total,
            "superseded_documents": superseded,
            "by_scope": {r["scope"]: r["c"] for r in scopes},
            "by_type": {r["doc_type"]: r["c"] for r in types},
        }

    def _sanitize_fts(self, query: str) -> str:
        """Sanitize query for FTS5."""
        clean = re.sub(r'[^\w\s]', ' ', query)
        tokens = clean.split()
        return " OR ".join(f"\"{t}\"" for t in tokens if len(t) >= 2) if tokens else ""

    def _update_scope_count(self, scope: str, delta: int = 1):
        """Update or create scope in registry."""
        existing = self._conn.execute(
            "SELECT name FROM scope_registry WHERE name = ?", (scope,)
        ).fetchone()
        if not existing:
            self._conn.execute(
                "INSERT INTO scope_registry (name, doc_count, created_at) VALUES (?, ?, ?)",
                (scope, delta, self._now()),
            )
        else:
            self._conn.execute(
                "UPDATE scope_registry SET doc_count = doc_count + ? WHERE name = ?",
                (delta, scope),
            )

    def close(self):
        self._conn.close()